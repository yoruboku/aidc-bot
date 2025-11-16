#!/usr/bin/env python3
"""
VITO - Discord -> Gemini bot (main.py)
Uses Playwright persistent context stored in ./playwright_data/

Behavior:
- Mention-based: only responds when @VITO is mentioned.
- Per-user Gemini chats (each user has own page).
- newchat command resets that user's Gemini chat.
- stop command:
    * Anyone can call stop.
    * Nobody can stop 'yoruboku' or the configured OWNER while their answer is running.
    * 'yoruboku' can preempt and stop everyone.
- Priority:
    * If 'yoruboku' sends a message, all running tasks + queue are cleared
      and their question runs first.
- Answers:
    * Bot mentions the asker at the start of the message.
    * The Gemini answer is forwarded as-is (no extra links or modifications).
"""

import os
import asyncio
import discord
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ID = os.getenv("BOT_ID")  # numeric id as string
OWNER_USERNAME = (os.getenv("OWNER_USERNAME") or "").strip().lower()
PRIORITY_NAME = "yoruboku"  # your global username

if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found. Run the installer to create a .env file.")
    raise SystemExit(1)

# Discord client setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Playwright globals
playwright_instance = None
browser_context = None

# Per-user pages (user_id -> Page)
user_pages = {}
task_queue = asyncio.Queue()

# STOP / priority state
stop_flag = False
running_tasks = set()
current_served_username = None  # lowercased username of user currently being answered

# Selectors
INPUT_SELECTOR = "div[contenteditable='true']"
RESPONSE_SELECTOR = "div.markdown"

# Timings
FIRST_RESPONSE_TIMEOUT = 60_000   # ms
POLL_INTERVAL = 0.15             # seconds
STABLE_REQUIRED = 2              # fewer cycles for speed


# ----------------- Helpers -----------------

def get_username(user: discord.abc.User) -> str:
    """Get a stable, lowercase username (prefer global name)."""
    name = getattr(user, "name", None) or ""
    display = getattr(user, "display_name", None) or ""
    return (name or display).lower()


def is_priority_user(user: discord.abc.User) -> bool:
    return get_username(user) == PRIORITY_NAME.lower()


def is_owner_user(user: discord.abc.User) -> bool:
    if not OWNER_USERNAME:
        return False
    return get_username(user) == OWNER_USERNAME


def clear_all_tasks():
    """Clear queue & cancel running tasks."""
    global stop_flag
    stop_flag = True
    # Clear queue
    while not task_queue.empty():
        try:
            task_queue.get_nowait()
            task_queue.task_done()
        except Exception:
            pass
    # Cancel running workers
    for t in list(running_tasks):
        try:
            t.cancel()
        except Exception:
            pass
    stop_flag = False


def can_stop_caller(message: discord.Message) -> bool:
    """
    Logic:
    - If nobody is being answered -> anyone can stop.
    - If current user is 'yoruboku' -> only yoruboku can stop.
    - If current user is OWNER -> only OWNER or yoruboku can stop.
    - Otherwise (normal user) -> anyone can stop.
    """
    global current_served_username

    caller_name = get_username(message.author)

    if current_served_username is None:
        return True

    if current_served_username == PRIORITY_NAME.lower():
        # Only you can stop your own answer
        return caller_name == PRIORITY_NAME.lower()

    if OWNER_USERNAME and current_served_username == OWNER_USERNAME:
        # Only owner or you can stop owner's answer
        return caller_name in {OWNER_USERNAME, PRIORITY_NAME.lower()}

    # Normal user: anyone can stop
    return True


# ----------------- Playwright / Gemini -----------------

async def ensure_browser():
    """Start Playwright and persistent browser context if not running."""
    global playwright_instance, browser_context
    if playwright_instance and browser_context:
        return

    playwright_instance = await async_playwright().start()
    browser_context = await playwright_instance.chromium.launch_persistent_context(
        user_data_dir="playwright_data",
        headless=True,
    )


async def get_user_page(user_id: int):
    """Return a per-user page. Create new if missing or dead."""
    await ensure_browser()

    page = user_pages.get(user_id)
    if page:
        try:
            await page.title()
            return page
        except Exception:
            try:
                await page.close()
            except Exception:
                pass
            user_pages.pop(user_id, None)

    page = await browser_context.new_page()
    await page.goto("https://gemini.google.com/")

    try:
        await page.wait_for_selector(INPUT_SELECTOR, timeout=FIRST_RESPONSE_TIMEOUT)
    except PlaywrightTimeout:
        await page.close()
        raise RuntimeError("Gemini input not found - are you logged in? Re-run installer to login to Gemini.")

    user_pages[user_id] = page
    return page


async def ask_gemini(page, question: str) -> str:
    """Send a question and wait for Gemini to finish generating the full answer."""
    previous_answers = await page.query_selector_all(RESPONSE_SELECTOR)
    prev_count = len(previous_answers)

    await page.click(INPUT_SELECTOR)
    await page.fill(INPUT_SELECTOR, question)
    await page.keyboard.press("Enter")

    try:
        await page.wait_for_selector(RESPONSE_SELECTOR, timeout=FIRST_RESPONSE_TIMEOUT)
    except PlaywrightTimeout:
        return "Gemini did not respond in time. Possibly rate-limited."

    # Wait until Gemini finishes streaming (Stop button gone)
    while True:
        stop_btn = await page.query_selector("button[aria-label='Stop']")
        if not stop_btn:
            break
        await asyncio.sleep(POLL_INTERVAL)

    # Wait for new answer element
    while True:
        answers = await page.query_selector_all(RESPONSE_SELECTOR)
        if len(answers) > prev_count:
            new_el = answers[-1]
            break
        await asyncio.sleep(POLL_INTERVAL)

    previous_text = ""
    stable = 0

    while True:
        try:
            current_text = await new_el.inner_text()
        except Exception:
            answers = await page.query_selector_all(RESPONSE_SELECTOR)
            if not answers:
                await asyncio.sleep(POLL_INTERVAL)
                continue
            new_el = answers[-1]
            current_text = await new_el.inner_text()

        if current_text == previous_text:
            stable += 1
        else:
            stable = 0
            previous_text = current_text

        if stable >= STABLE_REQUIRED:
            break

        await asyncio.sleep(POLL_INTERVAL)

    answers = await page.query_selector_all(RESPONSE_SELECTOR)
    answer_text = await answers[-1].inner_text()
    return answer_text.strip()


# ----------------- Worker -----------------

async def worker():
    global stop_flag, current_served_username

    while True:
        user_id, asker_name, asker_mention, question, channel = await task_queue.get()

        if stop_flag:
            task_queue.task_done()
            continue

        thinking_msg = await channel.send("🧠 Thinking…")

        current_task = asyncio.current_task()
        running_tasks.add(current_task)
        current_served_username = asker_name  # mark who is being answered

        try:
            page = await get_user_page(user_id)
            answer = await ask_gemini(page, question)
        except Exception as e:
            answer = f"Error: {e}"

        # remove "Thinking…"
        try:
            await thinking_msg.delete()
        except Exception:
            pass

        # prepend mention, forward Gemini text as-is
        full_msg = f"{asker_mention}\n{answer}"

        if len(full_msg) > 1900:
            for i in range(0, len(full_msg), 1800):
                await channel.send(full_msg[i:i+1800])
        else:
            await channel.send(full_msg)

        # cleanup
        running_tasks.discard(current_task)
        if current_served_username == asker_name:
            current_served_username = None

        task_queue.task_done()


# ----------------- Discord Events -----------------

@client.event
async def on_ready():
    print(f"VITO is online as {client.user}")
    asyncio.create_task(start_playwright())
    asyncio.create_task(worker())


@client.event
async def on_message(message: discord.Message):
    global stop_flag

    if message.author == client.user:
        return

    if f"<@{BOT_ID}>" not in message.content:
        return

    content_raw = message.content.split(">", 1)[1].strip()
    content_lc = content_raw.lower()
    author_name = get_username(message.author)
    author_mention = message.author.mention

    # If YOU (yoruboku) speak: full preempt
    if is_priority_user(message):
        clear_all_tasks()
        # Optionally reload pages to stop streaming
        for page in list(user_pages.values()):
            try:
                await page.reload()
            except Exception:
                pass

    # STOP command
    if content_lc.startswith("stop"):
        if not can_stop_caller(message):
            await message.channel.send("❌ You cannot stop the current owner/priority answer.")
            return

        clear_all_tasks()
        for page in list(user_pages.values()):
            try:
                await page.reload()
            except Exception:
                pass

        await message.channel.send("🛑 Stopped.")
        return

    # NEWCHAT
    if content_lc.startswith("newchat"):
        old = user_pages.pop(message.author.id, None)
        if old:
            try:
                await old.close()
            except Exception:
                pass

        question = content_raw[len("newchat"):].strip()
        if not question:
            await message.channel.send("New chat created. Ask your next question.")
            return

        await task_queue.put((message.author.id, author_name, author_mention, question, message.channel))
        return

    # Normal question
    question = content_raw
    await task_queue.put((message.author.id, author_name, author_mention, question, message.channel))


# ----------------- Playwright loop -----------------

async def start_playwright():
    await ensure_browser()
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
