"""Связь бота с приложением Rival Space (одна база на двоих).

Бот больше не хранит баланс и заказы у себя — всё берётся из приложения
через внутренний API: POST {APP_URL}/api/bot с заголовком x-bot-secret.

Переменные окружения (Render):
  APP_URL         — адрес приложения, например https://rival-space.vercel.app
  BOT_API_SECRET  — любой длинный пароль; ТОТ ЖЕ самый задаётся в Vercel
"""
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

logger = logging.getLogger(__name__)

APP_URL = (os.getenv("APP_URL") or os.getenv("WEBAPP_URL") or "https://rival-space.vercel.app").strip().rstrip("/")
BOT_API_SECRET = os.getenv("BOT_API_SECRET", "").strip()


class AppApiError(RuntimeError):
    pass


def tg_payload(user) -> dict:
    """Telegram-пользователь в том виде, в каком его ждёт приложение."""
    return {
        "id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name,
        "username": user.username,
    }


class AppApi:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(BOT_API_SECRET)

    async def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=APP_URL,
                timeout=httpx.Timeout(25, connect=10),
                headers={"x-bot-secret": BOT_API_SECRET, "Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def call(self, action: str, user, **extra) -> dict:
        if not self.enabled:
            raise AppApiError("BOT_API_SECRET не задан в окружении бота")
        client = await self.client()
        try:
            r = await client.post("/api/bot", json={"action": action, "user": tg_payload(user), **extra})
        except httpx.HTTPError as exc:
            raise AppApiError(f"приложение недоступно: {exc}") from exc
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            raise AppApiError(f"{r.status_code}: {data.get('error') or r.text[:200]}")
        return data

    # --- удобные обёртки
    async def start(self, user, ref: str | None = None) -> dict:
        return await self.call("start", user, **({"ref": ref} if ref else {}))

    async def profile(self, user) -> dict:
        return await self.call("profile", user)

    async def credit(self, user, amount_usd: float, reference: str) -> dict:
        return await self.call("credit", user, amountUsd=amount_usd, reference=reference)

    async def stars(self, user, payload: str) -> dict:
        return await self.call("stars", user, payload=payload)


app_api = AppApi()
