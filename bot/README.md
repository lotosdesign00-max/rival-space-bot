# Rival Space Telegram Bot

Python bot for the Rival Space ecosystem: menu, profile, balance, CryptoBot deposits, order wizard, order history, and WebApp launch button.

## Local Start On Windows

```powershell
cd C:\Users\igors\Desktop\rivaldesign-app-main\bot

# Create virtual environment once
py -m venv .venv

# Install dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Create .env if it does not exist yet
Copy-Item .env.example .env

# Fill .env with real values, then run
.\.venv\Scripts\python.exe main.py
```

To stop the bot after running it in terminal, press `Ctrl+C`.

## Railway Deploy

Recommended setup: create a separate Railway service from the same GitHub repository and set the service root directory to `bot`.

Railway reads `bot/railway.json` and starts the worker with:

```bash
python main.py
```

Python is pinned with `.python-version` / `runtime.txt` to `3.12.0` to avoid package build issues on newer Python versions.

### Railway Variables

Add these in Railway service `Variables`. Do not commit real values to GitHub.

```env
TELEGRAM_BOT_TOKEN=
PUBLIC_BOT_USERNAME=rivaldesign_bot
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SUPABASE_SECRET_KEY=
CRYPTOPAY_API_TOKEN=
CRYPTOPAY_ASSET=USDT
WEBAPP_URL=
WELCOME_VIDEO_ID=
WELCOME_VIDEO_PATH=assets/welcome.mp4
```

### Expected Logs

After deploy, Railway logs should show:

```text
Rival Design Bot started
Start polling
Run polling for bot @rivaldesign_bot
```

Run only one polling instance for the same Telegram bot token. If Railway is running the bot, stop the local terminal version.

## Checks

```powershell
# Safe import check, does not start polling
.\.venv\Scripts\python.exe -c "import main; print('bot import ok')"

# Compile check
.\.venv\Scripts\python.exe -m py_compile main.py database.py kb.py
```

## Required Env Variables

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather. |
| `PUBLIC_BOT_USERNAME` | Username shown in the welcome/profile text. |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_SERVICE_KEY` | Supabase service role key for server-side bot operations. |
| `CRYPTOPAY_API_TOKEN` | CryptoPay API token from CryptoBot. |
| `CRYPTOPAY_ASSET` | Payment asset, usually `USDT`. |
| `WEBAPP_URL` | Public Vercel URL of the Rival Space Mini App. |
| `WELCOME_VIDEO_ID` | Optional Telegram video `file_id` for the welcome message. |
| `WELCOME_VIDEO_PATH` | Local fallback video path bundled with the bot. |
