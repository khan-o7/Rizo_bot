"""
Admin buyurtmalar paneli.
  — "Qabul qilindi" bosilganda → kuryer guruhiga xabar yuboriladi
  — Status qayta bosilmasin (noop tekshiruvi)
  — Bekor qilish → majburiy izoh (ConversationHandler)
"""
from __future__ import annotations
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters,
)

from config import config
from db.models import Order, OrderStatus
from db.session import get_session
from keyboards.admin_kb import (
    STATUS_EMOJI, STATUS_LABELS,
    admin_orders_filter_kb, order_status_actions_kb,
    courier_accept_kb,
)
from services.order_service import (
    get_orders_by_status, save_courier_msg_id, update_order_status,
)
from utils.filters import PRIVATE_ONLY
from utils.formatters import fmt_order_for_admin
from utils.tg_helpers import safe_edit

logger = logging.getLogger(__name__)

WAIT_CANCEL_REASON = 10
_KEY = "adm_cancel"

FILTER_TITLES = {
    "new":        ("🆕", "Yangi buyurtmalar"),
    "processing": ("🚚", "Yetkazib berilmoqda"),
    "done":       ("✅", "Muvaffaqiyatli yakunlangan"),
    "canceled":   ("❌", "Bekor qilingan buyurtmalar"),
    "all":        ("📋", "Barcha buyurtmalar"),
}


# ── Menyu ─────────────────────────────────────────────────────────────

async def admin_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    await update.message.reply_text(
        "📦 <b>Buyurtmalar</b>\nQaysi statusdagilarni ko'rmoqchisiz?",
        parse_mode="HTML",
        reply_markup=admin_orders_filter_kb(),
    )


async def cbq_orders_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    status_str = query.data.split(":")[1]
    status_map = {
        "new": OrderStatus.NEW, "processing": OrderStatus.PROCESSING,
        "done": OrderStatus.DONE, "canceled": OrderStatus.CANCELED, "all": None,
    }
    status = status_map.get(status_str)
    async with get_session() as session:
        orders = await get_orders_by_status(session, status, limit=20)
    emoji, title = FILTER_TITLES.get(status_str, ("📋", "Buyurtmalar"))
    if not orders:
        await safe_edit(
            query.message,
            f"{emoji} <b>{title}</b>\n\n📭 Hech qanday buyurtma topilmadi.",
            reply_markup=admin_orders_filter_kb(),
        )
        return
    await safe_edit(
        query.message,
        f"{emoji} <b>{title}</b> — {len(orders)} ta",
        reply_markup=admin_orders_filter_kb(),
    )
    for order in orders:
        await query.message.reply_text(
            fmt_order_for_admin(order, show_status=True),
            parse_mode="HTML",
            reply_markup=order_status_actions_kb(order.id, order.status),
            disable_web_page_preview=True,
        )


async def cbq_orders_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.reply_text(
        "📦 <b>Buyurtmalar</b>\nQaysi statusdagilarni ko'rmoqchisiz?",
        parse_mode="HTML",
        reply_markup=admin_orders_filter_kb(),
    )


# ── Status o'zgartirish ───────────────────────────────────────────────

async def cbq_order_status_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ord_status:<order_id>:<status> — bekor bundan mustasno."""
    query = update.callback_query

    if query.data == "noop":
        await query.answer("ℹ️ Buyurtma allaqachon shu statusda.", show_alert=False)
        return

    await query.answer()
    parts          = query.data.split(":")
    order_id       = int(parts[1])
    new_status_str = parts[2]

    status_map = {"processing": OrderStatus.PROCESSING, "done": OrderStatus.DONE, "new": OrderStatus.NEW}
    new_status = status_map.get(new_status_str, OrderStatus.PROCESSING)

    courier_data  = None
    user_tg_id    = None
    order_lat     = None
    order_lon     = None

    async with get_session() as session:
        from services.order_service import get_order as _get
        current = await _get(session, order_id)
        if current is None:
            await query.answer("❌ Buyurtma topilmadi.", show_alert=True)
            return
        if current.status == new_status:
            await query.answer("ℹ️ Buyurtma allaqachon shu statusda.", show_alert=True)
            return

        order = await update_order_status(session, order_id, new_status)
        res   = await session.execute(
            select(Order).where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.user))
        )
        order = res.scalar_one()

        # Guruhga yuborish uchun ma'lumot — faqat PROCESSING ga o'tganda
        if new_status == OrderStatus.PROCESSING and config.has_courier_group():
            from db.models import DeliveryType
            if order.delivery_type == DeliveryType.DELIVERY:
                from services.courier_service import build_courier_data
                courier_data = build_courier_data(order)
                order_lat    = order.lat
                order_lon    = order.lon

        user_tg_id  = order.user.tg_id
        admin_text  = fmt_order_for_admin(order, show_status=True)

    # ── Admin xabarini yangilash ──────────────────────────────────────
    await safe_edit(
        query.message,
        admin_text,
        reply_markup=order_status_actions_kb(order_id, new_status),
    )

    # ── Xaridorga bildirishnoma ───────────────────────────────────────
    label = STATUS_LABELS[new_status]
    emoji = STATUS_EMOJI[new_status]
    try:
        await context.bot.send_message(
            chat_id=user_tg_id,
            text=f"📦 <b>Buyurtma #{order_id}</b>\nHolat: {emoji} <b>{label}</b>",
            parse_mode="HTML",
        )
    except Exception as ex:
        logger.warning(f"User notify: {ex}")

    # ── Kuryer guruhiga xabar — faqat PROCESSING va DELIVERY ─────────
    if courier_data is not None:
        from services.courier_service import send_to_courier_group
        logger.info(f"Buyurtma #{order_id} kuryer guruhiga yuborilmoqda (admin tasdiqladi)...")

        sent_msg_id = await send_to_courier_group(
            bot=context.bot,
            group_id=config.COURIER_GROUP_ID,
            order_id=order_id,
            courier_data=courier_data,
            accept_kb=courier_accept_kb(order_id),
        )

        if sent_msg_id:
            async with get_session() as session:
                await save_courier_msg_id(session, order_id, sent_msg_id)
            logger.info(f"✅ Buyurtma #{order_id} kuryer guruhiga yuborildi!")
        else:
            # Admin ogohlantirish
            try:
                await query.message.reply_text(
                    f"⚠️ <b>Diqqat!</b> Buyurtma #{order_id} kuryer guruhiga "
                    f"<b>yuborilmadi</b>!\n"
                    f"Guruh ID: <code>{config.COURIER_GROUP_ID}</code>\n\n"
                    "• Bot guruhga qo'shilganmi?\n"
                    "• Bot xabar yubora oladimi?\n"
                    "• COURIER_GROUP_ID to'g'rimi? (minus bilan boshlanishi kerak)",
                    parse_mode="HTML",
                )
            except Exception:
                pass


# ── Bekor qilish (ConversationHandler) ────────────────────────────────

async def cbq_cancel_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query    = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])

    async with get_session() as session:
        from services.order_service import get_order as _get
        order = await _get(session, order_id)
        if order and order.status == OrderStatus.CANCELED:
            await query.answer("ℹ️ Buyurtma allaqachon bekor qilingan.", show_alert=True)
            return ConversationHandler.END

    context.user_data[_KEY] = {"order_id": order_id}
    await query.message.reply_text(
        f"❌ <b>Buyurtma #{order_id}</b> ni bekor qilish\n\n"
        "💬 <b>Sababini yozing</b> (xaridorga jo'natiladi):\n\n"
        "<i>Masalan: Mahsulot tugagan, yetkazib bo'lmaydi...</i>",
        parse_mode="HTML",
    )
    return WAIT_CANCEL_REASON


async def cancel_reason_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reason = update.message.text.strip()
    if len(reason) < 3:
        await update.message.reply_text("⚠️ Sabab juda qisqa. Batafsil yozing:")
        return WAIT_CANCEL_REASON

    data     = context.user_data.pop(_KEY, {})
    order_id = data.get("order_id")
    if not order_id:
        await update.message.reply_text("❌ Xatolik. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    async with get_session() as session:
        order = await update_order_status(
            session, order_id, OrderStatus.CANCELED,
            cancel_reason=reason, canceled_by="admin",
        )
        if order is None:
            await update.message.reply_text("❌ Buyurtma topilmadi.")
            return ConversationHandler.END
        res = await session.execute(
            select(Order).where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.user))
        )
        order    = res.scalar_one()
        user_tg  = order.user.tg_id

    await update.message.reply_text(
        f"✅ Buyurtma #{order_id} bekor qilindi.\n💬 Sabab: <i>{reason}</i>",
        parse_mode="HTML",
    )
    try:
        await context.bot.send_message(
            chat_id=user_tg,
            text=(
                f"❌ <b>Buyurtma #{order_id}</b> bekor qilindi\n\n"
                f"💬 <b>Sabab:</b> <i>{reason}</i>\n\n"
                "Savollar bo'lsa, do'kon bilan bog'laning. 🙏"
            ),
            parse_mode="HTML",
        )
    except Exception as ex:
        logger.warning(f"User cancel notify: {ex}")
    return ConversationHandler.END


async def cancel_reason_abort(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop(_KEY, None)
    msg = (update.message
           or (update.callback_query and update.callback_query.message))
    if msg:
        await msg.reply_text("❌ Bekor qilish to'xtatildi.")
    return ConversationHandler.END


def build_admin_cancel_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(
            cbq_cancel_order_start, pattern=r"^ord_cancel:\d+$"
        )],
        states={
            WAIT_CANCEL_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_reason_received),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_reason_abort),
            CallbackQueryHandler(cancel_reason_abort, pattern=r"^adm:cancel$"),
        ],
        conversation_timeout=120,
        allow_reentry=True,
        name="admin_cancel_order",
    )


def register_admin_order_handlers(app) -> None:
    app.add_handler(build_admin_cancel_conv())
    app.add_handler(MessageHandler(
        PRIVATE_ONLY & filters.Regex("^📦 Buyurtmalar$"), admin_orders_menu
    ))
    app.add_handler(CallbackQueryHandler(
        cbq_orders_filter,
        pattern=r"^adm_orders:(new|processing|done|canceled|all)$",
    ))
    app.add_handler(CallbackQueryHandler(cbq_orders_back, pattern=r"^adm_orders:back$"))
    app.add_handler(CallbackQueryHandler(
        cbq_order_status_change,
        pattern=r"^(ord_status:\d+:(processing|done|new)|noop)$",
    ))
