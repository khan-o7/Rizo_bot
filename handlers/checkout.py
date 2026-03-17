"""
Checkout conversation — to'liq oqim.
Barcha query.edit_message_text → safe_edit() orqali.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import config
from db.models import DeliveryType, Order
from db.session import get_session
from keyboards.user_kb import delivery_type_kb, main_menu_kb, share_contact_kb, share_location_kb
from services.cart_service import cart_total, get_cart_with_items
from services.order_service import create_order
from services.user_service import get_or_create_user, update_phone
from utils.formatters import fmt_cart, fmt_order_for_admin
from utils.filters import PRIVATE_ONLY
from utils.tg_helpers import safe_edit
from utils.validators import clean_phone, is_valid_phone

logger = logging.getLogger(__name__)

CONFIRM, DELIVERY_TYPE, GET_PHONE, GET_LOCATION, GET_ADDRESS = range(5)

_KEY = "checkout"


def _ctx(c): return c.user_data.setdefault(_KEY, {})
def _clear(c): c.user_data.pop(_KEY, None)


# ── 1. Entry ──────────────────────────────────────────────────────────

async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _clear(context)

    async with get_session() as session:
        cart = await get_cart_with_items(session, update.effective_user.id)

    if not cart or not cart.items:
        await safe_edit(query.message, "🛒 Savatingiz bo'sh. Avval mahsulot qo'shing.")
        return ConversationHandler.END

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ha, buyurtma beraman", callback_data="co_ok")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="co_cancel")],
    ])
    await safe_edit(
        query.message,
        fmt_cart(cart) + "\n\n❓ Shu buyurtmani tasdiqlaysizmi?",
        reply_markup=kb,
    )
    return CONFIRM


# ── 2. Confirm ────────────────────────────────────────────────────────

async def step_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "co_cancel":
        await safe_edit(query.message, "❌ Buyurtma bekor qilindi.")
        _clear(context)
        return ConversationHandler.END

    await safe_edit(query.message, "📦 Yetkazib berish turini tanlang:")
    await query.message.reply_text(
        "Quyidagi tugmalardan birini bosing:",
        reply_markup=delivery_type_kb(),
    )
    return DELIVERY_TYPE


# ── 3. Delivery type ──────────────────────────────────────────────────

async def step_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    if text == "❌ Bekor qilish":
        await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_kb())
        _clear(context)
        return ConversationHandler.END

    if text == "🚚 Yetkazib berish":
        _ctx(context)["delivery_type"] = DeliveryType.DELIVERY
    elif text == "🏠 Olib ketish":
        _ctx(context)["delivery_type"] = DeliveryType.PICKUP
    else:
        await update.message.reply_text(
            "⚠️ Iltimos, quyidagi tugmalardan birini bosing:",
            reply_markup=delivery_type_kb(),
        )
        return DELIVERY_TYPE

    await update.message.reply_text(
        "📱 <b>Telefon raqamingizni yuboring:</b>",
        parse_mode="HTML",
        reply_markup=share_contact_kb(),
    )
    return GET_PHONE


# ── 4. Phone ──────────────────────────────────────────────────────────

async def step_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message

    if msg.contact:
        phone = clean_phone(msg.contact.phone_number)
    elif msg.text and is_valid_phone(msg.text):
        phone = clean_phone(msg.text)
    else:
        await msg.reply_text(
            "❌ Telefon raqam noto'g'ri.\n"
            "Tugma orqali yuboring yoki +998XXXXXXXXX formatida kiriting:",
            reply_markup=share_contact_kb(),
        )
        return GET_PHONE

    _ctx(context)["phone"] = phone
    async with get_session() as session:
        await update_phone(session, msg.from_user.id, phone)

    if _ctx(context).get("delivery_type") == DeliveryType.PICKUP:
        await msg.reply_text("✅ Qabul qilindi.", reply_markup=ReplyKeyboardRemove())
        return await _finalize(update, context)

    await msg.reply_text(
        "📍 <b>Yetkazib berish manzilingizni yuboring:</b>\n\n"
        "«📍 Lokatsiyani ulashish» tugmasini bosing.\n\n"
        "Agar tugma ko'rinmasa: xabar yozish maydonidagi 📎 belgini bosib, "
        "«Location» ni tanlang.",
        parse_mode="HTML",
        reply_markup=share_location_kb(),
    )
    return GET_LOCATION


# ── 5. Location ───────────────────────────────────────────────────────

async def step_get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message

    if msg.location:
        _ctx(context)["lat"] = msg.location.latitude
        _ctx(context)["lon"] = msg.location.longitude
        await msg.reply_text(
            "✅ Lokatsiya qabul qilindi!\n\n"
            "📝 Manzilni aniqlashtirish uchun izoh yozing (ko'cha, uy raqami).\n"
            "O'tkazib yuborish uchun: «-» yozing.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GET_ADDRESS

    if msg.text:
        if msg.text in ("❌ Bekor qilish", "/cancel"):
            await msg.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_kb())
            _clear(context)
            return ConversationHandler.END

    # Lokatsiya kelgmadi — qayta so'ra
    await msg.reply_text(
        "⚠️ Lokatsiya yuborilmadi.\n"
        "«📍 Lokatsiyani ulashish» tugmasini bosing:\n\n"
        "_Agar tugma ko'rinmasa: xabar yozish maydonidagi 📎 belgini bosib, "
        "«Location» ni tanlang._",
        parse_mode="HTML",
        reply_markup=share_location_kb(),
    )
    return GET_LOCATION


# ── 6. Address ────────────────────────────────────────────────────────

async def step_get_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text and text not in ("-", ".", "skip", "o'tkazib yuborish"):
        _ctx(context)["address_text"] = text
    return await _finalize(update, context)


# ── Finalize ──────────────────────────────────────────────────────────

async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_user = update.effective_user
    data    = _ctx(context)
    msg     = update.message

    # Session ichida hamma narsani yig'amiz — DTO ham shu yerda yasaladi
    courier_data = None

    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id)
        cart = await get_cart_with_items(session, tg_user.id)

        if not cart or not cart.items:
            await msg.reply_text("❌ Savatcha bo'sh.", reply_markup=main_menu_kb())
            _clear(context)
            return ConversationHandler.END

        order = await create_order(
            session=session,
            user=user,
            cart=cart,
            delivery_type=data["delivery_type"],
            phone=data["phone"],
            address_text=data.get("address_text"),
            lat=data.get("lat"),
            lon=data.get("lon"),
        )

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Order).where(Order.id == order.id)
            .options(selectinload(Order.items), selectinload(Order.user))
        )
        order = result.scalar_one()

        # Kerakli maydonlarni local o'zgaruvchilarga ko'chirish
        order_id     = order.id
        order_status = order.status
        order_lat    = order.lat
        order_lon    = order.lon
        admin_text   = fmt_order_for_admin(order)

    # ── Xaridorga tasdiqlash ──────────────────────────────────────────
    delivery_label = "🚚 Yetkazib berish" if data["delivery_type"] == DeliveryType.DELIVERY else "🏠 Olib ketish"
    await msg.reply_text(
        f"🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🔢 Buyurtma №: <b>{order_id}</b>\n"
        f"📍 Tur: {delivery_label}\n"
        f"💵 To'lov: Naqd\n\n"
        f"Operatorimiz siz bilan tez orada bog'lanadi. Rahmat! 🙏",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )

    # ── Adminlarga xabar ─────────────────────────────────────────────
    from keyboards.admin_kb import order_status_actions_kb
    for admin_id in config.ADMIN_IDS:
        try:
            if order_lat and order_lon:
                await context.bot.send_location(
                    chat_id=admin_id, latitude=order_lat, longitude=order_lon
                )
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="HTML",
                reply_markup=order_status_actions_kb(order_id, order_status),
                disable_web_page_preview=True,
            )
        except Exception as ex:
            logger.warning(f"Admin {admin_id} ga xabar: {ex}")

    # Kuryer guruhiga xabar endi admin "Qabul qilindi" bosgandan keyin yuboriladi
    # checkout.py da faqat admin va xaridorga xabar yuboriladi

    _clear(context)
    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────────

async def cancel_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _clear(context)
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_kb())
    return ConversationHandler.END


def build_checkout_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_checkout, pattern=r"^checkout:start$")],
        states={
            CONFIRM: [
                CallbackQueryHandler(step_confirm, pattern=r"^co_(ok|cancel)$"),
            ],
            DELIVERY_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_delivery_type),
            ],
            GET_PHONE: [
                MessageHandler(filters.CONTACT, step_get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_get_phone),
            ],
            GET_LOCATION: [
                MessageHandler(filters.LOCATION, step_get_location),  # birinchi!
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_get_location),
            ],
            GET_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, step_get_address),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_checkout),
            CommandHandler("start", cancel_checkout),
            MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_checkout),
        ],
        conversation_timeout=900,
        allow_reentry=True,
        name="checkout",
    )
