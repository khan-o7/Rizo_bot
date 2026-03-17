"""User-related DB operations."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
) -> User:
    """Return existing user or create a new one."""
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id, username=username, full_name=full_name)
        session.add(user)
        await session.flush()
    else:
        # Update display name on every interaction
        user.username = username
        user.full_name = full_name
    return user


async def update_phone(session: AsyncSession, tg_id: int, phone: str) -> None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if user:
        user.phone = phone


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    """Return list of all telegram IDs (for broadcast)."""
    result = await session.execute(select(User.tg_id))
    return list(result.scalars().all())
