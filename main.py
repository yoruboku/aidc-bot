#!/usr/bin/env python3
"""
VITO - Discord -> Gemini bot (main.py)
Uses Playwright persistent context stored in ./playwright_data/
"""

import os
import asyncio
import discord
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ID = os.getenv("BOT_ID")  # numeric id as string

if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found. Run the installer to create a .env file or set DISCORD_TOKEN in the environment.")
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

# STOP SYSTEM
stop_flag = False
running_tasks = set()

# OWNER LOCK SYSTEM
owner_lock = False
owner_active_task = None

# Selectors
INPUT_SELECTOR = "div[contenteditable='true']"
RESPONSE_SELECTOR = "div.markdown"

# Timings
FIRST_RESPONSE_TIMEOUT = 60_000
POLL_INTERVAL = 0.20
STABLE_REQUIRED = 3


def user_is_owner(message):
    """Owner priority check (matches both username + display name)."""
    username = str(message.author.name).lower()
    display = str(message.author.display_name).lower()
    return username == "yoruboku" or display == "yoruboku"


async def ensure_browser():
    """Start playwright and persistent browser context if not running."""
    global playwright_instance, browser_context
    if playwright_instance and browser_context:
        return

    playwright_instance = await async_playwright().start()

    browser_context = await playwright_instance.chromium.launch_persistent_context(
        user_data_dir="playwright_data",
        headless=True,
    )


async def get_user_page(user_id: int):
    """Return a per-user page. Create new if missing."""
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


async def ask_gemini(page, question: str):
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

    # Wait until Gemini finishes streaming
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

    # Detect errors
    if await page.query_selector("button:has-text('Try again')"):
        return "Gemini shows a 'Try again' button. Probably rate-limited."
    if await page.query_selector("text=limit") or await page.query_selector("text=usage limit"):
        return "Gemini usage limit reached."
    if await page.query_selector("text=Something went wrong"):
        return "Gemini had an internal error."

    # Get final answer
    answers = await page.query_selector_all(RESPONSE_SELECTOR)
    answer_text = await answers[-1].inner_text()

    # Video suggestion auto-detect
    lower_q = question.lower()
    if "suggest" in lower_q and "video" in lower_q:
        yt = "https://www.youtube.com/results?search_query=" + question.replace(" ", "+")
        answer_text += f"\n\n🔗 **Suggested video:** {yt}"

    return answer_text


async def worker():
    global stop_flag, owner_lock, owner_active_task

    while True:
        user_id, question, channel, thinking_msg = await task_queue.get()

        # If STOP is active skip work
        if stop_flag:
            try:
                await thinking_msg.delete()
            except:
                pass
            task_queue.task_done()
            continue

        current_task = asyncio.current_task()
        running_tasks.add(current_task)

        # OWNER LOCK
        try:
            member = channel.guild.get_member(user_id)
            if member and str(member.name).lower() == "yoruboku":
                owner_lock = True
                owner_active_task = current_task
        except:
            pass

        try:
            page = await get_user_page(user_id)
            answer = await ask_gemini(page, question)

            # If stop wasn't triggered, send result
            if not stop_flag:
                try:
                    await thinking_msg.delete()
                except:
                    pass

                if isinstance(answer, str) and len(answer) > 1900:
                    for i in range(0, len(answer), 1800):
                        await channel.send(answer[i:i+1800])
                else:
                    await channel.send(answer)

        except Exception as e:
            if not stop_flag:
                try:
                    await thinking_msg.delete()
                except:
                    pass
                await channel.send(f"Error: {e}")

        finally:
            # Release owner lock if this was the owner's task
            if current_task == owner_active_task:
                owner_lock = False
                owner_active_task = None

            running_tasks.discard(current_task)
            task_queue.task_done()


@client.event
async def on_ready():
    print(f"VITO is online as {client.user}")
    asyncio.create_task(start_playwright())
    asyncio.create_task(worker())


@client.event
async def on_message(message):
    global stop_flag, owner_lock

    if message.author == client.user:
        return

    if f"<@{BOT_ID}>" not in message.content:
        return

    # OWNER PRIORITY – if you speak, cancel EVERYTHING immediately
    if user_is_owner(message):
        stop_flag = True

        # Clear queue
        while not task_queue.empty():
            try:
                task_queue.get_nowait()
                task_queue.task_done()
            except:
                pass

        # Cancel tasks
        for t in list(running_tasks):
            try:
                t.cancel()
            except:
                pass

        # Reset pages to avoid stuck streaming
        for page in list(user_pages.values()):
            try:
                await page.reload()
            except:
                pass

        stop_flag = False  # ready for your real query

    # Extract content
    content = message.content.split(">", 1)[1].strip().lower()

    # STOP COMMAND
    if "stop" in content:
        # Prevent others from stopping while owner lock is active
        if owner_lock and not user_is_owner(message):
            await message.channel.send("⛔ VITO is currently answering the owner. Stop ignored.")
            return

        stop_flag = True

        while not task_queue.empty():
            try:
                task_queue.get_nowait()
                task_queue.task_done()
            except:
                pass

        for t in list(running_tasks):
            try:
                t.cancel()
            except:
                pass

        for page in list(user_pages.values()):
            try:
                await page.reload()
            except:
                pass

        await message.channel.send("🛑 All tasks stopped.")
        return

    stop_flag = False

    # NEWCHAT
    if content.startswith("newchat"):
        old = user_pages.pop(message.author.id, None)
        if old:
            try:
                await old.close()
            except:
                pass

        q = content.replace("newchat", "", 1).strip()
        if not q:
            await message.channel.send("New chat created. Ask your next question.")
            return

        thinking_msg = await message.channel.send("🧠 Starting a fresh chat...")
        await task_queue.put((message.author.id, q, message.channel, thinking_msg))
        return

    # NORMAL QUESTION
    question = content
    thinking_msg = await message.channel.send("🧠 Thinking…")
    await task_queue.put((message.author.id, question, message.channel, thinking_msg))


async def start_playwright():
    await ensure_browser()
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
