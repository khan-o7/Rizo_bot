"""
SQLAlchemy ORM models — v3.
Yangiliklar:
  Product.stock            — ombordagi miqdor
  Order.cancel_reason      — bekor sababi
  Order.canceled_by        — "admin" | "user"
  Order.courier_tg_id      — qabul qilgan kuryer Telegram ID
  Order.courier_name       — kuryer ismi
  Order.courier_msg_id     — guruh xabarining message_id (edit uchun)
"""
from __future__ import annotations
import enum
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float,
    ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DeliveryType(str, enum.Enum):
    DELIVERY = "delivery"
    PICKUP   = "pickup"


class PaymentType(str, enum.Enum):
    CASH = "cash"


class OrderStatus(str, enum.Enum):
    NEW        = "new"
    PROCESSING = "processing"
    DONE       = "done"
    CANCELED   = "canceled"


class User(Base):
    __tablename__ = "users"
    id        : Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id     : Mapped[int]           = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username  : Mapped[Optional[str]] = mapped_column(String(64),  nullable=True)
    full_name : Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    phone     : Mapped[Optional[str]] = mapped_column(String(20),  nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime, server_default=func.now(), nullable=False)
    cart  : Mapped[Optional["Cart"]]  = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    orders: Mapped[List["Order"]]     = relationship(back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"
    id       : Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    name     : Mapped[str]  = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    products : Mapped[List["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"
    id           : Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id  : Mapped[int]           = mapped_column(ForeignKey("categories.id"), nullable=False)
    name         : Mapped[str]           = mapped_column(String(128), nullable=False)
    price        : Mapped[float]         = mapped_column(Numeric(12, 2), nullable=False)
    description  : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active    : Mapped[bool]          = mapped_column(Boolean, default=True, nullable=False)
    stock        : Mapped[float]         = mapped_column(Numeric(8, 1), default=0, nullable=False)
    created_at   : Mapped[datetime]      = mapped_column(DateTime, server_default=func.now(), nullable=False)
    category  : Mapped["Category"]       = relationship(back_populates="products")
    cart_items: Mapped[List["CartItem"]] = relationship(back_populates="product")


class Cart(Base):
    __tablename__ = "carts"
    id     : Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    user : Mapped["User"]           = relationship(back_populates="cart")
    items: Mapped[List["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    id        : Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id   : Mapped[int]   = mapped_column(ForeignKey("carts.id"), nullable=False)
    product_id: Mapped[int]   = mapped_column(ForeignKey("products.id"), nullable=False)
    qty       : Mapped[float] = mapped_column(Numeric(6, 1), default=0.5, nullable=False)
    cart   : Mapped["Cart"]    = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"
    id             : Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id        : Mapped[int]             = mapped_column(ForeignKey("users.id"), nullable=False)
    total_price    : Mapped[float]           = mapped_column(Numeric(12, 2), nullable=False)
    delivery_type  : Mapped[DeliveryType]    = mapped_column(Enum(DeliveryType), nullable=False)
    payment_type   : Mapped[PaymentType]     = mapped_column(Enum(PaymentType), default=PaymentType.CASH, nullable=False)
    phone          : Mapped[str]             = mapped_column(String(20), nullable=False)
    address_text   : Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    lat            : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon            : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status         : Mapped[OrderStatus]     = mapped_column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)
    cancel_reason  : Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    canceled_by    : Mapped[Optional[str]]   = mapped_column(String(16), nullable=True)
    # ── Kuryer ────────────────────────────────────────────────────────
    courier_tg_id  : Mapped[Optional[int]]   = mapped_column(BigInteger, nullable=True)
    courier_name   : Mapped[Optional[str]]   = mapped_column(String(128), nullable=True)
    courier_msg_id : Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)  # guruh xabari ID
    created_at     : Mapped[datetime]        = mapped_column(DateTime, server_default=func.now(), nullable=False)
    user : Mapped["User"]            = relationship(back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id                   : Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id             : Mapped[int]            = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id           : Mapped[Optional[int]]  = mapped_column(ForeignKey("products.id"), nullable=True)
    product_name_snapshot: Mapped[str]            = mapped_column(String(128), nullable=False)
    price_snapshot       : Mapped[float]          = mapped_column(Numeric(12, 2), nullable=False)
    qty                  : Mapped[int]            = mapped_column(Integer, nullable=False)
    order  : Mapped["Order"]             = relationship(back_populates="items")
    product: Mapped[Optional["Product"]] = relationship()


# ── Arxiv modellari ────────────────────────────────────────────────────

class MonthlyStats(Base):
    """Har oy oxirida avtomatik arxivlanadigan oylik statistika."""
    __tablename__ = "monthly_stats"
    id              : Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    year            : Mapped[int]   = mapped_column(Integer, nullable=False)
    month           : Mapped[int]   = mapped_column(Integer, nullable=False)   # 1–12
    total_orders    : Mapped[int]   = mapped_column(Integer, default=0)
    done_orders     : Mapped[int]   = mapped_column(Integer, default=0)
    canceled_orders : Mapped[int]   = mapped_column(Integer, default=0)
    total_revenue   : Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    new_users       : Mapped[int]   = mapped_column(Integer, default=0)
    archived_at     : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class YearlyStats(Base):
    """Har yil oxirida avtomatik arxivlanadigan yillik statistika."""
    __tablename__ = "yearly_stats"
    id              : Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    year            : Mapped[int]   = mapped_column(Integer, nullable=False, unique=True)
    total_orders    : Mapped[int]   = mapped_column(Integer, default=0)
    done_orders     : Mapped[int]   = mapped_column(Integer, default=0)
    canceled_orders : Mapped[int]   = mapped_column(Integer, default=0)
    total_revenue   : Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    new_users       : Mapped[int]   = mapped_column(Integer, default=0)
    best_month      : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1–12
    archived_at     : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CourierMonthlyStats(Base):
    """Kuryer oylik arxivi."""
    __tablename__ = "courier_monthly_stats"
    id              : Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    courier_tg_id   : Mapped[int]   = mapped_column(BigInteger, nullable=False)
    courier_name    : Mapped[str]   = mapped_column(String(128), nullable=False)
    year            : Mapped[int]   = mapped_column(Integer, nullable=False)
    month           : Mapped[int]   = mapped_column(Integer, nullable=False)
    total_accepted  : Mapped[int]   = mapped_column(Integer, default=0)
    total_delivered : Mapped[int]   = mapped_column(Integer, default=0)
    archived_at     : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CourierYearlyStats(Base):
    """Kuryer yillik arxivi."""
    __tablename__ = "courier_yearly_stats"
    id              : Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    courier_tg_id   : Mapped[int]   = mapped_column(BigInteger, nullable=False)
    courier_name    : Mapped[str]   = mapped_column(String(128), nullable=False)
    year            : Mapped[int]   = mapped_column(Integer, nullable=False)
    total_accepted  : Mapped[int]   = mapped_column(Integer, default=0)
    total_delivered : Mapped[int]   = mapped_column(Integer, default=0)
    archived_at     : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
