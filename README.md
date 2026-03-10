# 🤖 Samira Chat Bot

> **A savage, AI-powered Telegram chat bot with a Delhi girl personality — built using Python, python-telegram-bot, and OpenRouter API.**

**Developed by [@MrLuffy12377](https://t.me/MrLuffy12377) (D Luffy)**

---

## ✨ Features

- 🧠 **AI-Powered Chat** — Uses OpenRouter API (LLaMA 3.1 70B) for intelligent, personality-driven responses
- 💅 **Savage Delhi Girl Persona** — Responds with attitude, humor, and short savage replies
- 🔥 **Fun Commands** — Roast, shayari, couple predictions, truth/dare, flirt, dice, and more
- 🛡️ **Group Moderation** — Ban, mute, warn users, auto-delete links, admin list
- 💌 **Anonymous Messages** — Crush and confession features for groups
- 👋 **Smart Welcome** — AI-generated welcome messages for new members
- 🚫 **Spam Prevention** — Rate limiting, repeated message detection, cooldowns
- 🔗 **Link Detection** — Auto-delete links with warnings and auto-ban
- 💬 **Continuous Chat** — Remembers conversation history per chat
- 🌐 **Webhook & Polling** — Supports both Render deployment (webhook) and local polling

---

## 🎯 Commands

### Fun Commands
| Command | Description |
|---------|-------------|
| `/troast` or `/r` | Savage roast 🔥 |
| `/shayari` or `/s` | Romantic shayari 💕 |
| `/couple` or `/c` | Couple prediction 💑 |
| `/crush {msg}` | Anonymous crush message 💌 |
| `/confess {msg}` | Anonymous confession 🤫 |
| `/flirt` | Flirty one-liners 😏 |
| `/truth` or `/t` | Truth question 🤔 |
| `/dare` or `/d` | Dare challenge 😈 |
| `/dice` | Roll the dice 🎲 |
| `/choose` | Let Samira choose for you 🎯 |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/ban` | Ban a user 🔨 |
| `/mute` | Mute a user 🤐 |
| `/warn` or `/w` | Warn a user ⚠️ |
| `/adminlist` | List group admins 👑 |
| `/send {msg}` | Send message as bot reply 📝 |
| `/checklink on/off` | Toggle link checking 🔗 |
| `/welcome on/off` | Toggle auto-welcome 👋 |

### Utility Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot 🚀 |
| `/stop` | Stop the bot 🛑 |
| `/ping` or `/alive` | Check bot status 🤖 |
| `/dev` | Developer info 👨‍💻 |
| `/help` or `/h` | Full command list 📖 |

---

## 🚀 Deployment on Render

This bot is designed to run as a **Web Service on Render**.

### 1. Fork / Clone this repo

```bash
git clone https://github.com/MrLuffy12377/Samira-Chat-bot.git
cd Samira-Chat-bot
```

### 2. Set up environment variables

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

**Required variables:**

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `OPENROUTER_API_KEYS` | Comma-separated API keys from [OpenRouter](https://openrouter.ai) |
| `OWNER_ID` | Your Telegram user ID |

See [`.env.example`](.env.example) for all available variables.

### 3. Deploy on Render

1. Create a new **Web Service** on [Render](https://render.com)
2. Connect your GitHub repository
3. Set the following:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
4. Add all environment variables from `.env.example` in the Render dashboard
5. Make sure to set `RENDER_EXTERNAL_HOSTNAME` (Render auto-sets this)

### 4. Run locally (optional)

```bash
pip install -r requirements.txt
python bot.py
```

> When no `RENDER_EXTERNAL_HOSTNAME` is set, the bot automatically uses polling mode instead of webhooks.

---

## 📁 Project Structure

```
├── bot.py              # Main bot file with all handlers and commands
├── chat_module.py      # Chat module with AI response generation
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

---

## 🔑 Getting OpenRouter API Keys

1. Go to [openrouter.ai](https://openrouter.ai)
2. Create an account and generate API keys
3. Add them as comma-separated values in `OPENROUTER_API_KEYS`
4. The bot supports multiple keys with automatic rotation and rate limit handling

---

## 📝 License

This project is open source. Feel free to fork and modify.

---

## 👨‍💻 Developer

**Developed by D Luffy ([@MrLuffy12377](https://t.me/MrLuffy12377))**

- Telegram: [@MrLuffy12377](https://t.me/MrLuffy12377)
- GitHub: [@MrLuffy12377](https://github.com/MrLuffy12377)

> Use `/dev` command in the bot to get developer contact info.

---

*Made with ❤️ by D Luffy*
