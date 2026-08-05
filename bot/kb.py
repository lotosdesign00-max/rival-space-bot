"""Keyboard definitions for the bot."""
import os
from pathlib import Path

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://rivaldesign.app")
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "https://t.me/rivalportfolio")
PRICES_URL = os.getenv("PRICES_URL", "https://t.me/rivalportfolio/4")
BLOG_URL = os.getenv("BLOG_URL", os.getenv("SERVICES_URL", "https://t.me/+a7SsFZHmCaJiNDMy"))
REVIEWS_URL = os.getenv("REVIEWS_URL", "https://t.me/reparival")


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu keyboard in the reference style."""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="Оставить заказ", callback_data="menu_order"))
    builder.row(InlineKeyboardButton(text="Мой профиль", callback_data="menu_profile"))
    builder.row(
        InlineKeyboardButton(text="Портфолио", url=PORTFOLIO_URL),
        InlineKeyboardButton(text="Цены", url=PRICES_URL),
    )
    builder.row(
        InlineKeyboardButton(text="Блог", url=BLOG_URL),
        InlineKeyboardButton(text="Отзывы", url=REVIEWS_URL),
    )

    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    """Profile keyboard."""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="Пополнить баланс", callback_data="profile_deposit"))
    builder.row(InlineKeyboardButton(text="История заказов", callback_data="profile_orders"))
    builder.row(InlineKeyboardButton(text="Активные заказы", callback_data="profile_active_orders"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="back_to_menu"))

    return builder.as_markup()


def deposit_kb() -> InlineKeyboardMarkup:
    """Deposit keyboard with amount options."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="5 USDT", callback_data="deposit_5"),
        InlineKeyboardButton(text="10 USDT", callback_data="deposit_10"),
    )
    builder.row(
        InlineKeyboardButton(text="25 USDT", callback_data="deposit_25"),
        InlineKeyboardButton(text="50 USDT", callback_data="deposit_50"),
    )
    builder.row(InlineKeyboardButton(text="Ввести вручную", callback_data="deposit_manual"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="menu_profile"))

    return builder.as_markup()


def orders_kb() -> InlineKeyboardMarkup:
    """Orders history keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Назад", callback_data="menu_profile")
    ]])


def order_category_kb() -> InlineKeyboardMarkup:
    """Order category selection keyboard copied from the reference structure."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="Аватарка", callback_data="order_avatar"),
        InlineKeyboardButton(text="Баннеры / превью", callback_data="order_banner_preview"),
    )
    builder.row(
        InlineKeyboardButton(text="Форумный баннер", callback_data="order_forum_banner"),
        InlineKeyboardButton(text="Креативы", callback_data="order_creatives"),
    )
    builder.row(
        InlineKeyboardButton(text="Инфографика", callback_data="order_infographic"),
        InlineKeyboardButton(text="Анимация аватарок", callback_data="order_avatar_animation"),
    )
    builder.row(InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu"))

    return builder.as_markup()


def order_step_kb(*, allow_skip: bool = False, allow_back: bool = True) -> InlineKeyboardMarkup:
    """Keyboard for text-based order steps."""
    rows = []
    if allow_skip:
        rows.append([InlineKeyboardButton(text="Пропустить", callback_data="order_skip")])
    nav = []
    if allow_back:
        nav.append(InlineKeyboardButton(text="Назад", callback_data="order_back"))
    nav.append(InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu"))
    rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_style_kb() -> InlineKeyboardMarkup:
    """Visual style selector."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Минимализм", callback_data="order_style_minimalism"),
            InlineKeyboardButton(text="Гармония", callback_data="order_style_harmony"),
            InlineKeyboardButton(text="Максимализм", callback_data="order_style_maximalism"),
        ],
        [InlineKeyboardButton(text="Назад", callback_data="order_back"), InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")],
    ])


def order_deadline_kb() -> InlineKeyboardMarkup:
    """Deadline selector."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="4 ч", callback_data="order_deadline_4"),
            InlineKeyboardButton(text="8 ч", callback_data="order_deadline_8"),
            InlineKeyboardButton(text="12 ч", callback_data="order_deadline_12"),
        ],
        [
            InlineKeyboardButton(text="24 ч", callback_data="order_deadline_24"),
            InlineKeyboardButton(text="48 ч", callback_data="order_deadline_48"),
            InlineKeyboardButton(text="72 ч", callback_data="order_deadline_72"),
        ],
        [InlineKeyboardButton(text="Назад", callback_data="order_style_back"), InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")],
    ])


def order_review_kb() -> InlineKeyboardMarkup:
    """Final order review keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить заказ", callback_data="order_confirm")],
        [InlineKeyboardButton(text="Редактировать сначала", callback_data="order_restart")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")],
    ])


def order_payment_kb(order_id: str | None = None) -> InlineKeyboardMarkup:
    """Order payment methods keyboard."""
    suffix = f":{order_id}" if order_id else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить CryptoBot", callback_data=f"order_pay_crypto{suffix}")],
        [InlineKeyboardButton(text="Банковская карта / реквизиты", callback_data=f"order_pay_card{suffix}")],
        [InlineKeyboardButton(text="Я оплатил", callback_data=f"order_paid{suffix}")],
        [InlineKeyboardButton(text="Отправить чек", callback_data=f"order_receipt{suffix}")],
        [InlineKeyboardButton(text="Проверить заказ", callback_data="order_show_review")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")],
    ])


def order_crypto_payment_kb(pay_url: str, order_id: str | None = None) -> InlineKeyboardMarkup:
    """CryptoBot order payment keyboard."""
    suffix = f":{order_id}" if order_id else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть оплату", url=pay_url)],
        [InlineKeyboardButton(text="Я оплатил", callback_data=f"order_paid{suffix}")],
        [InlineKeyboardButton(text="Отправить чек", callback_data=f"order_receipt{suffix}")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")],
    ])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Simple back to menu button."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")
    ]])


def payment_kb(pay_url: str) -> InlineKeyboardMarkup:
    """Deposit payment keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть оплату", url=pay_url)],
        [InlineKeyboardButton(text="Назад", callback_data="profile_deposit")],
    ])
