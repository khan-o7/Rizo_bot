"""Order creation and management + stock + courier."""
from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db.models import Cart, DeliveryType, Order, OrderItem, OrderStatus, PaymentType, User
from services.cart_service import cart_total, clear_cart
from services.product_service import deduct_stock, restore_stock


async def create_order(
    session: AsyncSession, user: User, cart: Cart,
    delivery_type: DeliveryType, phone: str,
    address_text: Optional[str] = None,
    lat: Optional[float] = None, lon: Optional[float] = None,
) -> Order:
    total = await cart_total(cart)
    order = Order(
        user_id=user.id, total_price=total, delivery_type=delivery_type,
        payment_type=PaymentType.CASH, phone=phone,
        address_text=address_text, lat=lat, lon=lon, status=OrderStatus.NEW,
    )
    session.add(order)
    await session.flush()
    for item in cart.items:
        session.add(OrderItem(
            order_id=order.id, product_id=item.product_id,
            product_name_snapshot=item.product.name,
            price_snapshot=float(item.product.price), qty=float(item.qty),
        ))
        await deduct_stock(session, item.product_id, item.qty)
    await clear_cart(session, user)
    await session.flush()
    return order


async def get_order(session: AsyncSession, order_id: int) -> Optional[Order]:
    result = await session.execute(
        select(Order).where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.user))
    )
    return result.scalar_one_or_none()


async def get_user_orders(session: AsyncSession, tg_id: int, limit: int = 10) -> Sequence[Order]:
    result = await session.execute(
        select(Order).join(Order.user).where(User.tg_id == tg_id)
        .options(selectinload(Order.items))
        .order_by(desc(Order.created_at)).limit(limit)
    )
    return result.scalars().all()


async def get_orders_by_status(
    session: AsyncSession, status: Optional[OrderStatus] = None, limit: int = 50
) -> Sequence[Order]:
    q = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .order_by(desc(Order.created_at)).limit(limit)
    )
    if status:
        q = q.where(Order.status == status)
    return (await session.execute(q)).scalars().all()


async def update_order_status(
    session: AsyncSession, order_id: int, status: OrderStatus,
    cancel_reason: Optional[str] = None, canceled_by: Optional[str] = None,
) -> Optional[Order]:
    order = await get_order(session, order_id)
    if order is None:
        return None
    old_status = order.status
    order.status = status
    if cancel_reason:
        order.cancel_reason = cancel_reason
    if canceled_by:
        order.canceled_by = canceled_by
    if status == OrderStatus.CANCELED and old_status != OrderStatus.CANCELED:
        for item in order.items:
            if item.product_id:
                await restore_stock(session, item.product_id, item.qty)
    return order


async def assign_courier(
    session: AsyncSession, order_id: int,
    courier_tg_id: int, courier_name: str,
) -> Optional[Order]:
    """Kuryer buyurtmani qabul qildi."""
    order = await get_order(session, order_id)
    if order is None:
        return None
    order.courier_tg_id = courier_tg_id
    order.courier_name  = courier_name
    order.status        = OrderStatus.PROCESSING
    return order


async def save_courier_msg_id(
    session: AsyncSession, order_id: int, msg_id: int
) -> None:
    """Guruh xabarining message_id ni saqlash (edit uchun)."""
    order = await get_order(session, order_id)
    if order:
        order.courier_msg_id = msg_id


async def mark_delivered(
    session: AsyncSession, order_id: int
) -> Optional[Order]:
    """Kuryer yetkazib berdi."""
    order = await get_order(session, order_id)
    if order is None:
        return None
    order.status = OrderStatus.DONE
    return order


async def can_user_cancel(order: Order) -> bool:
    return order.status == OrderStatus.NEW


# ── Statistics ────────────────────────────────────────────────────────
async def stats_today(session: AsyncSession) -> dict:
    from datetime import date, datetime
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_count = (await session.execute(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    )).scalar_one() or 0
    all_count = (await session.execute(select(func.count(Order.id)))).scalar_one() or 0
    revenue = float((await session.execute(
        select(func.sum(Order.total_price)).where(Order.status != OrderStatus.CANCELED)
    )).scalar_one() or 0)
    return {"today": today_count, "total": all_count, "revenue": revenue}


# ── Courier statistics ────────────────────────────────────────────────

async def get_courier_stats(session: AsyncSession) -> list[dict]:
    """
    Har bir kuryer uchun:
      - Jami qabul qilgan (courier_tg_id bo'lgan)
      - Yetkazib bergan (status=DONE)
      - Jarayondagi (status=PROCESSING)
    """
    from sqlalchemy import case
    result = await session.execute(
        select(
            Order.courier_tg_id,
            Order.courier_name,
            func.count(Order.id).label("total_accepted"),
            func.sum(
                case((Order.status == OrderStatus.DONE, 1), else_=0)
            ).label("total_delivered"),
            func.sum(
                case((Order.status == OrderStatus.PROCESSING, 1), else_=0)
            ).label("in_progress"),
        )
        .where(Order.courier_tg_id.isnot(None))
        .group_by(Order.courier_tg_id, Order.courier_name)
        .order_by(func.count(Order.id).desc())
    )
    rows = result.all()
    return [
        {
            "tg_id":           row.courier_tg_id,
            "name":            row.courier_name or "Noma'lum",
            "total_accepted":  int(row.total_accepted),
            "total_delivered": int(row.total_delivered or 0),
            "in_progress":     int(row.in_progress or 0),
        }
        for row in rows
    ]


async def get_courier_orders(
    session: AsyncSession,
    courier_tg_id: int,
    limit: int = 20,
) -> Sequence[Order]:
    """Kuryer tomonidan qabul qilingan buyurtmalar."""
    result = await session.execute(
        select(Order)
        .where(Order.courier_tg_id == courier_tg_id)
        .options(selectinload(Order.items), selectinload(Order.user))
        .order_by(desc(Order.created_at))
        .limit(limit)
    )
    return result.scalars().all()
