"""
Arxiv xizmati — oylik va yillik statistikani avtomatik arxivlash.

Qachon ishlaydi:
  - Har oy 1-sanasi soat 00:05 da o'tgan oy arxivlanadi
  - Har yil 1-yanvar soat 00:10 da o'tgan yil arxivlanadi
  - Bot ishga tushganda ham tekshiradi (o'tkazib yuborilgan arxivlar uchun)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CourierMonthlyStats, CourierYearlyStats,
    MonthlyStats, Order, OrderStatus, User, YearlyStats,
)
from db.session import get_session

logger = logging.getLogger(__name__)

MONTH_NAMES = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}


# ─────────────────────────────────────────────────────────────────────
# Arxivlash funksiyalari
# ─────────────────────────────────────────────────────────────────────

async def archive_month(session: AsyncSession, year: int, month: int) -> MonthlyStats | None:
    """Berilgan oy statistikasini arxivlaydi. Agar avval arxivlangan bo'lsa — o'tkazib yuboradi."""
    # Allaqachon arxivlanganmi?
    existing = (await session.execute(
        select(MonthlyStats).where(
            MonthlyStats.year == year,
            MonthlyStats.month == month,
        )
    )).scalar_one_or_none()
    if existing:
        logger.info(f"⏭ {year}/{month:02d} allaqachon arxivlangan.")
        return existing

    # Oy chegaralari
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)

    where = and_(Order.created_at >= start, Order.created_at < end)

    total_orders = (await session.execute(
        select(func.count(Order.id)).where(where)
    )).scalar_one() or 0

    done_orders = (await session.execute(
        select(func.count(Order.id)).where(where, Order.status == OrderStatus.DONE)
    )).scalar_one() or 0

    canceled_orders = (await session.execute(
        select(func.count(Order.id)).where(where, Order.status == OrderStatus.CANCELED)
    )).scalar_one() or 0

    total_revenue = float((await session.execute(
        select(func.sum(Order.total_price)).where(where, Order.status == OrderStatus.DONE)
    )).scalar_one() or 0)

    new_users = (await session.execute(
        select(func.count(User.id)).where(
            User.created_at >= start,
            User.created_at < end,
        )
    )).scalar_one() or 0

    rec = MonthlyStats(
        year=year, month=month,
        total_orders=total_orders,
        done_orders=done_orders,
        canceled_orders=canceled_orders,
        total_revenue=total_revenue,
        new_users=new_users,
    )
    session.add(rec)
    await session.flush()
    logger.info(f"✅ Arxivlandi: {year}/{month:02d} — {total_orders} buyurtma, {total_revenue:,.0f} so'm")
    return rec


async def archive_year(session: AsyncSession, year: int) -> YearlyStats | None:
    """Berilgan yil statistikasini arxivlaydi."""
    existing = (await session.execute(
        select(YearlyStats).where(YearlyStats.year == year)
    )).scalar_one_or_none()
    if existing:
        logger.info(f"⏭ {year} yil allaqachon arxivlangan.")
        return existing

    start = datetime(year, 1, 1)
    end   = datetime(year + 1, 1, 1)
    where = and_(Order.created_at >= start, Order.created_at < end)

    total_orders = (await session.execute(
        select(func.count(Order.id)).where(where)
    )).scalar_one() or 0

    done_orders = (await session.execute(
        select(func.count(Order.id)).where(where, Order.status == OrderStatus.DONE)
    )).scalar_one() or 0

    canceled_orders = (await session.execute(
        select(func.count(Order.id)).where(where, Order.status == OrderStatus.CANCELED)
    )).scalar_one() or 0

    total_revenue = float((await session.execute(
        select(func.sum(Order.total_price)).where(where, Order.status == OrderStatus.DONE)
    )).scalar_one() or 0)

    new_users = (await session.execute(
        select(func.count(User.id)).where(
            User.created_at >= start, User.created_at < end,
        )
    )).scalar_one() or 0

    # Eng yaxshi oy (daromad bo'yicha)
    best_month_row = (await session.execute(
        select(
            func.strftime("%m", Order.created_at).label("m"),
            func.sum(Order.total_price).label("rev"),
        )
        .where(where, Order.status == OrderStatus.DONE)
        .group_by("m")
        .order_by(func.sum(Order.total_price).desc())
        .limit(1)
    )).first()
    best_month = int(best_month_row.m) if best_month_row else None

    rec = YearlyStats(
        year=year,
        total_orders=total_orders,
        done_orders=done_orders,
        canceled_orders=canceled_orders,
        total_revenue=total_revenue,
        new_users=new_users,
        best_month=best_month,
    )
    session.add(rec)
    await session.flush()
    logger.info(f"✅ Arxivlandi: {year} yil — {total_orders} buyurtma, {total_revenue:,.0f} so'm")
    return rec


async def archive_courier_month(session: AsyncSession, year: int, month: int) -> None:
    """Barcha kuryerlar uchun oylik statistikani arxivlaydi."""
    start = datetime(year, month, 1)
    end   = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    from sqlalchemy import case
    rows = (await session.execute(
        select(
            Order.courier_tg_id,
            Order.courier_name,
            func.count(Order.id).label("accepted"),
            func.sum(case((Order.status == OrderStatus.DONE, 1), else_=0)).label("delivered"),
        )
        .where(
            Order.courier_tg_id.isnot(None),
            Order.created_at >= start,
            Order.created_at < end,
        )
        .group_by(Order.courier_tg_id, Order.courier_name)
    )).all()

    for row in rows:
        existing = (await session.execute(
            select(CourierMonthlyStats).where(
                CourierMonthlyStats.courier_tg_id == row.courier_tg_id,
                CourierMonthlyStats.year == year,
                CourierMonthlyStats.month == month,
            )
        )).scalar_one_or_none()
        if existing:
            continue
        session.add(CourierMonthlyStats(
            courier_tg_id=row.courier_tg_id,
            courier_name=row.courier_name or "Noma'lum",
            year=year, month=month,
            total_accepted=int(row.accepted),
            total_delivered=int(row.delivered or 0),
        ))
    await session.flush()
    logger.info(f"✅ Kuryer oylik arxivi: {year}/{month:02d} — {len(rows)} ta kuryer")


async def archive_courier_year(session: AsyncSession, year: int) -> None:
    """Barcha kuryerlar uchun yillik statistikani arxivlaydi."""
    start = datetime(year, 1, 1)
    end   = datetime(year + 1, 1, 1)

    from sqlalchemy import case
    rows = (await session.execute(
        select(
            Order.courier_tg_id,
            Order.courier_name,
            func.count(Order.id).label("accepted"),
            func.sum(case((Order.status == OrderStatus.DONE, 1), else_=0)).label("delivered"),
        )
        .where(
            Order.courier_tg_id.isnot(None),
            Order.created_at >= start,
            Order.created_at < end,
        )
        .group_by(Order.courier_tg_id, Order.courier_name)
    )).all()

    for row in rows:
        existing = (await session.execute(
            select(CourierYearlyStats).where(
                CourierYearlyStats.courier_tg_id == row.courier_tg_id,
                CourierYearlyStats.year == year,
            )
        )).scalar_one_or_none()
        if existing:
            continue
        session.add(CourierYearlyStats(
            courier_tg_id=row.courier_tg_id,
            courier_name=row.courier_name or "Noma'lum",
            year=year,
            total_accepted=int(row.accepted),
            total_delivered=int(row.delivered or 0),
        ))
    await session.flush()
    logger.info(f"✅ Kuryer yillik arxivi: {year} yil — {len(rows)} ta kuryer")


# ─────────────────────────────────────────────────────────────────────
# O'tkazib yuborilgan arxivlarni topib to'ldirish (startup da)
# ─────────────────────────────────────────────────────────────────────

async def run_missing_archives() -> None:
    """
    Bot ishga tushganda: faqat DB dagi birinchi yozuvdan boshlab
    o'tkazib yuborilgan arxivlarni to'ldiradi.
    Undan oldingi bo'sh davrlar arxivlanmaydi.
    """
    today = date.today()
    async with get_session() as session:

        # DBdagi eng birinchi yozuv sanasini topamiz
        first_order = (await session.execute(
            select(func.min(Order.created_at))
        )).scalar_one_or_none()

        first_user = (await session.execute(
            select(func.min(User.created_at))
        )).scalar_one_or_none()

        # Ikkalasidan eng eskisini olamiz
        candidates = [d for d in [first_order, first_user] if d is not None]
        if not candidates:
            logger.info("📭 DB bo'sh — arxivlash kerak emas.")
            return

        first_date: date = min(c.date() if hasattr(c, "date") else c for c in candidates)
        logger.info(f"📅 Bot faoliyati boshlanishi: {first_date}")

        # Birinchi oydan joriy oyga qadar barcha tugagan oylarni arxivlaymiz
        cur = first_date.replace(day=1)
        while True:
            next_m = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
            if next_m > today:
                break  # Joriy oy hali tugamagan
            await archive_month(session, cur.year, cur.month)
            await archive_courier_month(session, cur.year, cur.month)
            cur = next_m

        # Birinchi yildan o'tgan yilga qadar yillik arxiv
        for yr in range(first_date.year, today.year):
            await archive_year(session, yr)
            await archive_courier_year(session, yr)

        await session.commit()
    logger.info("✅ Arxiv tekshiruvi tugadi.")


# ─────────────────────────────────────────────────────────────────────
# Scheduler joblar
# ─────────────────────────────────────────────────────────────────────

async def job_monthly_archive() -> None:
    """Har oy 1-sanasi ishga tushadi — o'tgan oyni arxivlaydi."""
    today = date.today()
    # O'tgan oy
    first_day = today.replace(day=1)
    prev_month_last = first_day - timedelta(days=1)
    y, m = prev_month_last.year, prev_month_last.month

    async with get_session() as session:
        await archive_month(session, y, m)
        await archive_courier_month(session, y, m)
        await session.commit()
    logger.info(f"📦 Oylik arxiv: {y}/{m:02d}")


async def job_yearly_archive() -> None:
    """Har yil 1-yanvarda ishga tushadi — o'tgan yilni arxivlaydi."""
    prev_year = date.today().year - 1
    async with get_session() as session:
        await archive_year(session, prev_year)
        await archive_courier_year(session, prev_year)
        await session.commit()
    logger.info(f"📦 Yillik arxiv: {prev_year}")


# ─────────────────────────────────────────────────────────────────────
# Statistikani o'qish
# ─────────────────────────────────────────────────────────────────────

async def get_monthly_archive(session: AsyncSession, limit: int = 24) -> Sequence[MonthlyStats]:
    res = await session.execute(
        select(MonthlyStats)
        .order_by(MonthlyStats.year.desc(), MonthlyStats.month.desc())
        .limit(limit)
    )
    return res.scalars().all()


async def get_yearly_archive(session: AsyncSession) -> Sequence[YearlyStats]:
    res = await session.execute(
        select(YearlyStats).order_by(YearlyStats.year.desc())
    )
    return res.scalars().all()


async def get_courier_monthly_archive(
    session: AsyncSession,
    courier_tg_id: Optional[int] = None,
    limit: int = 12,
) -> Sequence[CourierMonthlyStats]:
    q = select(CourierMonthlyStats).order_by(
        CourierMonthlyStats.year.desc(), CourierMonthlyStats.month.desc()
    )
    if courier_tg_id:
        q = q.where(CourierMonthlyStats.courier_tg_id == courier_tg_id)
    q = q.limit(limit)
    return (await session.execute(q)).scalars().all()


async def get_courier_yearly_archive(
    session: AsyncSession,
    courier_tg_id: Optional[int] = None,
) -> Sequence[CourierYearlyStats]:
    q = select(CourierYearlyStats).order_by(CourierYearlyStats.year.desc())
    if courier_tg_id:
        q = q.where(CourierYearlyStats.courier_tg_id == courier_tg_id)
    return (await session.execute(q)).scalars().all()


# ─────────────────────────────────────────────────────────────────────
# Joriy oy/yil statistikasi (arxivlanmagan, real-time)
# ─────────────────────────────────────────────────────────────────────

async def get_current_month_stats(session: AsyncSession) -> dict:
    today = date.today()
    start = datetime(today.year, today.month, 1)
    where = Order.created_at >= start

    total    = (await session.execute(select(func.count(Order.id)).where(where))).scalar_one() or 0
    done     = (await session.execute(select(func.count(Order.id)).where(where, Order.status == OrderStatus.DONE))).scalar_one() or 0
    canceled = (await session.execute(select(func.count(Order.id)).where(where, Order.status == OrderStatus.CANCELED))).scalar_one() or 0
    revenue  = float((await session.execute(select(func.sum(Order.total_price)).where(where, Order.status == OrderStatus.DONE))).scalar_one() or 0)
    new_u    = (await session.execute(select(func.count(User.id)).where(User.created_at >= start))).scalar_one() or 0

    return {
        "year": today.year, "month": today.month,
        "total_orders": total, "done_orders": done,
        "canceled_orders": canceled, "total_revenue": revenue,
        "new_users": new_u, "is_current": True,
    }


async def get_current_year_stats(session: AsyncSession) -> dict:
    year = date.today().year
    start = datetime(year, 1, 1)
    where = Order.created_at >= start

    total    = (await session.execute(select(func.count(Order.id)).where(where))).scalar_one() or 0
    done     = (await session.execute(select(func.count(Order.id)).where(where, Order.status == OrderStatus.DONE))).scalar_one() or 0
    canceled = (await session.execute(select(func.count(Order.id)).where(where, Order.status == OrderStatus.CANCELED))).scalar_one() or 0
    revenue  = float((await session.execute(select(func.sum(Order.total_price)).where(where, Order.status == OrderStatus.DONE))).scalar_one() or 0)
    new_u    = (await session.execute(select(func.count(User.id)).where(User.created_at >= start))).scalar_one() or 0

    return {
        "year": year, "total_orders": total, "done_orders": done,
        "canceled_orders": canceled, "total_revenue": revenue,
        "new_users": new_u, "is_current": True,
    }
