"""Database operations with Supabase REST API."""
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from secrets import randbelow
from typing import Any

import httpx
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Keep database usable when imported directly from tests or scripts.
load_dotenv(Path(__file__).with_name(".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_SECRET_KEY", ""))

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is not set in bot/.env")
if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY is not set in bot/.env")


class Database:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{SUPABASE_URL}/rest/v1",
                timeout=20,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    @asynccontextmanager
    async def session(self):
        client = await self.get_client()
        yield client

    async def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        prefer: str | None = None,
    ) -> Any:
        client = await self.get_client()
        headers = {"Prefer": prefer} if prefer else None
        response = await client.request(method, f"/{table}", params=params, json=json, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Supabase {method} /{table} failed: "
                f"{response.status_code} {response.text}"
            ) from exc
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def _select(self, table: str, params: dict[str, Any]) -> list[dict]:
        data = await self._request("GET", table, params=params)
        return data if isinstance(data, list) else []

    async def _insert(self, table: str, payload: dict) -> dict | None:
        data = await self._request("POST", table, json=payload, prefer="return=representation")
        return data[0] if data else None

    async def _update(self, table: str, filters: dict[str, str], payload: dict) -> list[dict]:
        params = {"select": "*", **filters}
        data = await self._request(
            "PATCH",
            table,
            params=params,
            json=payload,
            prefer="return=representation",
        )
        return data if isinstance(data, list) else []

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        photo_url: str | None = None,
    ) -> dict | None:
        """Get existing user or create new one."""
        existing = await self._select(
            "users",
            {"select": "*", "telegram_id": f"eq.{telegram_id}", "limit": "1"},
        )
        if existing:
            return existing[0]

        # The current Supabase schema does not include photo_url, so keep the
        # bot compatible with the live table instead of failing first orders.
        return await self._insert(
            "users",
            {
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "balance": "0.00",
            },
        )

    async def get_user(self, telegram_id: int) -> dict | None:
        """Get user by telegram ID."""
        users = await self._select(
            "users",
            {"select": "*", "telegram_id": f"eq.{telegram_id}", "limit": "1"},
        )
        return users[0] if users else None

    async def get_user_balance(self, telegram_id: int) -> Decimal:
        """Get user's balance."""
        user = await self.get_user(telegram_id)
        return Decimal(str(user["balance"])) if user else Decimal("0.00")

    async def get_user_orders_count(self, telegram_id: int) -> int:
        """Count user's completed orders."""
        user = await self.get_user(telegram_id)
        if not user:
            return 0

        delivered = await self._select(
            "orders",
            {"select": "id", "user_id": f"eq.{user['id']}", "status": "eq.delivered"},
        )
        closed = await self._select(
            "orders",
            {"select": "id", "user_id": f"eq.{user['id']}", "status": "eq.closed"},
        )
        return len(delivered) + len(closed)

    async def get_user_orders(self, telegram_id: int) -> list[dict]:
        """Get user's order history."""
        user = await self.get_user(telegram_id)
        if not user:
            return []

        return await self.get_user_orders_for_user_id(user["id"])

    async def get_user_orders_for_user_id(self, user_id: str) -> list[dict]:
        """Get user's order history by internal Supabase user id."""
        return await self._select(
            "orders",
            {
                "select": "*",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
            },
        )

    async def get_order(self, order_id: str) -> dict | None:
        """Get one order by ID."""
        orders = await self._select("orders", {"select": "*", "id": f"eq.{order_id}", "limit": "1"})
        return orders[0] if orders else None

    async def update_balance(self, telegram_id: int, amount: Decimal) -> bool:
        """Add amount to user's balance."""
        user = await self.get_user(telegram_id)
        if not user:
            return False

        current_balance = Decimal(str(user.get("balance") or "0.00"))
        new_balance = current_balance + amount
        updated = await self._update(
            "users",
            {"id": f"eq.{user['id']}"},
            {"balance": str(new_balance)},
        )
        return bool(updated)

    async def create_payment(
        self,
        user_id: str,
        amount: Decimal,
        invoice_id: str | None = None,
        pay_url: str | None = None,
        currency: str = "USD",
    ) -> dict | None:
        """Create a pending payment record."""
        return await self._insert(
            "payments",
            {
                "user_id": user_id,
                "amount": str(amount),
                "currency": currency,
                "status": "pending",
                "crypto_invoice_id": invoice_id,
                "crypto_pay_url": pay_url,
                "payment_method": "cryptobot",
            },
        )

    async def get_payment(self, payment_id: str) -> dict | None:
        """Get payment by ID."""
        payments = await self._select("payments", {"select": "*", "id": f"eq.{payment_id}", "limit": "1"})
        return payments[0] if payments else None

    async def mark_payment_paid(self, payment_id: str) -> bool:
        """Mark payment as paid."""
        updated = await self._update(
            "payments",
            {"id": f"eq.{payment_id}", "status": "eq.pending"},
            {
                "status": "paid",
                "paid_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return bool(updated)

    async def create_order(
        self,
        *,
        user_id: str,
        service_name: str,
        total_amount: Decimal,
        brief: str,
        status: str = "waiting_payment",
        payment_id: str | None = None,
    ) -> dict | None:
        """Create a new design order."""
        order_number = f"RD-{datetime.now(timezone.utc):%Y%m%d}-{randbelow(10000):04d}"
        return await self._insert(
            "orders",
            {
                "order_number": order_number,
                "user_id": user_id,
                "service_name": service_name,
                "total_amount": str(total_amount),
                "status": status,
                "payment_id": payment_id,
                "brief": brief,
            },
        )

    async def update_order(self, order_id: str, payload: dict) -> dict | None:
        """Update an order and return the updated row."""
        payload = {**payload, "updated_at": datetime.now(timezone.utc).isoformat()}
        updated = await self._update("orders", {"id": f"eq.{order_id}"}, payload)
        return updated[0] if updated else None

    async def attach_payment_to_order(self, order_id: str, payment_id: str) -> dict | None:
        """Attach a payment draft to an order."""
        return await self.update_order(order_id, {"payment_id": payment_id})

    async def create_order_message(
        self,
        *,
        order_id: str,
        sender_id: str,
        text: str,
        sender_role: str = "client",
        attachment_url: str | None = None,
    ) -> dict | None:
        """Store a message inside an order chat."""
        return await self._insert(
            "messages",
            {
                "order_id": order_id,
                "sender_id": sender_id,
                "sender_role": sender_role,
                "text": text,
                "attachment_url": attachment_url,
            },
        )

    async def get_services(self) -> list[dict]:
        """Get all active services."""
        return await self._select(
            "services",
            {"select": "*", "is_active": "eq.true", "order": "sort_order.asc"},
        )


db = Database()
