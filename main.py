#!/usr/bin/env python3
"""
VITO - Discord -> Gemini bot (main.py)
Fast, accurate, per-user chats, with priority + stop logic.

Behavior:
- Only responds when mentioned: @VITO (or bot mention)
- Each Discord user gets their own Gemini chat (separate Playwright page).
- newchat: resets that user's Gemini page.
- stop: cancels all current/queued work, resets pages, BUT does NOT kill the bot.
- Priority:
    * 'yoruboku' has absolute priority.
      - When they ask, all current work is cancelled and their question runs first.
      - Nobody can stop their answer except themselves.
    * One extra OWNER_USERNAME (from .env) has elevated rights:
      - Cannot be stopped except by themselves or 'yoruboku'.
- Answers:
    * Bot mentions the asker at the start: "<@user>\n<gemini answer>"
    * Gemini answer is forwarded exactly (no extra links/edits).
"""

import os
import asyncio
import discord
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ID = os.getenv("BOT_ID")  # numeric id as string
OWNER_USERNAME = (os.getenv("OWNER_USERNAME") or "").strip().lower()
PRIORITY_NAME = "yoruboku"  # your username

if not DISCORD_TOKEN or not BOT_ID:
    print("ERROR: DISCORD_TOKEN or BOT_ID missing in .env")
    raise SystemExit(1)

# ------------ Discord setup ------------

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ------------ Playwright / Gemini state ------------

playwright_instance = None
browser_context = None

# Per-user pages: user_id -> Page
user_pages: dict[int, object] = {}

# Queue of jobs: each item is a tuple:
# (user_id, author_username, author_mention, question, channel, thinking_msg, job_token)
task_queue: asyncio.Queue = asyncio.Queue()

# Global generation token for cancellation
generation_id: int = 0

# Name of user currently being answered (lowercase)
current_served_username: str | None = None


# ------------ Utility: user name & roles ------------

def uname(user: discord.abc.User) -> str:
    name = getattr(user, "name", None) or ""
    display = getattr(user, "display_name", None) or ""
    return (name or display).lower()


def is_priority_user(user: discord.abc.User) -> bool:
    return uname(user) == PRIORITY_NAME.lower()


def is_owner_user(user: discord.abc.User) -> bool:
    if not OWNER_USERNAME:
        return False
    return uname(user) == OWNER_USERNAME


def can_stop_caller(message: discord.Message) -> bool:
    """
    Rules:
    - If no one is currently being answered: anyone can stop.
    - If current is 'yoruboku': only 'yoruboku' can stop.
    - If current is OWNER_USERNAME: only OWNER or 'yoruboku' can stop.
    - Otherwise: anyone can stop.
    """
    global current_served_username

    caller_name = uname(message.author)

    if current_served_username is None:
        return True

    # Priority user cannot be stopped except by themselves
    if current_served_username == PRIORITY_NAME.lower():
        return caller_name == PRIORITY_NAME.lower()

    # Owner cannot be stopped except by owner or priority
    if OWNER_USERNAME and current_served_username == OWNER_USERNAME:
        return caller_name in {OWNER_USERNAME, PRIORITY_NAME.lower()}

    # Normal user: anyone can stop
    return True


# ------------ Playwright helpers ------------

async def ensure_browser():
    """Make sure Playwright + persistent Chromium context is running."""
    global playwright_instance, browser_context
    if playwright_instance and browser_context:
        return

    playwright_instance = await async_playwright().start()
    browser_context = await playwright_instance.chromium.launch_persistent_context(
        "playwright_data",
        headless=True,
    )


async def get_user_page(user_id: int):
    """
    Get or create a Gemini page for a specific user.
    Each user gets their own page → their own chat context.
    """
    await ensure_browser()
    page = user_pages.get(user_id)

    # If page exists and is still alive → reuse
    if page:
        try:
            await page.title()  # will raise if closed
            return page
        except Exception:
            try:
                await page.close()
            except Exception:
                pass
            user_pages.pop(user_id, None)

    # Create new page
    page = await browser_context.new_page()
    await page.goto("https://gemini.google.com/")
    # We don't hard-block on a selector; assume installer logged us in.
    user_pages[user_id] = page
    return page


class JobCancelled(Exception):
    """Internal marker for cancellation via stop/generation_id."""
    pass


async def ask_gemini(page, question: str, job_token: int) -> str:
    """
    Send the question to Gemini and wait for the full answer.

    Faster, custom loop:
    - No big wait_for_selector.
    - We poll for new Markdown blocks and for text stabilization.
    - We also check job_token vs global generation_id to support instant stop.
    """
    global generation_id

    # Count existing answer blocks
    prev_blocks = await page.query_selector_all("div.markdown")
    prev_count = len(prev_blocks)

    # Type + send
    await page.click("div[contenteditable='true']")
    await page.fill("div[contenteditable='true']", question)
    await page.keyboard.press("Enter")

    # Wait for new answer block to appear, with timeout
    max_wait_seconds = 60
    waited = 0.0
    block = None

    while True:
        # Cancellation check
        if job_token != generation_id:
            raise JobCancelled()

        blocks = await page.query_selector_all("div.markdown")
        if len(blocks) > prev_count:
            block = blocks[-1]
            break

        await asyncio.sleep(0.15)
        waited += 0.15
        if waited >= max_wait_seconds:
            return "Gemini did not respond in time."

    # Now wait for the text to stabilize (F2: 2 stable reads)
    stable = 0
    last_text = ""

    while True:
        if job_token != generation_id:
            raise JobCancelled()

        try:
            text = await block.inner_text()
        except Exception:
            # If the node was replaced, grab the last one again
            blocks = await page.query_selector_all("div.markdown")
            if not blocks:
                await asyncio.sleep(0.15)
                continue
            block = blocks[-1]
            text = await block.inner_text()

        if text == last_text:
            stable += 1
        else:
            stable = 0
            last_text = text

        if stable >= 2:
            break

        await asyncio.sleep(0.15)

    return last_text.strip()


# ------------ Stop / reset ------------

async def global_reset(message: discord.Message, notify: bool = True):
    """
    Global stop:
    - Increment generation_id so current jobs see cancellation.
    - Clear queue.
    - Reload all user pages to reset any in-progress streams.
    """
    global generation_id, current_served_username

    generation_id += 1  # this invalidates all current jobs
    current_served_username = None

    # Clear queue
    try:
        while True:
            item = task_queue.get_nowait()
            task_queue.task_done()
    except asyncio.QueueEmpty:
        pass

    # Reload pages to fully clear UI state
    for page in list(user_pages.values()):
        try:
            await page.reload()
        except Exception:
            pass

    if notify:
        await message.channel.send("🧹 System reset complete — VITO is ready.")


# ------------ Worker ------------

async def worker():
    """
    Single worker that processes jobs from the queue sequentially.
    Uses generation_id to support safe cancellation.
    """
    global current_served_username

    while True:
        (
            user_id,
            author_username,
            author_mention,
            question,
            channel,
            thinking_msg,
            job_token,
        ) = await task_queue.get()

        # Mark who's being served
        current_served_username = author_username

        try:
            page = await get_user_page(user_id)
            answer = await ask_gemini(page, question, job_token)
        except JobCancelled:
            # Job was cancelled by a stop/reset: just delete "thinking" and move on
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            current_served_username = None
            task_queue.task_done()
            continue
        except Exception as e:
            answer = f"Error: {e}"

        # Remove "Thinking…" indicator
        try:
            await thinking_msg.delete()
        except Exception:
            pass

        # Prepend mention, forward answer exactly
        full = f"{author_mention}\n{answer}"
        if len(full) > 1900:
            for i in range(0, len(full), 1800):
                await channel.send(full[i:i + 1800])
        else:
            await channel.send(full)

        current_served_username = None
        task_queue.task_done()


# ------------ Discord events ------------

@client.event
async def on_ready():
    print(f"VITO is online as {client.user}")
    asyncio.create_task(start_playwright())
    asyncio.create_task(worker())


@client.event
async def on_message(message: discord.Message):
    global generation_id

    if message.author == client.user:
        return

    # Handle both <@ID> and <@!ID> mention formats
    mention_plain = f"<@{BOT_ID}>"
    mention_nick = f"<@!{BOT_ID}>"

    if mention_plain not in message.content and mention_nick not in message.content:
        return

    # Extract the content AFTER the first '>'
    try:
        content_raw = message.content.split(">", 1)[1].strip()
    except IndexError:
        return

    content_lc = content_raw.lower()
    author_username = uname(message.author)
    author_mention = message.author.mention

    # If YOU speak (priority user), preempt everyone:
    if is_priority_user(message):
        await global_reset(message, notify=False)

    # STOP command: global reset
    if content_lc.startswith("stop"):
        if not can_stop_caller(message):
            await message.channel.send("❌ You cannot stop the current owner/priority answer.")
            return

        await global_reset(message, notify=True)
        return

    # NEWCHAT command: reset only this user's page
    if content_lc.startswith("newchat"):
        # Drop this user's page so a fresh chat starts
        page = user_pages.pop(message.author.id, None)
        if page:
            try:
                await page.close()
            except Exception:
                pass

        question = content_raw[len("newchat"):].strip()
        if not question:
            await message.channel.send("New chat created. Ask your next question.")
            return

        # Show quick feedback
        thinking_msg = await message.channel.send("🧠 Starting a fresh chat…")

        job_token = generation_id  # snapshot current generation
        await task_queue.put(
            (
                message.author.id,
                author_username,
                author_mention,
                question,
                message.channel,
                thinking_msg,
                job_token,
            )
        )
        return

    # Normal question
    question = content_raw

    # Immediate feedback
    thinking_msg = await message.channel.send("🧠 Thinking…")

    job_token = generation_id  # snapshot cancel token
    await task_queue.put(
        (
            message.author.id,
            author_username,
            author_mention,
            question,
            message.channel,
            thinking_msg,
            job_token,
        )
    )


# ------------ Playwright keep-alive ------------

async def start_playwright():
    await ensure_browser()
    while True:
        await asyncio.sleep(2)


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
