"""Start command and main menu."""
from __future__ import annotations

import html
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from config import config
from db.session import get_session
from keyboards.admin_kb import admin_main_kb
from keyboards.user_kb import main_menu_kb
from services.user_service import get_or_create_user
from utils.filters import PRIVATE_ONLY

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    async with get_session() as session:
        await get_or_create_user(
            session,
            tg_id=user.id,
            username=user.username,
            full_name=user.full_name,
        )

    name = html.escape(user.first_name or "")

    # Oddiy foydalanuvchi uchun — asosiy menyu
    await update.message.reply_text(
        f"👋 Salom, <b>{name}</b>!\n\n"
        "🛍 Oziq-ovqat do'konimizga xush kelibsiz.\n"
        "Quyidagi bo'limlardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )

    # Admin xabari — FAQAT config.ADMIN_IDS da bo'lganlar uchun
    if config.is_admin(user.id):
        logger.info(f"Admin kirdi: {user.id} (@{user.username})")
        await update.message.reply_text(
            "🔐 <b>Admin paneliga kirish uchun:</b> /admin",
            parse_mode="HTML",
        )
    else:
        # Debug: konsolda ko'rinsin (ishlab chiqarish logida o'chirish mumkin)
        logger.debug(
            f"Oddiy user: {user.id} | Adminlar ro'yxati: {config.ADMIN_IDS}"
        )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    await update.message.reply_text(
        "🔐 <b>Admin panel</b>\nQuyidagi amallardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


async def btn_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🏠 Asosiy menyu:", reply_markup=main_menu_kb())


def register_start_handlers(app) -> None:
    app.add_handler(CommandHandler("start", cmd_start, filters=PRIVATE_ONLY))
    app.add_handler(CommandHandler("admin", cmd_admin, filters=PRIVATE_ONLY))
    app.add_handler(MessageHandler(PRIVATE_ONLY & filters.Regex("^🔙 Asosiy menyu$"), btn_back_to_main))
