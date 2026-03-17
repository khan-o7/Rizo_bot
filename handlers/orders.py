"""
Foydalanuvchi buyurtmalari tarixi + o'zi bekor qilish.
Bekor qilish — faqat NEW status, majburiy sabab kiritish.
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
from keyboards.user_kb import main_menu_kb, user_order_kb
from services.order_service import can_user_cancel, get_user_orders, update_order_status
from utils.filters import PRIVATE_ONLY
from utils.formatters import fmt_order_for_admin, fmt_order_for_user

logger = logging.getLogger(__name__)

WAIT_USER_CANCEL_REASON = 20
_KEY = "user_cancel"


async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    async with get_session() as session:
        orders = await get_user_orders(session, tg_id, limit=10)

    if not orders:
        await update.message.reply_text("📭 Hali buyurtma bermagansiz.")
        return

    await update.message.reply_text(f"📦 <b>Buyurtmalaringiz</b> ({len(orders)} ta):", parse_mode="HTML")
    for order in orders:
        kb = user_order_kb(order)
        await update.message.reply_text(
            fmt_order_for_user(order),
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=True,
        )


# ═══════════════════════════════════════════════════
#  FOYDALANUVCHI BEKOR QILISH — majburiy izoh
# ═══════════════════════════════════════════════════

async def cbq_user_cancel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """user_cancel:<order_id>"""
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split(":")[1])
    tg_id = update.effective_user.id

    async with get_session() as session:
        orders = await get_user_orders(session, tg_id)
        order = next((o for o in orders if o.id == order_id), None)

    if order is None:
        await query.message.reply_text("❌ Buyurtma topilmadi.")
        return ConversationHandler.END

    if not await can_user_cancel(order):
        await query.answer(
            "❌ Bu buyurtmani bekor qilib bo'lmaydi.\n"
            "Faqat 'Yangi' statusdagi buyurtmani bekor qilish mumkin.",
            show_alert=True,
        )
        return ConversationHandler.END

    context.user_data[_KEY] = {"order_id": order_id}
    await query.message.reply_text(
        f"❌ <b>Buyurtma #{order_id}</b> ni bekor qilmoqchisiz.\n\n"
        "💬 <b>Bekor qilish sababini yozing</b>:\n\n"
        "<i>Masalan: Fikrim o'zgardi, Boshqa joydan buyurtma berdim, va h.k.</i>",
        parse_mode="HTML",
    )
    return WAIT_USER_CANCEL_REASON


async def user_cancel_reason_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reason = update.message.text.strip()
    if len(reason) < 3:
        await update.message.reply_text("⚠️ Sabab juda qisqa. Iltimos, batafsil yozing:")
        return WAIT_USER_CANCEL_REASON

    data = context.user_data.pop(_KEY, {})
    order_id = data.get("order_id")
    if not order_id:
        await update.message.reply_text("❌ Xatolik yuz berdi.")
        return ConversationHandler.END

    tg_id = update.effective_user.id
    tg_user = update.effective_user

    async with get_session() as session:
        orders = await get_user_orders(session, tg_id)
        order = next((o for o in orders if o.id == order_id), None)
        if order is None or not await can_user_cancel(order):
            await update.message.reply_text("❌ Bu buyurtmani bekor qilib bo'lmaydi.")
            return ConversationHandler.END

        order = await update_order_status(
            session, order_id, OrderStatus.CANCELED,
            cancel_reason=reason, canceled_by="user",
        )
        res = await session.execute(
            select(Order).where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.user))
        )
        order = res.scalar_one()

    await update.message.reply_text(
        f"✅ <b>Buyurtma #{order_id}</b> bekor qilindi.\n"
        f"💬 Sabab: <i>{reason}</i>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )

    # Adminlarga xabar
    uname = f"@{tg_user.username}" if tg_user.username else str(tg_id)
    admin_text = (
        f"🔔 <b>Xaridor buyurtmani bekor qildi!</b>\n\n"
        f"👤 Xaridor: {tg_user.full_name or 'Nomsiz'} ({uname})\n"
        f"📦 Buyurtma: #{order_id}\n"
        f"💬 <b>Sabab:</b> <i>{reason}</i>\n\n"
        + fmt_order_for_admin(order, show_status=False)
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id, text=admin_text,
                parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception as ex:
            logger.warning(f"Admin {admin_id} notify: {ex}")

    return ConversationHandler.END


async def user_cancel_abort(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop(_KEY, None)
    await update.message.reply_text("↩️ Bekor qilish to'xtatildi.", reply_markup=main_menu_kb())
    return ConversationHandler.END


def build_user_cancel_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cbq_user_cancel_start, pattern=r"^user_cancel:\d+$")
        ],
        states={
            WAIT_USER_CANCEL_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_cancel_reason_received),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", user_cancel_abort),
            CommandHandler("start",  user_cancel_abort),
        ],
        conversation_timeout=120,
        allow_reentry=True,
        name="user_cancel_order",
    )


def register_orders_handlers(app) -> None:
    app.add_handler(build_user_cancel_conv())
    app.add_handler(MessageHandler(PRIVATE_ONLY & filters.Regex("^📦 Buyurtmalarim$"), show_orders))
