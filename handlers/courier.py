"""
Kuryer guruhi handlerlari.

Callbacklar (inline buttons):
  courier_accept:<order_id>   — kuryer qabul qildi
  courier_done:<order_id>     — kuryer yetkazdi

Buyruq (faqat kuryer guruhida):
  /mening_buyurtmalarim       — kuryer o'z statistikasini ko'radi
"""
from __future__ import annotations
import html
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from config import config
from db.models import Order, OrderStatus
from db.session import get_session
from keyboards.admin_kb import courier_delivered_kb
from services.courier_service import build_courier_data, fmt_courier_message
from services.order_service import (
    assign_courier, get_order, get_courier_orders,
    mark_delivered, save_courier_msg_id,
)
from utils.filters import GROUP_ONLY
from utils.formatters import fmt_price

logger = logging.getLogger(__name__)


def e(t: str) -> str:
    return html.escape(str(t))


# ─────────────────────────────────────────────────────────────────────
# Kuryer qabul qilish tugmasi
# ─────────────────────────────────────────────────────────────────────

async def cbq_courier_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query    = update.callback_query
    user     = update.effective_user
    order_id = int(query.data.split(":")[1])

    courier_name  = user.full_name or user.username or str(user.id)
    courier_text  = None

    async with get_session() as session:
        order = await get_order(session, order_id)
        if order is None:
            await query.answer("❌ Buyurtma topilmadi.", show_alert=True)
            return

        if order.courier_tg_id and order.courier_tg_id != user.id:
            await query.answer(
                f"❌ Bu buyurtmani '{order.courier_name}' allaqachon qabul qilgan!",
                show_alert=True,
            )
            return

        if order.status in (OrderStatus.DONE, OrderStatus.CANCELED):
            await query.answer("ℹ️ Bu buyurtma allaqachon yakunlangan.", show_alert=True)
            return

        order = await assign_courier(session, order_id, user.id, courier_name)

        res = await session.execute(
            select(Order).where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.user))
        )
        order      = res.scalar_one()
        c_data     = build_courier_data(order)
        courier_text = fmt_courier_message(c_data)

    try:
        await query.edit_message_text(
            text=courier_text + f"\n\n🚴 <b>Kuryer:</b> {e(courier_name)} — Qabul qilindi ✅",
            parse_mode="HTML",
            reply_markup=courier_delivered_kb(order_id),
            disable_web_page_preview=True,
        )
        await query.answer(f"✅ Buyurtma #{order_id} qabul qilindi!")
    except Exception as ex:
        logger.warning(f"Guruh xabarini edit: {ex}")
        await query.answer("✅ Qabul qilindi!")

    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🚴 <b>Kuryer buyurtmani qabul qildi!</b>\n\n"
                    f"👷 Kuryer: <b>{e(courier_name)}</b>\n"
                    f"🆔 ID: <code>{user.id}</code>\n"
                    f"📦 Buyurtma: <b>#{order_id}</b>\n"
                    f"📌 Status: 🚚 Yetkazilmoqda"
                ),
                parse_mode="HTML",
            )
        except Exception as ex:
            logger.warning(f"Admin {admin_id}: {ex}")


# ─────────────────────────────────────────────────────────────────────
# Kuryer yetkazdi tugmasi
# ─────────────────────────────────────────────────────────────────────

async def cbq_courier_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query    = update.callback_query
    user     = update.effective_user
    order_id = int(query.data.split(":")[1])

    courier_name = None
    client_tg_id = None
    courier_text = None

    async with get_session() as session:
        order = await get_order(session, order_id)
        if order is None:
            await query.answer("❌ Buyurtma topilmadi.", show_alert=True)
            return

        if order.courier_tg_id and order.courier_tg_id != user.id:
            await query.answer("❌ Siz bu buyurtmani qabul qilmagansiz!", show_alert=True)
            return

        if order.status == OrderStatus.DONE:
            await query.answer("ℹ️ Allaqachon yetkazilgan.", show_alert=True)
            return

        if order.status == OrderStatus.CANCELED:
            await query.answer("❌ Buyurtma bekor qilingan.", show_alert=True)
            return

        courier_name = order.courier_name or user.full_name or str(user.id)
        order = await mark_delivered(session, order_id)

        res = await session.execute(
            select(Order).where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.user))
        )
        order        = res.scalar_one()
        c_data       = build_courier_data(order)
        courier_text = fmt_courier_message(c_data)
        client_tg_id = order.user.tg_id

    try:
        await query.edit_message_text(
            text=courier_text
                 + f"\n\n✅ <b>Yetkazib berildi!</b>\n🚴 Kuryer: <b>{e(courier_name)}</b>",
            parse_mode="HTML",
            reply_markup=None,
            disable_web_page_preview=True,
        )
        await query.answer(f"✅ Buyurtma #{order_id} yetkazildi!")
    except Exception as ex:
        logger.warning(f"Guruh xabarini edit: {ex}")
        await query.answer("✅ Yetkazildi!")

    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"✅ <b>Buyurtma yetkazib berildi!</b>\n\n"
                    f"📦 Buyurtma: <b>#{order_id}</b>\n"
                    f"🚴 Kuryer: <b>{e(courier_name)}</b>"
                ),
                parse_mode="HTML",
            )
        except Exception as ex:
            logger.warning(f"Admin {admin_id}: {ex}")

    if client_tg_id:
        try:
            await context.bot.send_message(
                chat_id=client_tg_id,
                text=(
                    f"✅ <b>Buyurtma #{order_id} yetkazib berildi!</b>\n\n"
                    "Xarid uchun rahmat! 🙏\n"
                    "Yana buyurtma berish uchun /start bosing."
                ),
                parse_mode="HTML",
            )
        except Exception as ex:
            logger.warning(f"Xaridorga xabar: {ex}")


# ─────────────────────────────────────────────────────────────────────
# /mening_buyurtmalarim — faqat kuryer guruhida
# ─────────────────────────────────────────────────────────────────────

async def cmd_my_deliveries(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kuryer guruhida /mening_buyurtmalarim buyrug'i."""
    # Faqat to'g'ri guruhdan ishlashi kerak
    chat = update.effective_chat
    if config.has_courier_group() and chat.id != config.COURIER_GROUP_ID:
        return  # boshqa guruhda jim turamiz

    user = update.effective_user
    tg_id = user.id
    courier_name = user.full_name or user.username or str(tg_id)

    async with get_session() as session:
        orders = await get_courier_orders(session, tg_id, limit=50)

    if not orders:
        await update.message.reply_text(
            f"📭 <b>{e(courier_name)}</b>, siz hali birorta buyurtma qabul qilmagansiz.",
            parse_mode="HTML",
        )
        return

    total     = len(orders)
    delivered = sum(1 for o in orders if o.status == OrderStatus.DONE)
    in_prog   = sum(1 for o in orders if o.status == OrderStatus.PROCESSING)
    canceled  = sum(1 for o in orders if o.status == OrderStatus.CANCELED)

    # Xaridor tomonidan tasdiqlangan: yetkazib berilgan (DONE) = xaridor qabul qildi
    # (Status DONE = kuryer yetkazdi + xaridor qabul qildi hisoblanadi)
    confirmed = delivered  # bu yerda DONE = yetkazildi = qabul qilindi

    if delivered > 0 and total > 0:
        efficiency = f"{delivered / total * 100:.0f}%"
    else:
        efficiency = "—"

    lines = [
        f"🚴 <b>{e(courier_name)}</b> — Mening statistikam\n",
        f"📦 Jami qabul qilgan:    <b>{total}</b>",
        f"✅ Yetkazib bergan:       <b>{delivered}</b>",
        f"✔️ Xaridor qabul qilgan: <b>{confirmed}</b>",
        f"🚚 Jarayondagi:          <b>{in_prog}</b>",
        f"❌ Bekor qilingan:        <b>{canceled}</b>",
        f"📊 Samaradorlik:          <b>{efficiency}</b>",
    ]

    # So'nggi 5 ta buyurtma
    if orders:
        lines.append("\n🕐 <b>Oxirgi buyurtmalar:</b>")
        status_icons = {
            OrderStatus.DONE:       "✅",
            OrderStatus.PROCESSING: "🚚",
            OrderStatus.CANCELED:   "❌",
            OrderStatus.NEW:        "🆕",
        }
        for o in orders[:5]:
            icon  = status_icons.get(o.status, "•")
            date  = o.created_at.strftime("%d.%m %H:%M")
            total_price = fmt_price(float(o.total_price))
            lines.append(f"{icon} #{o.id} — {date} — {total_price}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def register_courier_handlers(app) -> None:
    # Inline buttons — guruhdan keladi
    app.add_handler(CallbackQueryHandler(
        cbq_courier_accept, pattern=r"^courier_accept:\d+$"
    ))
    app.add_handler(CallbackQueryHandler(
        cbq_courier_done, pattern=r"^courier_done:\d+$"
    ))
    # Buyruq — faqat guruhda
    app.add_handler(CommandHandler(
        "mening_buyurtmalarim",
        cmd_my_deliveries,
        filters=GROUP_ONLY,
    ))
