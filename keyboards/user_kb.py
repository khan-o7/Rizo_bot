"""User-facing keyboards."""
from __future__ import annotations
from typing import Optional, Sequence
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from db.models import Cart, Category, Order, OrderStatus, Product
from utils.formatters import fmt_price, fmt_qty


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🛍 Katalog", "🛒 Savatcha"], ["📦 Buyurtmalarim", "📞 Bog'lanish"]],
        resize_keyboard=True,
    )

def share_contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )

def share_location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Lokatsiyani ulashish", request_location=True)], ["⬅️ Orqaga"]],
        resize_keyboard=True, one_time_keyboard=True,
    )

def delivery_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🚚 Yetkazib berish", "🏠 Olib ketish"], ["❌ Bekor qilish"]],
        resize_keyboard=True,
    )

def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()

def _cart_summary_btn(cart: Optional[Cart]) -> Optional[InlineKeyboardButton]:
    if not cart or not cart.items:
        return None
    qty   = sum(float(i.qty) for i in cart.items)
    total = sum(float(i.product.price) * float(i.qty) for i in cart.items)
    return InlineKeyboardButton(f"🛒 Savatcha: {fmt_qty(qty)} · {fmt_price(total)}", callback_data="cart:view")

def categories_kb(categories: Sequence[Category], cart: Optional[Cart] = None) -> InlineKeyboardMarkup:
    buttons = []
    btn = _cart_summary_btn(cart)
    if btn:
        buttons.append([btn])
    for cat in categories:
        buttons.append([InlineKeyboardButton(cat.name, callback_data=f"cat:{cat.id}")])
    return InlineKeyboardMarkup(buttons)

def products_kb(products: Sequence[Product], category_id: int, cart: Optional[Cart] = None) -> InlineKeyboardMarkup:
    buttons = []
    btn = _cart_summary_btn(cart)
    if btn:
        buttons.append([btn])
    for p in products:
        stock_label = f"  📦{p.stock}" if p.stock <= 5 else ""
        buttons.append([InlineKeyboardButton(
            f"{p.name} — {p.price:,.0f} so'm{stock_label}",
            callback_data=f"prod:{p.id}",
        )])
    buttons.append([InlineKeyboardButton("⬅️ Kategoriyalar", callback_data="back:cats")])
    return InlineKeyboardMarkup(buttons)

def product_detail_kb(product_id: int, category_id: int, qty_in_cart: float = 0, cart: Optional[Cart] = None) -> InlineKeyboardMarkup:
    qty_label = f"✅ {fmt_qty(qty_in_cart)}" if qty_in_cart > 0 else "0 kg"
    buttons = [
        [
            InlineKeyboardButton("➖", callback_data=f"cart:remove:{product_id}"),
            InlineKeyboardButton(qty_label, callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"cart:add:{product_id}"),
        ],
    ]
    btn = _cart_summary_btn(cart)
    if btn:
        buttons.append([btn])
    buttons.append([InlineKeyboardButton("⬅️ Mahsulotlar", callback_data=f"cat:{category_id}")])
    return InlineKeyboardMarkup(buttons)

def cart_kb(cart: Cart) -> InlineKeyboardMarkup:
    buttons = []
    for item in cart.items:
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"cart:remove:{item.product_id}"),
            InlineKeyboardButton(f"{item.product.name[:18]} · {fmt_qty(item.qty)}", callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"cart:add:{item.product_id}"),
        ])
    buttons.append([InlineKeyboardButton("🗑 Savatchani tozalash", callback_data="cart:clear")])
    buttons.append([InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout:start")])
    return InlineKeyboardMarkup(buttons)

def user_order_kb(order: Order) -> Optional[InlineKeyboardMarkup]:
    """Foydalanuvchi buyurtmasi uchun tugmalar. NEW bo'lsagina bekor tugmasi."""
    if order.status == OrderStatus.NEW:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Bekor qilish", callback_data=f"user_cancel:{order.id}")]
        ])
    return None
