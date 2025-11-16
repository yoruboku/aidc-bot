# 🌌 Discord AI Web Bot

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-1.44.0-brightgreen.svg)](https://playwright.dev/)
[![License](https://img.shields.io/badge/license-MIT-red.svg)](LICENSE)
[![Discord](https://img.shields.io/discord/your-server-id?color=7289DA\&label=Discord)]()

---

![Logo](vito.png)

## ✨ Overview

**Vito** is a sleek self-hosted Discord AI bot powered by **Google Gemini** via Playwright.
It intelligently answers questions in your server when mentioned, supports **per-user sessions**, **new chat commands**, and **rate-limit management**.

> ⚠️ Gemini's UI may change over time, potentially breaking functionality. Use responsibly.

---

## 💡 Features

* 🚀 **Mention-Based:** Responds only when mentioned
* 🧩 **Per-User Sessions:** Independent, persistent chats per user
* 🔄 **New Chat Commands:** Reset conversation context easily
* 📝 **Queued Requests:** Prevents browser conflicts and rate-limit issues
* 🔐 **Persistent Login:** Saves your Gemini session for hassle-free logins
* ⚠️ **Error Handling:** Detects rate limits and retry prompts
* 💻 **Cross-Platform Installer:** Automated setup for Linux, macOS and windows.

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
git clone https://github.com/yoruboku/vito-bot.git
cd vito-bot
```

### 2️⃣ Run the Installer

#### Linux / macOS

```bash
chmod +x unified_install.sh
./install.sh
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
@Vito What is the capital of Japan?
```

**Start a New Chat:**

```
@Vito newchat
```

**New Chat with Prompt:**

```
@Vito newchat Tell me a story about a robot.
```

---

## 🖼 Visual Workflow

```
Discord Mention --> Bot Queue --> Playwright Browser --> Gemini UI Interaction --> Response Scraped --> Discord Channel Reply
```

---

## 📄 License

MIT License © 2025 YoruBoku
Contact: [omenboku@gmail.com](mailto:omenboku@gmail.com)

---

Made by Python using YoruBoku.
