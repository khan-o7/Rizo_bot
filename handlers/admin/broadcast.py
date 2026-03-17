"""Admin broadcast: send message to all registered users."""
from __future__ import annotations

import asyncio
from utils.filters import PRIVATE_ONLY
import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import config
from db.session import get_session
from keyboards.admin_kb import admin_main_kb
from services.user_service import get_all_user_ids

logger = logging.getLogger(__name__)

BROADCAST_TEXT = 0


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in config.ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text(
        "📢 <b>Broadcast</b>\n\nHamma foydalanuvchilarga yuboriladigan matnni kiriting:\n"
        "(bekor qilish uchun /cancel)",
        parse_mode="HTML",
    )
    return BROADCAST_TEXT


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    async with get_session() as session:
        user_ids = await get_all_user_ids(session)

    sent = failed = 0
    for tg_id in user_ids:
        try:
            await context.bot.send_message(chat_id=tg_id, text=text)
            sent += 1
            await asyncio.sleep(0.05)  # Avoid flood limits
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Broadcast yakunlandi.\n📤 Yuborildi: {sent}\n❌ Xato: {failed}",
        reply_markup=admin_main_kb(),
    )
    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=admin_main_kb())
    return ConversationHandler.END


def build_broadcast_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(PRIVATE_ONLY & filters.Regex("^📢 Broadcast$"), broadcast_start)
        ],
        states={
            BROADCAST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)
            ]
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
        conversation_timeout=120,
        allow_reentry=True,
    )
