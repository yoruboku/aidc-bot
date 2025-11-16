#!/usr/bin/env python3
"""
VITO - Discord -> Gemini bot (main.py)

Persistent Playwright context: ./playwright_data/

Owner system:
- Priority owner: PRIORITY_OWNER (default: 'yoruboku') has absolute priority.
- Installer-configurable owners: OWNER_MAIN, OWNER_EXTRA (comma-separated).
- Admins (server administrators) can STOP and override normal users,
  but NOT while the priority owner is being answered.

Core features:
- Mention-based activation (@VITO)
- Per-user Gemini chat pages
- newchat command to reset user context
- stop command with owner/admin permissions
- Full Gemini answer capture (waits for STOP button to vanish + text to stabilize)
- Video suggestion auto YouTube link when "suggest" + "video" in question
"""

import os
import asyncio
import discord
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ==============================
# ENV + OWNER CONFIG
# ==============================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ID = os.getenv("BOT_ID")

# OWNER config from .env (installer writes these)
OWNER_MAIN = os.getenv("OWNER_MAIN", "").strip()              # single username
OWNER_EXTRA = os.getenv("OWNER_EXTRA", "").strip()            # comma-separated list
PRIORITY_OWNER = os.getenv("PRIORITY_OWNER", "yoruboku").strip().lower()

# Normalize owner usernames (lowercase)
owner_usernames: set[str] = set()
if OWNER_MAIN:
    owner_usernames.add(OWNER_MAIN.lower())
if OWNER_EXTRA:
    for o in (x.strip() for x in OWNER_EXTRA.split(",") if x.strip()):
        owner_usernames.add(o.lower())

# Always ensure priority owner is included in internal logic
owner_usernames.add(PRIORITY_OWNER)

if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found. Run installer to create .env.")
    raise SystemExit(1)

# ==============================
# DISCORD CLIENT
# ==============================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ==============================
# PLAYWRIGHT / GEMINI STATE
# ==============================

playwright_instance = None
browser_context = None

# Per-user pages: user_id -> Page
user_pages: dict[int, object] = {}

# Queue of pending tasks
task_queue: asyncio.Queue = asyncio.Queue()

# STOP / owner lock state
stop_flag: bool = False
running_tasks: set[asyncio.Task] = set()
owner_lock: bool = False
owner_active_task: asyncio.Task | None = None
owner_being_served_username: str | None = None

# Gemini selectors & timing
INPUT_SELECTOR = "div[contenteditable='true']"
RESPONSE_SELECTOR = "div.markdown"
FIRST_RESPONSE_TIMEOUT = 60_000  # ms
POLL_INTERVAL = 0.20             # seconds
STABLE_REQUIRED = 3              # how many identical reads to consider "stable"/finished


# ==============================
# UTILS: USER & PERMISSIONS
# ==============================

def extract_global_username(message_author: discord.Member | discord.User) -> str:
    """
    Choose a stable identifier for a user:
    - Prefer .name (global username)
    - Fallback to .display_name
    Always lowercase.
    """
    try:
        name = getattr(message_author, "name", "") or ""
    except Exception:
        name = ""
    try:
        display = getattr(message_author, "display_name", "") or ""
    except Exception:
        display = ""
    candidate = name or display
    return str(candidate).lower()


def is_priority_owner(message: discord.Message) -> bool:
    """True if author is the hardcoded PRIORITY_OWNER (e.g. 'yoruboku')."""
    uname = extract_global_username(message.author)
    return uname == PRIORITY_OWNER


def is_configured_owner(message: discord.Message) -> bool:
    """True if author's global username is in the configured owner list."""
    uname = extract_global_username(message.author)
    return uname in owner_usernames


def is_admin(message: discord.Message) -> bool:
    """
    True if the author has Administrator permissions in the guild.
    Returns False for DMs or when guild is unavailable.
    """
    try:
        if isinstance(message.channel, discord.abc.GuildChannel):
            member = message.guild.get_member(message.author.id)
            if member:
                return member.guild_permissions.administrator
    except Exception:
        pass
    return False


# ==============================
# PLAYWRIGHT / GEMINI
# ==============================

async def ensure_browser() -> None:
    """Start Playwright and persistent Chromium context if not already running."""
    global playwright_instance, browser_context

    if playwright_instance and browser_context:
        return

    playwright_instance = await async_playwright().start()
    browser_context = await playwright_instance.chromium.launch_persistent_context(
        user_data_dir="playwright_data",
        headless=True,
    )


async def get_user_page(user_id: int):
    """Return a per-user Gemini page; recreate if dead."""
    await ensure_browser()

    page = user_pages.get(user_id)
    if page:
        # Check if page is still alive
        try:
            await page.title()
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
    try:
        await page.wait_for_selector(INPUT_SELECTOR, timeout=FIRST_RESPONSE_TIMEOUT)
    except PlaywrightTimeout:
        await page.close()
        raise RuntimeError("Gemini input not found. Are you logged in? Re-run installer.")
    user_pages[user_id] = page
    return page


async def ask_gemini(page, question: str) -> str:
    """
    Send question to Gemini and return full answer text.

    Behavior (unchanged from your original logic):
    - Waits for initial response.
    - Waits until Stop button disappears (stream finished).
    - Waits for a new markdown block.
    - Polls until the answer text stops changing STABLE_REQUIRED times.
    - Detects common error states (rate limit, 'Try again', etc.).
    - If the question contains 'suggest' + 'video', append YouTube search link.
    """

    # Count existing answers
    previous_answers = await page.query_selector_all(RESPONSE_SELECTOR)
    prev_count = len(previous_answers)

    # Send question
    await page.click(INPUT_SELECTOR)
    await page.fill(INPUT_SELECTOR, question)
    await page.keyboard.press("Enter")

    # Wait for first answer to show up
    try:
        await page.wait_for_selector(RESPONSE_SELECTOR, timeout=FIRST_RESPONSE_TIMEOUT)
    except PlaywrightTimeout:
        return "Gemini did not respond in time. Possibly rate-limited."

    # Wait for Stop button to disappear (Gemini done streaming)
    while True:
        stop_btn = await page.query_selector("button[aria-label='Stop']")
        if not stop_btn:
            break
        await asyncio.sleep(POLL_INTERVAL)

    # Wait until a new markdown answer appears
    while True:
        answers = await page.query_selector_all(RESPONSE_SELECTOR)
        if len(answers) > prev_count:
            new_el = answers[-1]
            break
        await asyncio.sleep(POLL_INTERVAL)

    # Wait until that answer's text stabilizes
    previous_text = ""
    stable = 0
    while True:
        try:
            current_text = await new_el.inner_text()
        except Exception:
            # If the element went stale, fetch last one again
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

    # Error / rate limit detection
    if await page.query_selector("button:has-text('Try again')"):
        return "Gemini shows a 'Try again' button. Probably rate-limited."
    if await page.query_selector("text=limit") or await page.query_selector("text=usage limit"):
        return "Gemini usage limit reached."
    if await page.query_selector("text=Something went wrong"):
        return "Gemini had an internal error."

    # Final answer text
    answers = await page.query_selector_all(RESPONSE_SELECTOR)
    answer_text = await answers[-1].inner_text()

    # Video suggestion detection (unchanged)
    if "suggest" in question.lower() and "video" in question.lower():
        yt = "https://www.youtube.com/results?search_query=" + question.replace(" ", "+")
        answer_text += f"\n\n🔗 **Suggested video:** {yt}"

    return answer_text


# ==============================
# WORKER
# ==============================

async def worker():
    """
    Queue worker:
    - Pulls items from task_queue
    - Handles owner lock
    - Calls ask_gemini
    - Sends answer in chunks
    """
    global stop_flag, owner_lock, owner_active_task, owner_being_served_username

    while True:
        user_id, question, channel, thinking_msg, author_username = await task_queue.get()

        # If a global stop has been triggered, drop this task
        if stop_flag:
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            task_queue.task_done()
            continue

        current_task = asyncio.current_task()
        running_tasks.add(current_task)

        # Owner lock: if this task belongs to a priority/configured owner, lock
        served_user_is_priority = (author_username == PRIORITY_OWNER)
        served_user_is_config_owner = (author_username in owner_usernames)

        if served_user_is_priority or served_user_is_config_owner:
            owner_lock = True
            owner_active_task = current_task
            owner_being_served_username = author_username

        try:
            page = await get_user_page(user_id)
            answer = await ask_gemini(page, question)

            if not stop_flag:
                # Remove "Thinking..." message
                try:
                    await thinking_msg.delete()
                except Exception:
                    pass

                # Chunk long responses
                if isinstance(answer, str) and len(answer) > 1900:
                    for i in range(0, len(answer), 1800):
                        await channel.send(answer[i:i+1800])
                else:
                    await channel.send(answer)

        except Exception as e:
            if not stop_flag:
                try:
                    await thinking_msg.delete()
                except Exception:
                    pass
                await channel.send(f"Error: {e}")

        finally:
            # Release owner lock if this was the active owner's task
            if current_task == owner_active_task:
                owner_lock = False
                owner_active_task = None
                owner_being_served_username = None

            running_tasks.discard(current_task)
            task_queue.task_done()


# ==============================
# DISCORD EVENTS
# ==============================

@client.event
async def on_ready():
    print(f"VITO is online as {client.user}")
    asyncio.create_task(start_playwright())
    asyncio.create_task(worker())


@client.event
async def on_message(message: discord.Message):
    global stop_flag, owner_lock

    # Ignore own messages
    if message.author == client.user:
        return

    # Only respond when mentioned
    if f"<@{BOT_ID}>" not in message.content:
        return

    # Extract the content AFTER the mention
    content_raw = message.content.split(">", 1)[1].strip()
    content = content_raw.strip()
    content_lc = content.lower()
    author_uname = extract_global_username(message.author)  # lowercase

    # Priority owner path:
    # If the author is PRIORITY_OWNER, clear queue + cancel tasks + reload pages,
    # then continue to handle their message normally.
    if is_priority_owner(message):
        stop_flag = True

        # Clear queue
        while not task_queue.empty():
            try:
                task_queue.get_nowait()
                task_queue.task_done()
            except Exception:
                pass

        # Cancel running tasks
        for t in list(running_tasks):
            try:
                t.cancel()
            except Exception:
                pass

        # Soft reload pages to cancel current Gemini generations
        for p in list(user_pages.values()):
            try:
                await p.reload()
            except Exception:
                pass

        stop_flag = False  # allow new tasks now

    # STOP command
    if "stop" in content_lc:
        # If owner lock is active and this is NOT the priority owner
        if owner_lock and not is_priority_owner(message):
            # Only the currently-served owner can interrupt themselves during owner_lock
            if not (is_configured_owner(message) and author_uname == owner_being_served_username):
                await message.channel.send("⛔ VITO is currently answering a protected owner. Stop ignored.")
                return

        caller_is_admin = is_admin(message)
        caller_is_owner = is_configured_owner(message) or is_priority_owner(message)

        if caller_is_admin or caller_is_owner:
            # Perform global stop
            stop_flag = True

            # Clear queued tasks
            while not task_queue.empty():
                try:
                    task_queue.get_nowait()
                    task_queue.task_done()
                except Exception:
                    pass

            # Cancel running tasks
            for t in list(running_tasks):
                try:
                    t.cancel()
                except Exception:
                    pass

            # Reload pages to interrupt Gemini
            for p in list(user_pages.values()):
                try:
                    await p.reload()
                except Exception:
                    pass

            await message.channel.send("🛑 All tasks stopped.")
            stop_flag = False
            return
        else:
            await message.channel.send("⛔ You don't have permission to stop ongoing tasks.")
            return

    # NEWCHAT command
    if content_lc.startswith("newchat"):
        # Drop user's page for a clean conversation
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

        thinking_msg = await message.channel.send("🧠 Starting a fresh chat...")
        await task_queue.put((message.author.id, question, message.channel, thinking_msg, author_uname))
        return

    # Normal question path
    thinking_msg = await message.channel.send("🧠 Thinking…")
    await task_queue.put((message.author.id, content_raw, message.channel, thinking_msg, author_uname))


# ==============================
# PLAYWRIGHT LOOP
# ==============================

async def start_playwright():
    """Keep Playwright context alive in the background."""
    await ensure_browser()
    while True:
        await asyncio.sleep(1)


# ==============================
# ENTRY POINT
# ==============================

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
