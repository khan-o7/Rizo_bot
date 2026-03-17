"""Admin ombor — stok ko'rinishi."""
from __future__ import annotations
from utils.filters import PRIVATE_ONLY
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from config import config
from db.session import get_session
from services.product_service import get_warehouse_stats

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 5  # kam qolganlar uchun ogohlantirish


async def show_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    async with get_session() as session:
        stats = await get_warehouse_stats(session)

    if not stats:
        await update.message.reply_text("📭 Hali mahsulotlar qo'shilmagan.")
        return

    lines = ["🏪 <b>Ombor holati</b>\n"]
    low_lines = []
    for p in stats:
        status_icon = "✅" if p["active"] else "❌"
        stock = p["stock"]
        stock_icon = "🔴" if stock == 0 else ("🟡" if stock <= LOW_STOCK_THRESHOLD else "🟢")
        line = (
            f"{stock_icon} {status_icon} <b>{p['name']}</b>\n"
            f"   📦 Qoldiq: <b>{stock} kg</b>  |  "
            f"🛒 Sotilgan: {p['sold']} dona\n"
            f"   💰 Narxi: {p['price']:,.0f} so'm  |  "
            f"📁 {p['category']}"
        )
        lines.append(line)
        if stock <= LOW_STOCK_THRESHOLD:
            low_lines.append(f"• {p['name']} — {stock} kg")

    if low_lines:
        lines.append(
            "\n⚠️ <b>Kam qolgan mahsulotlar:</b>\n" + "\n".join(low_lines)
        )

    total_products = len(stats)
    out_of_stock = sum(1 for p in stats if p["stock"] == 0)
    lines.append(
        f"\n📊 Jami: {total_products} mahsulot  |  "
        f"🔴 Tugagan: {out_of_stock} ta"
    )

    # Telegram xabar 4096 belgidan oshmasligi uchun bo'laklarga ajratamiz
    text = "\n\n".join(lines)
    if len(text) <= 4000:
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        # Bo'laklash
        chunk, chunks = [], []
        chunk.append(lines[0])
        for line in lines[1:]:
            if sum(len(l) for l in chunk) + len(line) > 3500:
                chunks.append("\n\n".join(chunk))
                chunk = []
            chunk.append(line)
        if chunk:
            chunks.append("\n\n".join(chunk))
        for part in chunks:
            await update.message.reply_text(part, parse_mode="HTML")


def register_warehouse_handlers(app) -> None:
    app.add_handler(MessageHandler(PRIVATE_ONLY & filters.Regex("^🏪 Ombor$"), show_warehouse))
