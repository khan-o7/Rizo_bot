"""
Admin — oylik va yillik arxiv statistikasi.

Tugmalar:
  📅 Oylik statistika  — oxirgi 12+ oy
  📆 Yillik statistika — barcha yillar
"""
from __future__ import annotations
import logging
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import config
from db.session import get_session
from services.archive_service import (
    MONTH_NAMES,
    get_current_month_stats, get_current_year_stats,
    get_monthly_archive, get_yearly_archive,
)
from utils.filters import PRIVATE_ONLY
from utils.formatters import fmt_price

logger = logging.getLogger(__name__)


def _month_row(r, is_current: bool = False) -> str:
    label = MONTH_NAMES.get(r["month"] if isinstance(r, dict) else r.month, "?")
    year  = r["year"] if isinstance(r, dict) else r.year
    total = r["total_orders"] if isinstance(r, dict) else r.total_orders
    done  = r["done_orders"]  if isinstance(r, dict) else r.done_orders
    canc  = r["canceled_orders"] if isinstance(r, dict) else r.canceled_orders
    rev   = r["total_revenue"] if isinstance(r, dict) else float(r.total_revenue)
    new_u = r["new_users"]    if isinstance(r, dict) else r.new_users

    cur = " 🔴 joriy" if is_current else ""
    eff = f"{done/total*100:.0f}%" if total > 0 else "—"
    return (
        f"📅 <b>{label} {year}</b>{cur}\n"
        f"   📦 Buyurtmalar: <b>{total}</b>  ✅ {done}  ❌ {canc}\n"
        f"   💰 Daromad: <b>{fmt_price(rev)}</b>  |  📊 {eff}\n"
        f"   👤 Yangi foydalanuvchilar: {new_u}"
    )


def _year_row(r, is_current: bool = False) -> str:
    year  = r["year"]  if isinstance(r, dict) else r.year
    total = r["total_orders"] if isinstance(r, dict) else r.total_orders
    done  = r["done_orders"]  if isinstance(r, dict) else r.done_orders
    canc  = r["canceled_orders"] if isinstance(r, dict) else r.canceled_orders
    rev   = r["total_revenue"] if isinstance(r, dict) else float(r.total_revenue)
    new_u = r["new_users"]    if isinstance(r, dict) else r.new_users
    best  = None if isinstance(r, dict) else r.best_month
    if isinstance(r, dict):
        best = None  # joriy yil uchun best_month hisoblanmaydi real-time

    cur = " 🔴 joriy" if is_current else ""
    eff = f"{done/total*100:.0f}%" if total > 0 else "—"
    best_str = f"  |  🏆 Eng yaxshi oy: {MONTH_NAMES.get(best, '?')}" if best else ""
    return (
        f"📆 <b>{year} yil</b>{cur}\n"
        f"   📦 Buyurtmalar: <b>{total}</b>  ✅ {done}  ❌ {canc}\n"
        f"   💰 Daromad: <b>{fmt_price(rev)}</b>  |  📊 {eff}{best_str}\n"
        f"   👤 Yangi foydalanuvchilar: {new_u}"
    )


def _archive_nav_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 Oylik", callback_data="arch:monthly:0"),
        InlineKeyboardButton("📆 Yillik", callback_data="arch:yearly"),
    ]])


def _monthly_nav_kb(offset: int, has_more: bool) -> InlineKeyboardMarkup:
    btns = []
    row = []
    if offset > 0:
        row.append(InlineKeyboardButton("⬅️ Yangi", callback_data=f"arch:monthly:{max(0, offset-6)}"))
    if has_more:
        row.append(InlineKeyboardButton("Eski ➡️", callback_data=f"arch:monthly:{offset+6}"))
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton("📆 Yillik ko'rinish", callback_data="arch:yearly")])
    return InlineKeyboardMarkup(btns)


# ── Handlers ──────────────────────────────────────────────────────────

async def show_archive_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    await update.message.reply_text(
        "📊 <b>Arxiv statistikasi</b>\n\nQaysi davrni ko'rmoqchisiz?",
        parse_mode="HTML",
        reply_markup=_archive_nav_kb(),
    )


async def cbq_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id not in config.ADMIN_IDS:
        await query.answer("Ruxsat yo'q")
        return
    await query.answer()

    offset = int(query.data.split(":")[2])
    PAGE   = 6

    async with get_session() as session:
        archived = list(await get_monthly_archive(session, limit=48))
        current  = await get_current_month_stats(session)

    has_more = len(archived) > offset + PAGE
    page_items = archived[offset : offset + PAGE]

    lines = ["📅 <b>Oylik statistika</b>\n"]

    # Joriy oy — faqat birinchi sahifada
    if offset == 0:
        lines.append(_month_row(current, is_current=True))
        lines.append("")

    for rec in page_items:
        lines.append(_month_row(rec))
        lines.append("")

    if not page_items and offset == 0:
        lines.append("📭 Hali arxiv ma'lumotlari yo'q.\nBirinchi arxiv keyingi oyda yaratiladi.")

    text = "\n".join(lines).strip()
    kb   = _monthly_nav_kb(offset, has_more)

    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


async def cbq_yearly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id not in config.ADMIN_IDS:
        await query.answer("Ruxsat yo'q")
        return
    await query.answer()

    async with get_session() as session:
        archived = list(await get_yearly_archive(session))
        current  = await get_current_year_stats(session)

    lines = ["📆 <b>Yillik statistika</b>\n"]
    lines.append(_year_row(current, is_current=True))
    lines.append("")

    for rec in archived:
        lines.append(_year_row(rec))
        lines.append("")

    if not archived:
        lines.append("📭 Hali yillik arxiv yo'q.\nBirinchi arxiv yanvar oyida yaratiladi.")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 Oylik ko'rinish", callback_data="arch:monthly:0")
    ]])
    try:
        await query.edit_message_text("\n".join(lines).strip(), parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


def register_archive_handlers(app) -> None:
    app.add_handler(MessageHandler(
        PRIVATE_ONLY & filters.Regex("^📊 Arxiv statistika$"),
        show_archive_menu,
    ))
    app.add_handler(CallbackQueryHandler(cbq_monthly, pattern=r"^arch:monthly:\d+$"))
    app.add_handler(CallbackQueryHandler(cbq_yearly,  pattern=r"^arch:yearly$"))
