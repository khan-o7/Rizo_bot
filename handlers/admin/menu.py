"""Admin statistika va bog'lanish."""
from __future__ import annotations
from utils.filters import PRIVATE_ONLY
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from config import config
from db.session import get_session
from services.order_service import stats_today
from services.product_service import top_products

logger = logging.getLogger(__name__)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    async with get_session() as session:
        stats = await stats_today(session)
        tops = await top_products(session, limit=5)

    top_lines = "\n".join(
        [f"  {i+1}. {p['name']} — {p['qty']} dona" for i, p in enumerate(tops)]
    ) or "  (ma'lumot yo'q)"

    await update.message.reply_text(
        f"📊 <b>Statistika</b>\n\n"
        f"📅 Bugungi buyurtmalar: <b>{stats['today']}</b>\n"
        f"📦 Jami buyurtmalar: <b>{stats['total']}</b>\n"
        f"💰 Jami daromad: <b>{stats['revenue']:,.0f} so'm</b>\n\n"
        f"🏆 <b>Top mahsulotlar:</b>\n{top_lines}",
        parse_mode="HTML",
    )


async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📞 <b>Bog'lanish</b>\n\n"
        "📱 Telefon: +998 (33) 336-63-36\n +998 (97) 520-20-27 \n"
        "💬 Telegram: @rizo_kolbasa\n @rizo_xorazm \n"
        "🕐 Ish vaqti: 9:00 – 21:00",
        parse_mode="HTML",
    )


def register_admin_menu_handlers(app) -> None:
    app.add_handler(MessageHandler(PRIVATE_ONLY & filters.Regex("^📊 Statistika$"), admin_stats))
    app.add_handler(MessageHandler(filters.Regex("^📞 Bog'lanish$"), contact_info))
