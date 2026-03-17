"""
Telegram xabar yordamchilari.

safe_edit_text() — BARCHA JOYDA ishlatilishi kerak bo'lgan yagona funksiya.
Rasm/video xabarlarda edit_text() HECH QACHON chaqirilmaydi.
"""
from __future__ import annotations

import logging
from typing import Optional

from telegram import InlineKeyboardMarkup, Message
from telegram.error import BadRequest

logger = logging.getLogger(__name__)


def is_media_msg(msg: Message) -> bool:
    """True — agar xabarda rasm/video/document bo'lsa."""
    return bool(msg.photo or msg.video or msg.document or msg.animation or msg.sticker)


async def safe_edit(
    msg: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
) -> None:
    """
    Media xabarda: o'chir + yangi matn xabar yuvor.
    Matn xabarda: edit_text() qo'lla.
    Ikkalasida ham xatolik bo'lsa: reply_text() bilan yangi xabar yuvor.
    """
    if is_media_msg(msg):
        _delete_silently(msg)
        await msg.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        return

    try:
        await msg.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"edit_text xatosi ({e}), yangi xabar yuborilmoqda...")
        _delete_silently(msg)
        await msg.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)


def _delete_silently(msg: Message) -> None:
    """Xabarnomani sinxron o'chirish — await yo'q (fire-and-forget)."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(msg.delete())
    except Exception:
        pass
