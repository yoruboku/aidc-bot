# ![BOKU AIDC](logo.svg) BOKU AIDC - Discord AI Bot

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-1.44.0-brightgreen.svg)](https://playwright.dev/)
[![License](https://img.shields.io/badge/license-MIT-red.svg)](LICENSE)
[![Discord](https://img.shields.io/discord/your-server-id?color=7289DA\&label=Discord)]()

---

## ✨ Overview

**BOKU AIDC** is a sleek self-hosted Discord AI bot powered by **Google Gemini** via Playwright.
It intelligently answers questions in your server when mentioned (`@zom`), supports **per-user sessions**, **new chat commands**, and **rate-limit management**.

> ⚠️ Gemini's UI may change over time, potentially breaking functionality. Use responsibly.

---

## 💡 Features

* 🚀 **Mention-Based:** Responds only when mentioned (`@zom`)
* 🧩 **Per-User Sessions:** Independent, persistent chats per user
* 🔄 **New Chat Commands:** `/newchat` to reset conversation context
* 📝 **Queued Requests:** Prevents browser conflicts and rate-limit issues
* 🔐 **Persistent Login:** Saves your Gemini session for hassle-free logins
* ⚠️ **Error Handling:** Detects rate limits and retry prompts
* 💻 **Cross-Platform Installer:** Automated setup for Linux, macOS, Windows, and Termux

---

## 🛠 Requirements

* Python 3.11+
* Discord Bot Token & Application ID
* Git
* Internet access for Gemini login

---

## 🚀 Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yoruboku/aidc-bot.git
cd aidc-bot
```

### 2️⃣ Run the Installer

#### Linux / macOS / Termux

```bash
chmod +x unified_install.sh
./unified_install.sh
```

#### Windows (PowerShell)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\install.ps1
```

**Installer Workflow:**

* Creates Python virtual environment
* Installs dependencies from `requirements.txt`
* Prompts for Discord token & bot ID
* Launches Chromium for Gemini login
* Saves session and starts the bot automatically

> Subsequent runs skip installation and launch the bot directly.

---

## 🔄 Updating

#### Linux/macOS/Termux

```bash
./update.sh
```

#### Windows

```powershell
..\update.ps1
```

> Updates code, dependencies, and restarts the bot.

---

## ⚡ Running the Bot Manually

#### Linux/macOS

```bash
source venv/bin/activate
python3 zom_bot.py
```

#### Windows (PowerShell)

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1
# Run bot
python.exe zom_bot.py
```

---

## 📝 Discord Developer Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Enable **Message Content Intent** under Privileged Gateway Intents
4. Set scopes: `bot`, `applications.commands`
5. Set permissions: Send Messages, Read Message History, View Channels
6. Copy your **Bot Token** and **Application ID** into the installer

---

## 💬 Usage Examples

**Ask a Question:**

```
@zom What is the capital of Japan?
```

**Start a New Chat:**

```
@zom newchat
```

**New Chat with Prompt:**

```
@zom newchat Tell me a story about a robot.
```

---

## 🖼 Visual Workflow

```
Discord Mention --> Bot Queue --> Playwright Browser --> Gemini UI Interaction --> Response Scraped --> Discord Channel Reply
```

---

## 📄 License

MIT License © 2025 Yoruboku
Contact: [omenboku@gmail.com](mailto:omenboku@gmail.com)

---

Made with ❤️ and Python by **BOKU**
