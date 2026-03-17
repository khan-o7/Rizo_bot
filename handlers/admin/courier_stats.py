"""Admin — kuryer statistikasi."""
from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from config import config
from db.session import get_session
from services.order_service import get_courier_stats
from utils.filters import PRIVATE_ONLY
from utils.formatters import fmt_price

logger = logging.getLogger(__name__)


async def show_courier_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in config.ADMIN_IDS:
        return

    async with get_session() as session:
        stats = await get_courier_stats(session)

    if not stats:
        await update.message.reply_text(
            "🚴 <b>Kuryer statistikasi</b>\n\n📭 Hali birorta kuryer buyurtma qabul qilmagan.",
            parse_mode="HTML",
        )
        return

    lines = ["🚴 <b>Kuryer statistikasi</b>\n"]
    total_delivered = 0
    total_accepted  = 0

    for i, c in enumerate(stats, 1):
        delivered = c["total_delivered"]
        accepted  = c["total_accepted"]
        in_prog   = c["in_progress"]
        total_delivered += delivered
        total_accepted  += accepted

        if delivered == accepted:
            efficiency = "100%"
        elif accepted > 0:
            efficiency = f"{delivered / accepted * 100:.0f}%"
        else:
            efficiency = "—"

        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
        lines.append(
            f"{medal} <b>{c['name']}</b>\n"
            f"   ✅ Yetkazilgan: <b>{delivered}</b>  |  "
            f"📦 Qabul: {accepted}  |  "
            f"🚚 Jarayonda: {in_prog}\n"
            f"   📊 Samaradorlik: {efficiency}"
        )

    lines += [
        "",
        f"📈 <b>Jami:</b> {total_accepted} qabul  |  {total_delivered} yetkazilgan",
        f"👷 Faol kuryer'lar: {len(stats)} ta",
    ]

    await update.message.reply_text("\n\n".join(lines), parse_mode="HTML")


def register_courier_stats_handlers(app) -> None:
    app.add_handler(MessageHandler(
        PRIVATE_ONLY & filters.Regex("^🚴 Kuryer statistikasi$"),
        show_courier_stats,
    ))
