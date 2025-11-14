# ![BOKU AIDC](logo.svg) BOKU AIDC - Discord AI Bot

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-1.44.0-brightgreen.svg)](https://playwright.dev/)
[![License](https://img.shields.io/badge/license-MIT-red.svg)](LICENSE)

---

## Overview

BOKU AIDC is a Discord AI bot powered by Google Gemini (via Playwright).  
It automatically answers questions in your server when mentioned (`@zom`) and supports **new chat sessions**, **user-based context**, and **rate limit detection**.

> ⚠️ Gemini UI may change over time, which could break the bot. Use responsibly and follow all legal terms.

---

## Features

- Responds only when mentioned (`@zom`)
- Supports `/newchat` style commands per user
- Queued requests to avoid browser race conditions
- Automatic Gemini login session persistence
- Error handling for rate limits
- Styled installer with automated setup

---

## Requirements

- Python 3.11+
- Discord Bot Token & Application ID
- Git
- Internet access for Gemini login

---

## Installation (All OS)

### 1. Clone the repo

```bash
git clone https://github.com/yoruboku/aidc-bot.git
cd aidc-bot
