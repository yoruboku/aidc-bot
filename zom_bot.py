import discord
import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ID = os.getenv("BOT_ID")  # Bot Application ID

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

browser_context = None
user_pages = {}
task_queue = asyncio.Queue()

INPUT_SELECTOR = "div[contenteditable='true']"
RESPONSE_SELECTOR = "div.markdown"

# ---------------------------------------------
# Initialize Playwright browser
# ---------------------------------------------
async def init_browser(playwright):
    global browser_context

    browser_context = await playwright.chromium.launch_persistent_context(
        "playwright_data",
        headless=True
    )

# ---------------------------------------------
# User-specific page (each person gets a chat)
# ---------------------------------------------
async def get_user_page(user_id):
    if user_id in user_pages:
        return user_pages[user_id]

    page = await browser_context.new_page()
    await page.goto("https://gemini.google.com/")
    await page.wait_for_selector(INPUT_SELECTOR, timeout=60000)

    user_pages[user_id] = page
    return page

# ---------------------------------------------
# Reset a user's chat
# ---------------------------------------------
async def new_chat_for_user(user_id):
    if user_id in user_pages:
        try:
            await user_pages[user_id].close()
        except:
            pass
        del user_pages[user_id]

# ---------------------------------------------
# Ask Gemini
# ---------------------------------------------
async def ask_gemini(page, question):
    await page.click(INPUT_SELECTOR)
    await page.fill(INPUT_SELECTOR, question)
    await page.keyboard.press("Enter")

    try:
        await page.wait_for_selector(RESPONSE_SELECTOR, timeout=60000)
    except PlaywrightTimeout:
        return "Gemini did not respond in time."

    try_again = await page.query_selector("button:has-text('Try again')")
    limit = await page.query_selector("text=limit")
    error_box = await page.query_selector("text=Something went wrong")

    if try_again:
        return "Gemini shows 'Try again'. Probably rate-limited."

    if limit:
        return "Gemini usage limit reached."

    if error_box:
        return "Gemini encountered an error."

    answers = await page.query_selector_all(RESPONSE_SELECTOR)
    return await answers[-1].inner_text()

# ---------------------------------------------
# Queue Worker
# ---------------------------------------------
async def worker():
    while True:
        user_id, question, channel, thinking_message = await task_queue.get()
        try:
            page = await get_user_page(user_id)
            answer = await ask_gemini(page, question)
            await thinking_message.delete()
            await channel.send(answer)
        except Exception as e:
            await thinking_message.delete()
            await channel.send(f"Error: {e}")
        finally:
            task_queue.task_done()

# ---------------------------------------------
# Discord Events
# ---------------------------------------------
@client.event
async def on_ready():
    print(f"Bot logged in as {client.user}")
    asyncio.create_task(start_playwright())
    asyncio.create_task(worker())

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()

    if not f"<@{BOT_ID}>" in content:
        return

    text = content.split(">", 1)[1].strip()

    # NEWCHAT COMMAND
    if text.lower().startswith("newchat"):
        await new_chat_for_user(message.author.id)
        question = text.replace("newchat", "", 1).strip()

        if question == "":
            await message.channel.send("New chat created. Ask something now.")
            return

        thinking = await message.channel.send("🧠 Thinking…")
        await task_queue.put((
            message.author.id, question, message.channel, thinking
        ))
        return

    # Normal question
    thinking = await message.channel.send("🧠 Thinking…")
    await task_queue.put((
        message.author.id, text, message.channel, thinking
    ))

# ---------------------------------------------
# Start Playwright
# ---------------------------------------------
async def start_playwright():
    async with async_playwright() as pw:
        await init_browser(pw)
        while True:
            await asyncio.sleep(1)

# ---------------------------------------------
# Launch
# ---------------------------------------------
client.run(DISCORD_TOKEN)
