"""
Kuryer arxiv statistikasi.

Bot guruhida:
  /mening_statistikam oy   — oxirgi 6 oy
  /mening_statistikam yil  — barcha yillar
  /mening_statistikam      — ham oy, ham yil (qisqacha)

Admin (private):
  /kuryer_arxiv <tg_id>    — muayyan kuryer tarixi
"""
from __future__ import annotations
import logging
from datetime import date

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from config import config
from db.session import get_session
from services.archive_service import (
    MONTH_NAMES,
    get_courier_monthly_archive,
    get_courier_yearly_archive,
    get_current_month_stats,
)
from utils.filters import PRIVATE_ONLY
from utils.formatters import fmt_price

logger = logging.getLogger(__name__)
GROUP_ONLY = filters.ChatType.GROUPS


def _eff(accepted: int, delivered: int) -> str:
    if accepted == 0:
        return "—"
    return f"{delivered / accepted * 100:.0f}%"


def _courier_monthly_block(records, courier_name: str = "") -> str:
    lines = [f"🚴 <b>{courier_name} — Oylik statistika</b>\n"] if courier_name else ["🚴 <b>Oylik statistika</b>\n"]
    if not records:
        lines.append("📭 Hali arxiv ma'lumotlari yo'q.")
        return "\n".join(lines)
    total_acc = total_del = 0
    for r in records:
        acc = r.total_accepted
        dld = r.total_delivered
        total_acc += acc
        total_del += dld
        lines.append(
            f"📅 <b>{MONTH_NAMES[r.month]} {r.year}</b>\n"
            f"   📦 Qabul: {acc}  ✅ Yetkazilgan: {dld}  📊 {_eff(acc, dld)}"
        )
    lines.append(f"\n📈 <b>Jami:</b> {total_acc} qabul | {total_del} yetkazilgan | {_eff(total_acc, total_del)}")
    return "\n".join(lines)


def _courier_yearly_block(records, courier_name: str = "") -> str:
    lines = [f"🚴 <b>{courier_name} — Yillik statistika</b>\n"] if courier_name else ["🚴 <b>Yillik statistika</b>\n"]
    if not records:
        lines.append("📭 Hali yillik arxiv yo'q.")
        return "\n".join(lines)
    total_acc = total_del = 0
    for r in records:
        acc = r.total_accepted
        dld = r.total_delivered
        total_acc += acc
        total_del += dld
        lines.append(
            f"📆 <b>{r.year} yil</b>\n"
            f"   📦 Qabul: {acc}  ✅ Yetkazilgan: {dld}  📊 {_eff(acc, dld)}"
        )
    lines.append(f"\n📈 <b>Jami:</b> {total_acc} qabul | {total_del} yetkazilgan | {_eff(total_acc, total_del)}")
    return "\n".join(lines)


# ── Guruh ichida kuryer o'z statistikasini ko'radi ────────────────────

async def cmd_courier_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /mening_statistikam [oy|yil]
    Faqat kuryer guruhida ishlaydi.
    """
    tg_id = update.effective_user.id
    args  = context.args or []
    mode  = args[0].lower() if args else "all"

    async with get_session() as session:
        monthly = await get_courier_monthly_archive(session, tg_id, limit=12)
        yearly  = await get_courier_yearly_archive(session, tg_id)

    if mode == "oy":
        text = _courier_monthly_block(monthly)
    elif mode == "yil":
        text = _courier_yearly_block(yearly)
    else:
        # Joriy oy qo'shimcha
        today = date.today()
        m_txt = _courier_monthly_block(list(monthly)[:6])
        y_txt = _courier_yearly_block(list(yearly)[:3])
        text  = m_txt + "\n\n━━━━━━━━━━━━━━━━\n\n" + y_txt

    await update.message.reply_text(text, parse_mode="HTML")


# ── Admin: muayyan kuryer tarixi ──────────────────────────────────────

async def cmd_admin_courier_archive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /kuryer_arxiv <tg_id> [oy|yil]
    Private chat da adminlar uchun.
    """
    if update.effective_user.id not in config.ADMIN_IDS:
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Foydalanish: /kuryer_arxiv <tg_id> [oy|yil]\n"
            "Misol: /kuryer_arxiv 123456789 oy",
            parse_mode="HTML",
        )
        return

    try:
        tg_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri tg_id.")
        return

    mode = args[1].lower() if len(args) > 1 else "all"

    async with get_session() as session:
        monthly = await get_courier_monthly_archive(session, tg_id, limit=24)
        yearly  = await get_courier_yearly_archive(session, tg_id)

    name = (monthly[0].courier_name if monthly else
            yearly[0].courier_name if yearly else f"ID:{tg_id}")

    if mode == "oy":
        text = _courier_monthly_block(monthly, courier_name=name)
    elif mode == "yil":
        text = _courier_yearly_block(yearly, courier_name=name)
    else:
        m_txt = _courier_monthly_block(monthly, courier_name=name)
        y_txt = _courier_yearly_block(yearly)
        text  = m_txt + "\n\n━━━━━━━━━━━━━━━━\n\n" + y_txt

    await update.message.reply_text(text, parse_mode="HTML")


# ── Yangilangan courier_stats ko'rinishi (oylik + yillik) ─────────────

async def show_courier_stats_extended(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin — kuryer umumiy + oylik arxiv."""
    if update.effective_user.id not in config.ADMIN_IDS:
        return

    from services.order_service import get_courier_stats

    async with get_session() as session:
        live_stats = await get_courier_stats(session)
        monthly    = await get_courier_monthly_archive(session, limit=48)

    # Joriy holat
    if not live_stats:
        await update.message.reply_text(
            "🚴 <b>Kuryer statistikasi</b>\n\n📭 Hali birorta kuryer buyurtma qabul qilmagan.",
            parse_mode="HTML",
        )
        return

    lines = ["🚴 <b>Kuryer statistikasi — Joriy</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    total_acc = total_del = 0

    for i, c in enumerate(live_stats, 1):
        acc  = c["total_accepted"]
        dld  = c["total_delivered"]
        prog = c["in_progress"]
        total_acc += acc; total_del += dld
        medal = medals[i-1] if i <= 3 else f"{i}."
        lines.append(
            f"{medal} <b>{c['name']}</b>\n"
            f"   ✅ {dld}  📦 {acc}  🚚 {prog}  📊 {_eff(acc, dld)}"
        )

    lines += [
        "",
        f"📈 <b>Jami:</b> {total_acc} qabul | {total_del} yetkazilgan",
        "",
        "📅 <b>Oylik arxiv (oxirgi 3 oy):</b>",
    ]

    # Oylik arxiv — guruh bo'yicha (har oy yig'indi)
    from collections import defaultdict
    month_agg: dict[tuple, dict] = defaultdict(lambda: {"acc": 0, "del": 0})
    for r in monthly[:18]:
        key = (r.year, r.month)
        month_agg[key]["acc"] += r.total_accepted
        month_agg[key]["del"] += r.total_delivered

    for (y, m), v in sorted(month_agg.items(), reverse=True)[:3]:
        lines.append(
            f"   📅 {MONTH_NAMES[m]} {y}: "
            f"{v['acc']} qabul | {v['del']} yetkazilgan | {_eff(v['acc'], v['del'])}"
        )

    lines += [
        "",
        "💡 Batafsil: /kuryer_arxiv <tg_id>",
        "🔗 Kuryer o'z statistikasi uchun: /mening_statistikam",
    ]

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def register_courier_archive_handlers(app) -> None:
    # Kuryer guruhida — /mening_statistikam
    app.add_handler(CommandHandler(
        "mening_statistikam", cmd_courier_my_stats,
        filters=filters.ChatType.GROUPS,
    ))
    # Admin private — /kuryer_arxiv
    app.add_handler(CommandHandler(
        "kuryer_arxiv", cmd_admin_courier_archive,
        filters=PRIVATE_ONLY,
    ))
    # Admin private — "🚴 Kuryer statistikasi" tugmasi yangi versiyasi
    app.add_handler(MessageHandler(
        PRIVATE_ONLY & filters.Regex("^🚴 Kuryer statistikasi$"),
        show_courier_stats_extended,
    ))
