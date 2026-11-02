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

## Render Deploy

`render.yaml` в корне репозитория уже всё настраивает.

1. Render → **New → Blueprint** → выбери репозиторий → **Apply**.
   (Или вручную: **New → Web Service**, Root Directory `bot`, Build `pip install -r requirements.txt`, Start `python main.py`, Health Check Path `/health`, переменная `PYTHON_VERSION=3.12.8`.)
2. Заполни переменные: `TELEGRAM_BOT_TOKEN`, `CRYPTOPAY_API_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ADMIN_TELEGRAM_ID`, `WEBAPP_URL`.
3. Дождись деплоя. Бот сам ставит вебхук на `https://<сервис>.onrender.com/webhook` — вручную ничего открывать не нужно.

Ожидаемый лог:

```text
Rival Design Bot started: webhook mode for @rivaldesign_bot -> https://....onrender.com/webhook
```

Режим выбирается сам: если есть `RENDER_EXTERNAL_URL` (Render ставит его автоматически) или `WEBHOOK_URL` — вебхук, иначе polling.

> Не запускай бота локально, пока он работает на Render: локальный запуск (polling) снимает вебхук. После локального теста нажми на Render **Manual Deploy → Restart service**.

> Бесплатный план засыпает после 15 минут без запросов. Первое сообщение после сна обрабатывается ~30–60 сек. Чтобы не засыпал — пингуй `https://<сервис>.onrender.com/health` раз в 10 минут (UptimeRobot / cron-job.org) или перейди на Starter.

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
