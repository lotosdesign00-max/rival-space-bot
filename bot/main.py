"""Rival Design Telegram Bot - Main entry point."""
import os
import asyncio
import logging
from decimal import Decimal, InvalidOperation
from functools import wraps
from html import escape
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from aiocryptopay import AioCryptoPay
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import FSInputFile, Message
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from database import db
from kb import (
    main_menu_kb,
    profile_kb,
    deposit_kb,
    orders_kb,
    order_category_kb,
    order_step_kb,
    order_style_kb,
    order_deadline_kb,
    order_review_kb,
    order_payment_kb,
    order_crypto_payment_kb,
    back_to_menu_kb,
    payment_kb,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CRYPTOPAY_TOKEN = os.getenv("CRYPTOPAY_API_TOKEN", "").strip()
CRYPTOPAY_ASSET = os.getenv("CRYPTOPAY_ASSET", "USDT").strip().upper()
WELCOME_VIDEO_ID = os.getenv("WELCOME_VIDEO_ID", "").strip()
WELCOME_VIDEO_PATH = os.getenv("WELCOME_VIDEO_PATH", "").strip()
PUBLIC_BOT_USERNAME = os.getenv("PUBLIC_BOT_USERNAME", "rivaldesign_bot").strip().lstrip("@")
ADMIN_TELEGRAM_ID = (
    os.getenv("ADMIN_TELEGRAM_ID")
    or os.getenv("TELEGRAM_ADMIN_ID")
    or os.getenv("ADMIN_ID")
    or os.getenv("DESIGNER_TELEGRAM_ID")
    or ""
).strip()
CACHED_WELCOME_VIDEO_ID: str | None = None

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in bot/.env")
if not CRYPTOPAY_TOKEN:
    raise RuntimeError("CRYPTOPAY_API_TOKEN is not set in bot/.env")

cryptopay: AioCryptoPay | None = None
router = Router()
SESSIONS: dict[int, dict] = {}

ORDER_CATEGORIES = {
    "avatar": "Аватарка",
    "banner_preview": "Баннеры / превью",
    "forum_banner": "Форумный баннер",
    "creatives": "Креативы",
    "infographic": "Инфографика",
    "avatar_animation": "Анимация аватарок",
}

CATEGORY_CALLBACKS = [f"order_{key}" for key in ORDER_CATEGORIES]

ORDER_PRICES_RUB = {
    "avatar": Decimal("1200"),
    "banner_preview": Decimal("1500"),
    "forum_banner": Decimal("1300"),
    "creatives": Decimal("1000"),
    "infographic": Decimal("1200"),
    "avatar_animation": Decimal("1800"),
}

ORDER_STEPS = {
    2: {
        "key": "object",
        "title": "Главный объект",
        "prompt": "Укажите персонажа или объект для визуализации. Опишите детали: внешность, эмоции или конкретную личность.",
        "examples": [
            "Леонардо Ди Каприо (Волк с Уолл-стрит)",
            "Аниме-персонаж",
            "Мужчина в деловом костюме",
        ],
        "skip": False,
    },
    3: {
        "key": "environment",
        "title": "Окружение",
        "prompt": "Опишите локацию или атмосферу заднего плана. Система подберет освещение и глубину резкости на основе ваших данных.",
        "examples": [
            "Офис в стиле мафии (интерьер)",
            "Ночной город, неоновое освещение",
            "Тёмный абстрактный градиент",
        ],
        "skip": False,
    },
    4: {
        "key": "text_layer",
        "title": "Текстовый слой",
        "prompt": "Введите надпись, никнейм или основной заголовок. Если визуал должен быть без текста — используйте кнопку пропуска.",
        "examples": [
            "Название проекта: «Formula»",
            "Игровой никнейм",
            "Пропустить (без текста)",
        ],
        "skip": True,
    },
    5: {
        "key": "details",
        "title": "Атмосферные детали",
        "prompt": "Укажите ключевые предметы для усиления композиции. Они расставят акценты и подчеркнут стиль.",
        "examples": [
            "Пачки денег, золотые часы",
            "Сигара, пистолет",
            "Пропустить",
        ],
        "skip": True,
    },
    6: {
        "key": "colors",
        "title": "Цветовая схема",
        "prompt": "Определите палитру проекта. Рекомендуется использовать не более двух основных цветов для сохранения чистоты стиля.",
        "examples": [
            "Синий и чёрный",
            "Красный и золотой",
            "Фиолетовый и белый",
        ],
        "skip": False,
    },
    7: {
        "key": "concept",
        "title": "Концепция и ракурс",
        "prompt": "Опишите финальное настроение или конкретную сцену. Это поможет правильно выставить свет и выбрать угол обзора.",
        "examples": [
            "Уверенный взгляд в камеру, ракурс снизу",
            "Динамичная сцена, персонаж в движении",
            "Мрачный вайб, акцент на деталях",
        ],
        "skip": False,
    },
}

STYLE_LABELS = {
    "minimalism": "Минимализм",
    "harmony": "Гармония",
    "maximalism": "Максимализм",
}

STATUS_LABELS = {
    "waiting_payment": "Ожидает оплаты",
    "payment_review": "Проверка оплаты",
    "queued": "В очереди",
    "in_progress": "В работе",
    "preview_sent": "Превью отправлено",
    "revision": "На правках",
    "delivered": "Доставлен",
    "closed": "Завершён",
    "canceled": "Отменён",
}

ACTIVE_STATUSES = {"waiting_payment", "payment_review", "queued", "in_progress", "preview_sent", "revision"}


def run_background(coro):
    """Run non-critical async work without blocking Telegram responses."""
    task = asyncio.create_task(coro)

    def on_done(done_task):
        try:
            done_task.result()
        except Exception:
            logger.exception("Background task failed")

    task.add_done_callback(on_done)
    return task


async def ack_callback(callback):
    """Answer callback queries quickly so Telegram removes the button spinner."""
    try:
        await callback.answer()
    except Exception:
        logger.debug("Callback already answered or expired", exc_info=True)


def instant_ack(handler):
    """Decorator for callback handlers that must acknowledge taps immediately."""
    @wraps(handler)
    async def wrapper(callback, *args, **kwargs):
        await ack_callback(callback)
        logger.info(
            "Callback received: data=%s user_id=%s",
            getattr(callback, "data", None),
            getattr(getattr(callback, "from_user", None), "id", None),
        )
        try:
            return await handler(callback, *args, **kwargs)
        except Exception:
            logger.exception("Callback handler failed: data=%s", getattr(callback, "data", None))
            try:
                if callback.message:
                    await callback.message.answer(
                        "Не смог обработать нажатие. Уже записал ошибку в лог, нажми /start и попробуй ещё раз."
                    )
            except Exception:
                logger.exception("Could not send callback fallback message")
            return None

    return wrapper


def get_cryptopay() -> AioCryptoPay:
    """Create CryptoPay client inside an active asyncio loop."""
    global cryptopay
    if cryptopay is None:
        cryptopay = AioCryptoPay(token=CRYPTOPAY_TOKEN)
    return cryptopay


def money(value, symbol: str = "₽") -> str:
    """Format money values without noisy decimals."""
    amount = safe_decimal(value)
    if amount == amount.to_integral():
        return f"{int(amount)}{symbol}"
    return f"{amount:.2f}{symbol}"


def safe_decimal(value, default: str = "0") -> Decimal:
    """Convert nullable database values to Decimal without crashing handlers."""
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def parse_amount(text: str) -> Decimal | None:
    """Parse a user-entered amount."""
    cleaned = text.strip().replace(",", ".").replace("USDT", "").replace("usdt", "").strip()
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0:
        return None
    return amount


def invoice_url(invoice) -> str:
    """Pick the best URL field from aiocryptopay invoice models."""
    return (
        getattr(invoice, "bot_invoice_url", None)
        or getattr(invoice, "mini_app_invoice_url", None)
        or getattr(invoice, "web_app_invoice_url", None)
        or getattr(invoice, "pay_url", None)
        or ""
    )


async def ensure_telegram_user(user) -> dict:
    """Ensure Telegram user exists in database."""
    return await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=getattr(user, "photo_url", None),
    )


async def ensure_user(message: Message) -> dict:
    """Ensure message sender exists in database."""
    return await ensure_telegram_user(message.from_user)


def welcome_text() -> str:
    return (
        "<b>Привет, Rival Design! — твой официальный ассистент.</b>\n\n"
        "Здесь ты можешь оформить заказ, ознакомиться с ценами и посмотреть примеры работ — "
        "всё в одном месте, быстро и без лишних действий.\n\n"
        "<b>Процесс простой и прозрачный:</b>\n"
        "заполняешь ТЗ → подтверждаешь заказ → получаешь готовый результат в срок.\n\n"
        "<b>С чего начнём?</b>\n\n"
        f"<i>Официальный бот @{PUBLIC_BOT_USERNAME}</i>"
    )


async def send_main_menu(message: Message):
    """Send the reference-style welcome message with optional video."""
    global CACHED_WELCOME_VIDEO_ID
    text = welcome_text()
    video = None

    cache_path = Path(__file__).parent / "assets" / "welcome_video_id.txt"
    if CACHED_WELCOME_VIDEO_ID:
        video = CACHED_WELCOME_VIDEO_ID
    elif WELCOME_VIDEO_ID:
        video = WELCOME_VIDEO_ID
    elif cache_path.exists():
        cached = cache_path.read_text(encoding="utf-8").strip()
        if cached:
            CACHED_WELCOME_VIDEO_ID = cached
            video = cached
    elif WELCOME_VIDEO_PATH:
        video_path = Path(WELCOME_VIDEO_PATH)
        if not video_path.is_absolute():
            video_path = Path(__file__).parent / WELCOME_VIDEO_PATH
        if video_path.exists():
            video = FSInputFile(video_path)
        else:
            logger.warning("Welcome video path does not exist: %s", video_path)

    if video:
        sent = await message.answer_video(
            video=video,
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(),
        )
        if isinstance(video, FSInputFile) and sent.video:
            CACHED_WELCOME_VIDEO_ID = sent.video.file_id
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(sent.video.file_id, encoding="utf-8")
            except OSError as exc:
                logger.warning("Could not cache welcome video file_id: %s", exc)
            logger.info("Cached Telegram welcome video file_id. Add this to Railway as WELCOME_VIDEO_ID=%s", sent.video.file_id)
        return

    await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


def get_order_session(user_id: int) -> dict | None:
    session = SESSIONS.get(user_id)
    if not session or session.get("mode") != "order":
        return None
    return session


def reset_order_session(user_id: int, category_code: str):
    SESSIONS[user_id] = {
        "mode": "order",
        "category": category_code,
        "step": 2,
        "answers": {},
    }


def step_text(step_number: int, category_code: str) -> str:
    if step_number == 8:
        return (
            "<b>Спецификация заказа</b>\n"
            "Шаг 8 / 8 | Визуальный стиль\n\n"
            "Выберите направление, в котором будет реализован проект. "
            "Система адаптирует все предыдущие параметры под выбранную стилистику."
        )

    step = ORDER_STEPS[step_number]
    examples = "\n".join(f"• {escape(item)}" for item in step["examples"])
    return (
        "<b>Спецификация заказа</b>\n"
        f"Шаг {step_number} / 8 | {step['title']}\n\n"
        f"{step['prompt']}\n\n"
        f"{examples}"
    )


async def send_order_step(message: Message, user_id: int):
    session = get_order_session(user_id)
    if not session:
        await send_main_menu(message)
        return

    step_number = session["step"]
    if step_number == 8:
        await message.answer(step_text(8, session["category"]), parse_mode=ParseMode.HTML, reply_markup=order_style_kb())
        return

    step = ORDER_STEPS[step_number]
    await message.answer(
        step_text(step_number, session["category"]),
        parse_mode=ParseMode.HTML,
        reply_markup=order_step_kb(allow_skip=step["skip"], allow_back=step_number > 2),
    )


def build_review_text(session: dict) -> str:
    category_code = session["category"]
    answers = session["answers"]
    category_name = ORDER_CATEGORIES.get(category_code, "Заказ")
    price = ORDER_PRICES_RUB.get(category_code, Decimal("1200"))

    lines = [
        "<b>Проверка конфигурации ТЗ</b>",
        "",
        "Проверьте внесенные данные. Если всё верно — подтвердите заказ для перехода к оплате. Для редактирования вернитесь на нужный шаг.",
        "",
        "<b>Спецификация:</b>",
        f"• Тип: {escape(category_name)}",
    ]

    field_labels = {
        "object": "Главный объект",
        "environment": "Окружение",
        "text_layer": "Текстовый слой",
        "details": "Детали",
        "colors": "Цветовая схема",
        "concept": "Концепция",
        "style": "Стиль",
        "deadline": "Дедлайн",
    }

    for key, label in field_labels.items():
        value = answers.get(key)
        if value:
            lines.append(f"• {label}: {escape(str(value))}")

    lines.extend([
        "",
        f"<b>К оплате: {money(price)}</b>",
        "Статус: Ожидание транзакции",
    ])
    return "\n".join(lines)


def build_order_brief(session: dict) -> str:
    """Build a plain-text brief that can be stored in Supabase."""
    category_code = session["category"]
    answers = session.get("answers", {})
    category_name = ORDER_CATEGORIES.get(category_code, "Заказ")
    field_labels = {
        "object": "Главный объект",
        "environment": "Окружение",
        "text_layer": "Текстовый слой",
        "details": "Детали",
        "colors": "Цветовая схема",
        "concept": "Концепция",
        "style": "Стиль",
        "deadline": "Дедлайн",
    }
    lines = [f"Тип: {category_name}"]
    for key, label in field_labels.items():
        value = answers.get(key)
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def build_admin_order_text(order: dict, session: dict, user) -> str:
    """Render an admin notification for a newly confirmed order."""
    category_code = session["category"]
    category_name = ORDER_CATEGORIES.get(category_code, "Заказ")
    price = ORDER_PRICES_RUB.get(category_code, Decimal("1200"))
    username = escape(f"@{user.username}" if user.username else (user.full_name or str(user.id)))
    order_number = escape(str(order.get("order_number") or "новый заказ"))
    brief = build_order_brief(session)
    if len(brief) > 2600:
        brief = brief[:2600].rstrip() + "\n...ТЗ обрезано, полная версия в Supabase."
    return (
        "<b>Новый заказ в Rival Space</b>\n\n"
        f"<b>{order_number}</b>\n"
        f"Клиент: {username}\n"
        f"Telegram ID: <code>{user.id}</code>\n"
        f"Тип: <b>{escape(category_name)}</b>\n"
        f"Сумма: <b>{money(price)}</b>\n"
        "Статус: <b>Ожидает оплаты</b>\n\n"
        "<b>ТЗ:</b>\n"
        f"<pre>{escape(brief)}</pre>"
    )


def build_admin_order_fallback(order: dict, session: dict, user) -> str:
    """Plain notification that should pass even if Telegram rejects HTML."""
    category_name = ORDER_CATEGORIES.get(session["category"], "Заказ")
    brief = build_order_brief(session)
    if len(brief) > 1800:
        brief = brief[:1800].rstrip() + "\n...ТЗ обрезано, полная версия в Supabase."
    username = f"@{user.username}" if user.username else (user.full_name or str(user.id))
    return (
        "Новый заказ в Rival Space\n\n"
        f"{order.get('order_number') or 'новый заказ'}\n"
        f"Клиент: {username}\n"
        f"Telegram ID: {user.id}\n"
        f"Тип: {category_name}\n"
        f"Сумма: {money(ORDER_PRICES_RUB.get(session['category'], Decimal('1200')))}\n"
        "Статус: Ожидает оплаты\n\n"
        f"ТЗ:\n{brief}"
    )


def build_payment_text(session: dict) -> str:
    category_code = session["category"]
    price = ORDER_PRICES_RUB.get(category_code, Decimal("1200"))
    order_number = session.get("order_number")
    order_line = f"Заказ: <b>{escape(str(order_number))}</b>\n" if order_number else ""
    return (
        order_line +
        f"<b>К оплате: {money(price)}</b>\n"
        "Статус: Ожидание транзакции\n\n"
        "Выберите метод оплаты. После подтверждения платежа система активирует заказ и зафиксирует дедлайн в рабочем графике.\n\n"
        "Доступные методы:\n"
        "• CryptoBot (USDT / TON / BTC)\n"
        "• Банковская карта (РФ)\n\n"
        "Транзакция защищена. Заказ будет передан дизайнеру автоматически."
    )


async def notify_admin(bot: Bot, text: str, fallback_text: str | None = None):
    """Send a notification to the configured designer/admin chat."""
    if not ADMIN_TELEGRAM_ID:
        logger.warning("ADMIN_TELEGRAM_ID is not set; admin notification skipped")
        return False
    try:
        await bot.send_message(chat_id=int(ADMIN_TELEGRAM_ID), text=text, parse_mode=ParseMode.HTML)
        return True
    except Exception as exc:
        logger.exception("Could not send admin notification as HTML")
        if fallback_text:
            try:
                await bot.send_message(chat_id=int(ADMIN_TELEGRAM_ID), text=fallback_text[:3900])
                return True
            except Exception:
                logger.exception("Could not send admin fallback notification")
        logger.warning("Admin notification failed: %s", exc)
        return False


def admin_status_line() -> str:
    """Return a safe status line for admin notification setup."""
    if not ADMIN_TELEGRAM_ID:
        return "ADMIN_TELEGRAM_ID: <code>missing</code>"
    masked = ADMIN_TELEGRAM_ID[:3] + "***" + ADMIN_TELEGRAM_ID[-3:] if len(ADMIN_TELEGRAM_ID) > 6 else "***"
    return f"ADMIN_TELEGRAM_ID: <code>set ({masked})</code>"


def callback_order_id(data: str | None) -> str | None:
    """Extract order id from callback data like action:uuid."""
    if not data or ":" not in data:
        return None
    return data.split(":", 1)[1] or None


async def ensure_order_for_session(callback, session: dict) -> dict | None:
    """Persist the current order wizard session to Supabase once."""
    if session.get("order_id"):
        return {
            "id": session.get("order_id"),
            "order_number": session.get("order_number"),
        }

    user = await ensure_telegram_user(callback.from_user)
    category_code = session["category"]
    category_name = ORDER_CATEGORIES.get(category_code, "Заказ")
    price = ORDER_PRICES_RUB.get(category_code, Decimal("1200"))
    brief = build_order_brief(session)
    order = await db.create_order(
        user_id=user["id"],
        service_name=category_name,
        total_amount=price,
        brief=brief,
        status="waiting_payment",
    )
    if not order:
        raise RuntimeError("Supabase did not return created order")

    session["order_id"] = order["id"]
    session["order_number"] = order.get("order_number")
    session["db_user_id"] = user["id"]
    try:
        await db.create_order_message(
            order_id=order["id"],
            sender_id=user["id"],
            sender_role="client",
            text=brief,
        )
    except Exception:
        logger.exception("Could not create order chat message for order_id=%s", order["id"])
    sent = await notify_admin(
        callback.bot,
        build_admin_order_text(order, session, callback.from_user),
        build_admin_order_fallback(order, session, callback.from_user),
    )
    if not sent:
        logger.warning("Order %s was saved but admin notification was not delivered", order.get("id"))
    return order


async def run_supabase_diagnostics(telegram_id: int) -> str:
    """Create and remove a tiny test user/order using the current bot environment."""
    test_user = None
    test_order = None
    report = [
        "<b>Bot diagnostics</b>",
        f"SUPABASE_URL: <code>{'set' if os.getenv('SUPABASE_URL') else 'missing'}</code>",
        f"SUPABASE_SERVICE_KEY: <code>{'set' if os.getenv('SUPABASE_SERVICE_KEY') else 'missing'}</code>",
        f"SUPABASE_SECRET_KEY: <code>{'set' if os.getenv('SUPABASE_SECRET_KEY') else 'missing'}</code>",
        admin_status_line(),
    ]
    try:
        test_user = await db.get_or_create_user(
            telegram_id=9000000000000 + int(str(telegram_id)[-6:]),
            username="diag_user",
            first_name="Diag",
        )
        report.append(f"User insert: <code>ok</code> <code>{test_user.get('id')}</code>")
        test_order = await db.create_order(
            user_id=test_user["id"],
            service_name="Diagnostic order",
            total_amount=Decimal("1.00"),
            brief="diagnostic brief",
        )
        report.append(f"Order insert: <code>ok</code> <code>{test_order.get('order_number')}</code>")
        return "\n".join(report)
    except Exception as exc:
        report.append(f"Error: <pre>{escape(str(exc)[:1200])}</pre>")
        return "\n".join(report)
    finally:
        try:
            async with db.session() as client:
                if test_order:
                    await client.delete("/orders", params={"id": f"eq.{test_order['id']}"})
                if test_user:
                    await client.delete("/users", params={"id": f"eq.{test_user['id']}"})
        except Exception:
            logger.exception("Could not clean diagnostic rows")


async def create_deposit_invoice(message: Message, user_id: int, amount: Decimal):
    try:
        invoice = await get_cryptopay().create_invoice(
            asset=CRYPTOPAY_ASSET,
            amount=float(amount),
            description=f"Пополнение Rival Space: {amount} {CRYPTOPAY_ASSET}",
        )
        pay_url = invoice_url(invoice)
        if not pay_url:
            raise RuntimeError("CryptoBot invoice was created without a payment URL")
        await message.answer(
            "<b>Счёт на пополнение создан</b>\n\n"
            f"Сумма: <b>{amount} {CRYPTOPAY_ASSET}</b>\n"
            "Открой оплату через кнопку ниже.",
            parse_mode=ParseMode.HTML,
            reply_markup=payment_kb(pay_url),
        )
        user = await db.get_user(user_id)
        if user:
            await db.create_payment(
                user_id=user["id"],
                amount=amount,
                invoice_id=str(invoice.invoice_id),
                pay_url=pay_url,
            )
    except Exception as e:
        logger.exception("Failed to create deposit invoice: %s", e)
        await message.answer(
            "Не удалось создать счёт CryptoBot. Проверь токен CryptoPay или попробуй позже.",
            reply_markup=back_to_menu_kb(),
        )


async def create_order_invoice(message: Message, session: dict, telegram_user):
    category_code = session["category"]
    price = ORDER_PRICES_RUB.get(category_code, Decimal("1200"))
    category_name = ORDER_CATEGORIES.get(category_code, "Заказ")
    try:
        user = await ensure_telegram_user(telegram_user)
        if not session.get("order_id"):
            order = await db.create_order(
                user_id=user["id"],
                service_name=category_name,
                total_amount=price,
                brief=build_order_brief(session),
                status="waiting_payment",
            )
            if order:
                session["order_id"] = order["id"]
                session["order_number"] = order.get("order_number")
                session["db_user_id"] = user["id"]

        invoice = await get_cryptopay().create_invoice(
            amount=float(price),
            fiat="RUB",
            currency_type="fiat",
            accepted_assets=["USDT", "TON", "BTC"],
            description=f"Rival Space: {category_name}",
        )
        pay_url = invoice_url(invoice)
        if not pay_url:
            raise RuntimeError("CryptoBot order invoice was created without a payment URL")
        try:
            payment = await db.create_payment(
                user_id=session.get("db_user_id") or user["id"],
                amount=price,
                invoice_id=str(invoice.invoice_id),
                pay_url=pay_url,
                currency="RUB",
            )
            if payment and session.get("order_id"):
                await db.attach_payment_to_order(session["order_id"], payment["id"])
        except Exception:
            logger.exception("Could not persist order payment draft")
        await message.answer(
            "<b>Счёт CryptoBot создан</b>\n\n"
            f"Заказ: <b>{escape(str(session.get('order_number') or category_name))}</b>\n"
            f"Сумма: <b>{money(price)}</b>\n"
            "Оплатите счёт и нажмите «Я оплатил» или отправьте чек.",
            parse_mode=ParseMode.HTML,
            reply_markup=order_crypto_payment_kb(pay_url, session.get("order_id")),
        )
    except Exception as e:
        logger.exception("Failed to create order invoice: %s", e)
        await message.answer(
            "Не удалось создать счёт CryptoBot для заказа. Можно выбрать банковскую карту или попробовать позже.",
            reply_markup=order_payment_kb(session.get("order_id")),
        )


async def create_order_invoice_for_persisted_order(message: Message, order: dict, telegram_user):
    """Create a CryptoBot invoice when the in-memory session is gone."""
    category_name = str(order.get("service_name") or "Заказ")
    price = safe_decimal(order.get("total_amount"), "1200")
    try:
        await ensure_telegram_user(telegram_user)
        invoice = await get_cryptopay().create_invoice(
            amount=float(price),
            fiat="RUB",
            currency_type="fiat",
            accepted_assets=["USDT", "TON", "BTC"],
            description=f"Rival Space: {category_name}",
        )
        pay_url = invoice_url(invoice)
        if not pay_url:
            raise RuntimeError("CryptoBot order invoice was created without a payment URL")
        try:
            payment = await db.create_payment(
                user_id=order["user_id"],
                amount=price,
                invoice_id=str(invoice.invoice_id),
                pay_url=pay_url,
                currency="RUB",
            )
            if payment:
                await db.attach_payment_to_order(order["id"], payment["id"])
        except Exception:
            logger.exception("Could not persist order payment draft")
        await message.answer(
            "<b>Счёт CryptoBot создан</b>\n\n"
            f"Заказ: <b>{escape(str(order.get('order_number') or category_name))}</b>\n"
            f"Сумма: <b>{money(price)}</b>\n"
            "Оплатите счёт и нажмите «Я оплатил» или отправьте чек.",
            parse_mode=ParseMode.HTML,
            reply_markup=order_crypto_payment_kb(pay_url, order["id"]),
        )
    except Exception as e:
        logger.exception("Failed to create persisted order invoice: %s", e)
        await message.answer(
            "Не удалось создать счёт CryptoBot для заказа. Можно выбрать банковскую карту или попробовать позже.",
            reply_markup=order_payment_kb(order.get("id")),
        )


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    SESSIONS.pop(message.from_user.id, None)
    run_background(ensure_telegram_user(message.from_user))
    await send_main_menu(message)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Handle /menu command."""
    SESSIONS.pop(message.from_user.id, None)
    run_background(ensure_telegram_user(message.from_user))
    await send_main_menu(message)


@router.message(Command("id"))
async def cmd_id(message: Message):
    """Show the user's Telegram ID for admin setup."""
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode=ParseMode.HTML)


@router.message(Command("diag"))
async def cmd_diag(message: Message):
    """Run a safe Supabase diagnostic from the deployed bot environment."""
    await message.answer("Проверяю Supabase из окружения бота...")
    result = await run_supabase_diagnostics(message.from_user.id)
    await message.answer(result, parse_mode=ParseMode.HTML)


@router.message(Command("admin_test"))
async def cmd_admin_test(message: Message):
    """Send a test notification to the configured admin chat."""
    if not ADMIN_TELEGRAM_ID:
        await message.answer(
            "ADMIN_TELEGRAM_ID не задан в окружении бота. Добавь его именно в Railway и сделай redeploy."
        )
        return

    sent = await notify_admin(
        message.bot,
        "<b>Тест уведомлений Rival Space</b>\n\n"
        f"Команду запустил: <code>{message.from_user.id}</code>\n"
        "Если ты видишь это сообщение, админ-уведомления работают.",
    )
    if sent:
        await message.answer("Тестовое уведомление отправлено админу.")
    else:
        await message.answer(
            "Не смог отправить тест админу. Проверь, что ADMIN_TELEGRAM_ID это именно numeric ID, "
            "и что этот аккаунт уже нажимал /start в боте."
        )


@router.callback_query(F.data == "menu_order")
@instant_ack
async def callback_order(callback):
    """Show order category selection."""
    run_background(ensure_telegram_user(callback.from_user))
    await callback.message.answer(
        "<b>Выбери направление заказа</b>\n\n"
        "Нажми на нужный тип работы — дальше откроется оформление заказа.",
        parse_mode=ParseMode.HTML,
        reply_markup=order_category_kb(),
    )
    await ack_callback(callback)


@router.callback_query(F.data.in_(CATEGORY_CALLBACKS))
@instant_ack
async def callback_order_category(callback):
    """Selected order category."""
    category_code = callback.data.replace("order_", "", 1)
    reset_order_session(callback.from_user.id, category_code)
    await send_order_step(callback.message, callback.from_user.id)
    await ack_callback(callback)


@router.callback_query(F.data == "order_skip")
@instant_ack
async def callback_order_skip(callback):
    session = get_order_session(callback.from_user.id)
    if not session:
        await ack_callback(callback)
        return
    step_number = session["step"]
    step = ORDER_STEPS.get(step_number)
    if step and step.get("skip"):
        session["answers"][step["key"]] = "Пропустить"
        session["step"] += 1
        await send_order_step(callback.message, callback.from_user.id)
    await ack_callback(callback)


@router.callback_query(F.data == "order_back")
@instant_ack
async def callback_order_back(callback):
    session = get_order_session(callback.from_user.id)
    if session:
        session["step"] = max(2, int(session.get("step", 2)) - 1)
        await send_order_step(callback.message, callback.from_user.id)
    await ack_callback(callback)


@router.callback_query(F.data == "order_style_back")
@instant_ack
async def callback_order_style_back(callback):
    session = get_order_session(callback.from_user.id)
    if session:
        session["step"] = 8
        await send_order_step(callback.message, callback.from_user.id)
    await ack_callback(callback)


@router.callback_query(F.data.startswith("order_style_"))
@instant_ack
async def callback_order_style(callback):
    session = get_order_session(callback.from_user.id)
    if not session:
        await ack_callback(callback)
        return
    style_code = callback.data.replace("order_style_", "", 1)
    session["answers"]["style"] = STYLE_LABELS.get(style_code, style_code)
    await callback.message.answer(
        "<b>Спецификация заказа</b>\n"
        "Шаг 8 / 8 | Тайминг и дедлайн\n\n"
        "Укажите время на реализацию проекта. Система бронирует слот в графике дизайнера и фиксирует время сдачи.",
        parse_mode=ParseMode.HTML,
        reply_markup=order_deadline_kb(),
    )
    await ack_callback(callback)


@router.callback_query(F.data.startswith("order_deadline_"))
@instant_ack
async def callback_order_deadline(callback):
    session = get_order_session(callback.from_user.id)
    if not session:
        await ack_callback(callback)
        return
    hours = callback.data.replace("order_deadline_", "", 1)
    session["answers"]["deadline"] = f"{hours} ч."
    await callback.message.answer(build_review_text(session), parse_mode=ParseMode.HTML, reply_markup=order_review_kb())
    await ack_callback(callback)


@router.callback_query(F.data == "order_show_review")
@instant_ack
async def callback_order_show_review(callback):
    session = get_order_session(callback.from_user.id)
    if session:
        await callback.message.answer(build_review_text(session), parse_mode=ParseMode.HTML, reply_markup=order_review_kb())
    await ack_callback(callback)


@router.callback_query(F.data == "order_restart")
@instant_ack
async def callback_order_restart(callback):
    session = get_order_session(callback.from_user.id)
    if session:
        reset_order_session(callback.from_user.id, session["category"])
        await send_order_step(callback.message, callback.from_user.id)
    await ack_callback(callback)


@router.callback_query(F.data == "order_confirm")
@instant_ack
async def callback_order_confirm(callback):
    session = get_order_session(callback.from_user.id)
    if session:
        try:
            await ensure_order_for_session(callback, session)
        except Exception:
            logger.exception("Could not persist order for user_id=%s", callback.from_user.id)
            result = await run_supabase_diagnostics(callback.from_user.id)
            await callback.message.answer(
                "Не смог сохранить заказ в базе. Ниже диагностика из окружения бота:\n\n"
                f"{result}",
                parse_mode=ParseMode.HTML,
                reply_markup=order_review_kb(),
            )
            return
        await callback.message.answer(
            build_payment_text(session),
            parse_mode=ParseMode.HTML,
            reply_markup=order_payment_kb(session.get("order_id")),
        )
    await ack_callback(callback)


@router.callback_query(F.data.startswith("order_pay_crypto"))
@instant_ack
async def callback_order_pay_crypto(callback):
    session = get_order_session(callback.from_user.id)
    if session:
        await create_order_invoice(callback.message, session, callback.from_user)
        await ack_callback(callback)
        return
    order_id = callback_order_id(callback.data)
    if order_id:
        order = await db.get_order(order_id)
        if order:
            await create_order_invoice_for_persisted_order(callback.message, order, callback.from_user)
    await ack_callback(callback)


@router.callback_query(F.data.startswith("order_pay_card"))
@instant_ack
async def callback_order_pay_card(callback):
    session = get_order_session(callback.from_user.id)
    order_id = session.get("order_id") if session else callback_order_id(callback.data)
    await callback.message.answer(
        "<b>Оплата банковской картой</b>\n\n"
        "Напиши дизайнеру в Telegram для получения актуальных реквизитов. После оплаты отправь чек через кнопку «Отправить чек».",
        parse_mode=ParseMode.HTML,
        reply_markup=order_payment_kb(order_id),
    )
    await ack_callback(callback)


@router.callback_query(F.data.startswith("order_paid"))
@instant_ack
async def callback_order_paid(callback):
    session = get_order_session(callback.from_user.id)
    order_id = session.get("order_id") if session else callback_order_id(callback.data)
    order_number = session.get("order_number") if session else order_id
    if order_id:
        try:
            await db.update_order(order_id, {"status": "payment_review"})
            await notify_admin(
                callback.bot,
                "<b>Клиент отметил оплату</b>\n\n"
                f"Заказ: <b>{escape(str(order_number))}</b>\n"
                f"Клиент: <code>{callback.from_user.id}</code>\n"
                "Статус переведён в проверку оплаты.",
            )
        except Exception:
            logger.exception("Could not mark order payment review for order_id=%s", order_id)
    await callback.message.answer(
        "Платёж отмечен как отправленный. Если оплата уже прошла, отправь чек или дождись подтверждения дизайнера.",
        reply_markup=order_payment_kb(order_id),
    )
    await ack_callback(callback)


@router.callback_query(F.data.startswith("order_receipt"))
@instant_ack
async def callback_order_receipt(callback):
    session = get_order_session(callback.from_user.id)
    order_id = session.get("order_id") if session else callback_order_id(callback.data)
    SESSIONS[callback.from_user.id] = {
        "mode": "receipt_waiting",
        "order_id": order_id,
        "order_number": session.get("order_number") if session else None,
        "db_user_id": session.get("db_user_id") if session else None,
    }
    await callback.message.answer("Пришли чек файлом, фото или текстом. Я сохраню его в заявке.")
    await ack_callback(callback)


@router.callback_query(F.data == "menu_profile")
@instant_ack
async def callback_profile(callback):
    """Show user profile."""
    loading = await callback.message.answer("Открываю профиль...")
    user = None
    orders = []
    try:
        user = await db.get_user(callback.from_user.id)
        if not user:
            user = await ensure_telegram_user(callback.from_user)
        if user:
            orders = await db.get_user_orders_for_user_id(user["id"])
    except Exception:
        logger.exception("Could not load profile data for user_id=%s", callback.from_user.id)

    completed_orders = [order for order in orders if order.get("status") in {"delivered", "closed"}]
    active_orders = [order for order in orders if order.get("status") in ACTIVE_STATUSES]
    total_amount = sum(safe_decimal(order.get("total_amount")) for order in completed_orders)
    balance = safe_decimal(user.get("balance") if user else 0)
    username = escape(callback.from_user.username or callback.from_user.first_name or "client")

    profile_text = (
        f"<b>Профиль — @{username}</b>\n\n"
        f"Аккаунт: клиент @{PUBLIC_BOT_USERNAME}\n\n"
        "<b>Активность:</b>\n"
        f"— Выполнено заказов: <b>{len(completed_orders)}</b>\n"
        f"— Общая сумма: <b>{money(total_amount)}</b>\n"
        f"— Баланс: <b>{money(balance)}</b>\n"
        f"— Активно: <b>{len(active_orders)}</b>"
    )

    await loading.edit_text(text=profile_text, parse_mode=ParseMode.HTML, reply_markup=profile_kb())
    await ack_callback(callback)


@router.callback_query(F.data == "profile_deposit")
@instant_ack
async def callback_deposit(callback):
    """Show deposit options."""
    await callback.message.answer(
        "<b>Пополнение баланса</b>\n\n"
        "Выбери готовую сумму или введи свою вручную. После этого я создам счёт CryptoBot.",
        parse_mode=ParseMode.HTML,
        reply_markup=deposit_kb(),
    )
    await ack_callback(callback)


@router.callback_query(F.data == "deposit_manual")
@instant_ack
async def callback_deposit_manual(callback):
    SESSIONS[callback.from_user.id] = {"mode": "deposit_manual"}
    await callback.message.answer(
        "Введи сумму пополнения в USDT одним сообщением.\n\nНапример: <b>7.5</b>",
        parse_mode=ParseMode.HTML,
    )
    await ack_callback(callback)


@router.callback_query(F.data.startswith("deposit_"))
@instant_ack
async def callback_deposit_amount(callback):
    """Create invoice for deposit."""
    amount = parse_amount(callback.data.split("_", 1)[1])
    if amount is None:
        await callback.message.answer("Не понял сумму. Попробуй ещё раз.", reply_markup=deposit_kb())
    else:
        await create_deposit_invoice(callback.message, callback.from_user.id, amount)
    await ack_callback(callback)


def build_orders_text(title: str, orders: list[dict]) -> str:
    """Render compact order list."""
    if not orders:
        return f"<b>{title}</b>\n\nПока здесь пусто. Как только появится заказ, он будет отображаться в этом разделе."

    lines = [f"<b>{title}</b>"]
    for order in orders[:10]:
        order_num = order.get("order_number", "—")
        service = order.get("service_name") or order.get("title") or "Заказ"
        status = STATUS_LABELS.get(order.get("status"), order.get("status", "—"))
        amount = money(order.get("total_amount") or 0)
        lines.append(f"\n<code>{escape(str(order_num))}</code>\n{escape(str(service))}\n{amount} — {escape(str(status))}")
    return "\n".join(lines)


@router.callback_query(F.data == "profile_orders")
@instant_ack
async def callback_orders(callback):
    """Show user orders history."""
    orders = await db.get_user_orders(callback.from_user.id)
    completed_or_all = [order for order in orders if order.get("status") not in ACTIVE_STATUSES]
    await callback.message.answer(
        build_orders_text("История заказов", completed_or_all),
        parse_mode=ParseMode.HTML,
        reply_markup=orders_kb(),
    )
    await ack_callback(callback)


@router.callback_query(F.data == "profile_active_orders")
@instant_ack
async def callback_active_orders(callback):
    """Show active orders."""
    orders = await db.get_user_orders(callback.from_user.id)
    active_orders = [order for order in orders if order.get("status") in ACTIVE_STATUSES]
    await callback.message.answer(
        build_orders_text("Активные заказы", active_orders),
        parse_mode=ParseMode.HTML,
        reply_markup=orders_kb(),
    )
    await ack_callback(callback)


@router.callback_query(F.data == "back_to_menu")
@instant_ack
async def callback_back_to_menu(callback):
    """Return to main menu."""
    SESSIONS.pop(callback.from_user.id, None)
    run_background(ensure_telegram_user(callback.from_user))
    await send_main_menu(callback.message)
    await ack_callback(callback)


@router.callback_query()
@instant_ack
async def callback_unknown(callback):
    """Handle stale inline buttons from older bot messages."""
    logger.warning(
        "Unknown callback data: data=%s user_id=%s",
        getattr(callback, "data", None),
        getattr(getattr(callback, "from_user", None), "id", None),
    )
    if callback.message:
        await callback.message.answer(
            "Эта кнопка уже устарела. Нажми /start, я отправлю свежее меню."
        )
    await ack_callback(callback)


@router.message()
async def handle_text_state(message: Message):
    """Handle free-text states for manual deposit and order wizard."""
    user_id = message.from_user.id
    session = SESSIONS.get(user_id)
    if not session:
        return

    if session.get("mode") == "deposit_manual":
        amount = parse_amount(message.text or "")
        if amount is None:
            await message.answer("Введи корректную сумму числом, например: 12.5")
            return
        SESSIONS.pop(user_id, None)
        await create_deposit_invoice(message, user_id, amount)
        return

    if session.get("mode") == "receipt_waiting":
        order_id = session.get("order_id")
        order_number = session.get("order_number") or order_id or "заказ"
        user = await ensure_telegram_user(message.from_user)
        receipt_text = message.text or message.caption or "Клиент отправил чек вложением."
        attachment_url = None
        if message.document:
            attachment_url = message.document.file_id
        elif message.photo:
            attachment_url = message.photo[-1].file_id
        elif message.video:
            attachment_url = message.video.file_id

        if order_id:
            try:
                await db.update_order(order_id, {"status": "payment_review"})
                await db.create_order_message(
                    order_id=order_id,
                    sender_id=session.get("db_user_id") or user["id"],
                    sender_role="client",
                    text=receipt_text,
                    attachment_url=attachment_url,
                )
                await notify_admin(
                    message.bot,
                    "<b>Клиент отправил чек</b>\n\n"
                    f"Заказ: <b>{escape(str(order_number))}</b>\n"
                    f"Клиент: <code>{message.from_user.id}</code>\n"
                    f"Сообщение: {escape(receipt_text)}\n"
                    + (f"Вложение file_id: <code>{escape(attachment_url)}</code>" if attachment_url else ""),
                )
            except Exception:
                logger.exception("Could not save receipt for order_id=%s", order_id)
        SESSIONS.pop(user_id, None)
        await message.answer(
            "Чек получен. Дизайнер проверит оплату и подтвердит заказ.",
            reply_markup=back_to_menu_kb(),
        )
        return

    if session.get("mode") != "order":
        return

    step_number = session.get("step")
    step = ORDER_STEPS.get(step_number)
    if not step:
        await message.answer("Выбери вариант кнопкой ниже, чтобы продолжить.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Напиши ответ текстом, чтобы я сохранил его в ТЗ.")
        return

    session["answers"][step["key"]] = text
    session["step"] = step_number + 1
    await send_order_step(message, user_id)


async def main():
    """Main entry point."""
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Rival Design Bot started")
    allowed_updates = dp.resolve_used_update_types()
    logger.info("Polling allowed updates: %s", allowed_updates)
    await dp.start_polling(bot, allowed_updates=allowed_updates)


if __name__ == "__main__":
    asyncio.run(main())
