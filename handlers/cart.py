"""
Savatcha — inline add/remove/clear/view.

cbq_cart_add / cbq_cart_remove:
  Mahsulot kartasida bosilganda (photo yoki text xabar):
    → DB yangilanadi
    → Keyboard real vaqtda yangilanadi (qty + savatcha tugmasi)
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from db.session import get_session
from keyboards.user_kb import cart_kb, product_detail_kb
from services.cart_service import (
    add_to_cart,
    clear_cart,
    get_cart_with_items,
    remove_from_cart,
)
from services.user_service import get_or_create_user
from utils.formatters import fmt_cart, fmt_qty
from utils.filters import PRIVATE_ONLY
from utils.tg_helpers import safe_edit

logger = logging.getLogger(__name__)


def _qty_for(cart, product_id: int) -> float:
    if not cart:
        return 0
    for item in cart.items:
        if item.product_id == product_id:
            return item.qty
    return 0


def _parse_product_id_from_kb(message) -> int | None:
    """
    Mahsulot kartasining inline keyboard'idan product_id ni topadi.
    cart:add:<id> yoki cart:remove:<id> pattern'ini izlaydi.
    """
    try:
        if not message.reply_markup:
            return None
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                data = btn.callback_data or ""
                if data.startswith("cart:add:") or data.startswith("cart:remove:"):
                    return int(data.split(":")[2])
    except Exception:
        pass
    return None


def _parse_category_id_from_kb(message) -> int | None:
    """Keyboard'dagi cat:<id> dan category_id ni topadi."""
    try:
        if not message.reply_markup:
            return None
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                data = btn.callback_data or ""
                if data.startswith("cat:"):
                    return int(data.split(":")[1])
    except Exception:
        pass
    return None


async def _refresh_product_kb(query, cart, product_id: int) -> None:
    """
    Mahsulot kartasining keyboard'ini yangilaydi:
      - O'rta tugma: yangi qty
      - Savatcha tugmasi: yangi jami
    Photo xabarda reply_markup edit qilish mumkin (faqat caption emas).
    """
    category_id = _parse_category_id_from_kb(query.message) or 0
    qty = _qty_for(cart, product_id)
    new_kb = product_detail_kb(product_id, category_id, qty_in_cart=qty, cart=cart)

    try:
        await query.edit_message_reply_markup(reply_markup=new_kb)
    except BadRequest as e:
        if "not modified" in str(e).lower():
            pass  # keyboard o'zgarmagan — OK
        else:
            logger.debug(f"Keyboard yangilanmadi: {e}")


# ── Handlers ──────────────────────────────────────────────────────────


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'🛒 Savatcha' tugmasi yoki cart:view callback."""
    tg_user = update.effective_user
    async with get_session() as session:
        cart = await get_cart_with_items(session, tg_user.id)

    if not cart or not cart.items:
        if update.callback_query:
            await update.callback_query.answer("🛒 Savatcha bo'sh!", show_alert=True)
        else:
            await update.message.reply_text("🛒 Savatingiz bo'sh.")
        return

    text = fmt_cart(cart)
    kb = cart_kb(cart)

    if update.callback_query:
        await update.callback_query.answer()
        # Savatcha inline xabar sifatida ko'rsatiladi
        await update.callback_query.message.reply_text(
            text, parse_mode="HTML", reply_markup=kb
        )
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


def _is_cart_view(message) -> bool:
    """Xabar savatcha ko'rinishimi yoki mahsulot kartasimi — aniqlaymiz."""
    try:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data == "cart:clear":
                    return True
    except Exception:
        pass
    return False


async def cbq_cart_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: cart:add:<product_id>"""
    query = update.callback_query
    product_id = int(query.data.split(":")[2])
    tg_user = update.effective_user

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id)
        await add_to_cart(session, user, product_id)
        cart = await get_cart_with_items(session, tg_user.id)

    qty = _qty_for(cart, product_id)
    await query.answer(f"➕ Qo'shildi! Savatchada: {fmt_qty(qty)}")

    if _is_cart_view(query.message):
        # Savatcha ko'rinishida — matn + keyboard birga yangilanadi
        await safe_edit(query.message, fmt_cart(cart), reply_markup=cart_kb(cart))
    else:
        # Mahsulot kartasida — faqat keyboard
        await _refresh_product_kb(query, cart, product_id)


async def cbq_cart_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: cart:remove:<product_id>"""
    query = update.callback_query
    product_id = int(query.data.split(":")[2])
    tg_user = update.effective_user

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id)
        removed = await remove_from_cart(session, user, product_id)
        cart = await get_cart_with_items(session, tg_user.id)

    if not removed:
        await query.answer("Savatchada bu mahsulot yo'q.")
        return

    qty = _qty_for(cart, product_id)
    msg = f"➖ Kamaytirildi. Savatchada: {fmt_qty(qty)}" if qty > 0 else "🗑 Mahsulot olib tashlandi."
    await query.answer(msg)

    if _is_cart_view(query.message):
        # Savatcha ko'rinishida — bo'shab qolganmi?
        if not cart or not cart.items:
            await safe_edit(query.message, "🛒 Savatingiz bo'sh.")
        else:
            await safe_edit(query.message, fmt_cart(cart), reply_markup=cart_kb(cart))
    else:
        # Mahsulot kartasida — faqat keyboard
        await _refresh_product_kb(query, cart, product_id)


async def cbq_cart_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: cart:clear"""
    query = update.callback_query
    await query.answer("🗑 Savatcha tozalandi.")
    tg_user = update.effective_user

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id)
        await clear_cart(session, user)

    await safe_edit(query.message, "🛒 Savatingiz bo'sh.")


async def cbq_cart_remove_from_cart_view(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """cart:remove savatcha ko'rinishidan (matn xabar) ishlaganda."""
    # Bu handler catalog'dan emas, savatcha sahifasidan bosilganida
    # safe_edit bilan savatcha matnini yangilaydi
    query = update.callback_query
    product_id = int(query.data.split(":")[2])
    tg_user = update.effective_user

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id)
        await remove_from_cart(session, user, product_id)
        cart = await get_cart_with_items(session, tg_user.id)

    if not cart or not cart.items:
        await query.answer("🛒 Savatcha bo'shadi.")
        await safe_edit(query.message, "🛒 Savatingiz bo'sh.")
        return

    await query.answer("➖ Kamaytirildi.")
    await safe_edit(query.message, fmt_cart(cart), reply_markup=cart_kb(cart))


async def cbq_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()


def register_cart_handlers(app) -> None:
    app.add_handler(MessageHandler(PRIVATE_ONLY & filters.Regex("^🛒 Savatcha$"), show_cart))
    app.add_handler(CallbackQueryHandler(show_cart, pattern=r"^cart:view$"))
    app.add_handler(CallbackQueryHandler(cbq_cart_add, pattern=r"^cart:add:\d+$"))
    app.add_handler(CallbackQueryHandler(cbq_cart_remove, pattern=r"^cart:remove:\d+$"))
    app.add_handler(CallbackQueryHandler(cbq_cart_clear, pattern=r"^cart:clear$"))
    app.add_handler(CallbackQueryHandler(cbq_noop, pattern=r"^noop$"))
