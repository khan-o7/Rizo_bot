"""Product and category CRUD + stock management."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Category, Order, OrderItem, OrderStatus, Product


# ── Categories ────────────────────────────────────────────────────────

async def get_active_categories(session: AsyncSession) -> Sequence[Category]:
    result = await session.execute(
        select(Category).where(Category.is_active == True).order_by(Category.name)
    )
    return result.scalars().all()


async def get_all_categories(session: AsyncSession) -> Sequence[Category]:
    result = await session.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


async def create_category(session: AsyncSession, name: str) -> Category:
    cat = Category(name=name)
    session.add(cat)
    await session.flush()
    return cat


async def get_category(session: AsyncSession, category_id: int) -> Optional[Category]:
    result = await session.execute(select(Category).where(Category.id == category_id))
    return result.scalar_one_or_none()


# ── Products ──────────────────────────────────────────────────────────

async def get_products_by_category(
    session: AsyncSession, category_id: int, active_only: bool = True
) -> Sequence[Product]:
    q = select(Product).where(Product.category_id == category_id)
    if active_only:
        q = q.where(Product.is_active == True)
    result = await session.execute(q.order_by(Product.name))
    return result.scalars().all()


async def get_product(session: AsyncSession, product_id: int) -> Optional[Product]:
    result = await session.execute(
        select(Product).where(Product.id == product_id)
        .options(selectinload(Product.category))
    )
    return result.scalar_one_or_none()


async def get_all_products(session: AsyncSession) -> Sequence[Product]:
    result = await session.execute(
        select(Product).options(selectinload(Product.category)).order_by(Product.name)
    )
    return result.scalars().all()


async def create_product(
    session: AsyncSession,
    category_id: int,
    name: str,
    price: float,
    description: Optional[str] = None,
    photo_file_id: Optional[str] = None,
    is_active: bool = True,
    stock: int = 0,
) -> Product:
    product = Product(
        category_id=category_id,
        name=name,
        price=price,
        description=description,
        photo_file_id=photo_file_id,
        is_active=is_active,
        stock=stock,
    )
    session.add(product)
    await session.flush()
    return product


async def update_product(
    session: AsyncSession, product_id: int, **kwargs
) -> Optional[Product]:
    product = await get_product(session, product_id)
    if product is None:
        return None
    for key, value in kwargs.items():
        if hasattr(product, key):
            setattr(product, key, value)
    return product


async def delete_product(session: AsyncSession, product_id: int) -> bool:
    product = await get_product(session, product_id)
    if product is None:
        return False
    await session.delete(product)
    return True


# ── Stock management ──────────────────────────────────────────────────

async def deduct_stock(session: AsyncSession, product_id: int, qty: float) -> bool:
    """Ombordan miqdor ayiradi. Yetarli bo'lmasa False qaytaradi."""
    product = await get_product(session, product_id)
    if product is None:
        return False
    if product.stock < qty:
        product.stock = 0  # kamida 0
    else:
        product.stock -= qty
    return True


async def restore_stock(session: AsyncSession, product_id: int, qty: float) -> None:
    """Buyurtma bekor bo'lganda omborga qaytaradi."""
    product = await get_product(session, product_id)
    if product:
        product.stock += qty


# ── Warehouse overview ────────────────────────────────────────────────

async def get_warehouse_stats(session: AsyncSession) -> list[dict]:
    """
    Har bir mahsulot uchun:
      - Ombordagi qoldiq (stock)
      - Jami sotilgan (orderlardan, bekor qilinmaganlar)
    """
    # Jami sotilganlar (bekor qilinmaganlar hisobsiz)
    sold_result = await session.execute(
        select(
            OrderItem.product_id,
            func.sum(OrderItem.qty).label("sold_qty"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status != OrderStatus.CANCELED)
        .where(OrderItem.product_id.isnot(None))
        .group_by(OrderItem.product_id)
    )
    sold_map = {row.product_id: int(row.sold_qty) for row in sold_result.all()}

    products = await get_all_products(session)
    result = []
    for p in products:
        result.append({
            "id":      p.id,
            "name":    p.name,
            "price":   float(p.price),
            "stock":   p.stock,
            "sold":    sold_map.get(p.id, 0),
            "active":  p.is_active,
            "category": p.category.name if p.category else "—",
        })
    result.sort(key=lambda x: x["stock"])  # kamlari yuqorida
    return result


# ── Stats ─────────────────────────────────────────────────────────────

async def top_products(session: AsyncSession, limit: int = 5) -> list[dict]:
    result = await session.execute(
        select(
            OrderItem.product_name_snapshot,
            func.sum(OrderItem.qty).label("total_qty"),
        )
        .group_by(OrderItem.product_name_snapshot)
        .order_by(desc("total_qty"))
        .limit(limit)
    )
    return [{"name": row[0], "qty": int(row[1])} for row in result.all()]
