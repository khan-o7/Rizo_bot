"""
Catalog: kategoriyalar → mahsulotlar → mahsulot kartasi.

Har bir sahifada foydalanuvchining joriy savatchasi yuklanadi va
keyboard'ga savatcha tugmasi + mahsulot sonlari ko'rsatiladi.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from db.session import get_session
from keyboards.user_kb import categories_kb, product_detail_kb, products_kb
from services.cart_service import get_cart_with_items
from services.product_service import (
    get_active_categories,
    get_product,
    get_products_by_category,
)
from utils.formatters import fmt_price, fmt_qty
from utils.filters import PRIVATE_ONLY
from utils.filters import PRIVATE_ONLY
from utils.filters import PRIVATE_ONLY
from utils.tg_helpers import safe_edit

logger = logging.getLogger(__name__)


def _qty_for(cart, product_id: int) -> float:
    """Savatchada shu mahsulotdan nechta borligini qaytaradi."""
    if not cart:
        return 0
    for item in cart.items:
        if item.product_id == product_id:
            return item.qty
    return 0


# ── Handlers ──────────────────────────────────────────────────────────


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with get_session() as session:
        cats = await get_active_categories(session)
        cart = await get_cart_with_items(session, tg_user.id)

    if not cats:
        await update.message.reply_text("😔 Hozircha mahsulotlar mavjud emas.")
        return

    await update.message.reply_text(
        "📦 <b>Kategoriyani tanlang:</b>",
        parse_mode="HTML",
        reply_markup=categories_kb(cats, cart=cart),
    )


async def cbq_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: cat:<id>"""
    query = update.callback_query
    await query.answer()
    category_id = int(query.data.split(":")[1])
    tg_user = update.effective_user

    async with get_session() as session:
        products = await get_products_by_category(session, category_id)
        cart = await get_cart_with_items(session, tg_user.id)

    if not products:
        await safe_edit(query.message, "😔 Bu kategoriyada mahsulot yo'q.")
        return

    await safe_edit(
        query.message,
        "🛍 <b>Mahsulotni tanlang:</b>",
        reply_markup=products_kb(products, category_id, cart=cart),
    )


async def cbq_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: prod:<id>"""
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    tg_user = update.effective_user

    async with get_session() as session:
        product = await get_product(session, product_id)
        cart = await get_cart_with_items(session, tg_user.id)

    if product is None:
        await safe_edit(query.message, "❌ Mahsulot topilmadi.")
        return

    qty = _qty_for(cart, product_id)
    caption = (
        f"🛍 <b>{product.name}</b>\n"
        f"💰 Narx: <b>{fmt_price(float(product.price))}</b>"
    )
    if product.description:
        caption += f"\n\n📝 {product.description}"

    kb = product_detail_kb(product.id, product.category_id, qty_in_cart=qty, cart=cart)

    if product.photo_file_id:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.reply_photo(
            photo=product.photo_file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await safe_edit(query.message, caption, reply_markup=kb)


async def cbq_back_cats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: back:cats"""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user

    async with get_session() as session:
        cats = await get_active_categories(session)
        cart = await get_cart_with_items(session, tg_user.id)

    await safe_edit(
        query.message,
        "📦 <b>Kategoriyani tanlang:</b>",
        reply_markup=categories_kb(cats, cart=cart),
    )


def register_catalog_handlers(app) -> None:
    app.add_handler(MessageHandler(PRIVATE_ONLY & filters.Regex("^🛍 Katalog$"), show_catalog))
    app.add_handler(CallbackQueryHandler(cbq_category, pattern=r"^cat:\d+$"))
    app.add_handler(CallbackQueryHandler(cbq_product, pattern=r"^prod:\d+$"))
    app.add_handler(CallbackQueryHandler(cbq_back_cats, pattern=r"^back:cats$"))
