"""Shopping cart operations."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Cart, CartItem, Product, User


async def _get_or_create_cart(session: AsyncSession, user: User) -> Cart:
    """Get existing cart or create new one (uses explicit query, no lazy load)."""
    result = await session.execute(
        select(Cart).where(Cart.user_id == user.id)
    )
    cart = result.scalar_one_or_none()
    if cart is None:
        cart = Cart(user_id=user.id)
        session.add(cart)
        await session.flush()
    return cart


async def get_cart_with_items(
    session: AsyncSession, tg_id: int
) -> Optional[Cart]:
    """Load full cart with items and products for a telegram user."""
    result = await session.execute(
        select(Cart)
        .join(Cart.user)
        .where(User.tg_id == tg_id)
        .options(
            selectinload(Cart.items).selectinload(CartItem.product)
        )
    )
    return result.scalar_one_or_none()


async def add_to_cart(
    session: AsyncSession, user: User, product_id: int, qty: float = 0.5
) -> CartItem:
    cart = await _get_or_create_cart(session, user)

    result = await session.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )
    item = result.scalar_one_or_none()

    if item:
        item.qty = round(float(item.qty) + qty, 1)
    else:
        item = CartItem(cart_id=cart.id, product_id=product_id, qty=qty)
        session.add(item)

    await session.flush()
    return item


async def remove_from_cart(
    session: AsyncSession, user: User, product_id: int
) -> bool:
    cart = await _get_or_create_cart(session, user)
    result = await session.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        return False
    if float(item.qty) > 0.5:
        item.qty = round(float(item.qty) - 0.5, 1)
    else:
        await session.delete(item)
    return True


async def clear_cart(session: AsyncSession, user: User) -> None:
    cart = await _get_or_create_cart(session, user)
    result = await session.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    for item in result.scalars().all():
        await session.delete(item)


async def cart_total(cart: Cart) -> float:
    return sum(float(item.product.price) * float(item.qty) for item in cart.items)
