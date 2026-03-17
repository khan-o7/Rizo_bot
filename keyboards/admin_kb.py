"""Admin keyboards."""
from __future__ import annotations
from typing import Sequence
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from db.models import Category, OrderStatus, Product

STATUS_LABELS = {
    OrderStatus.NEW:        "🆕 Yangi",
    OrderStatus.PROCESSING: "🚚 Yetkazib berilmoqda",
    OrderStatus.DONE:       "✅ Muvaffaqiyatli yakunlangan",
    OrderStatus.CANCELED:   "❌ Bekor qilingan",
}
STATUS_EMOJI = {
    OrderStatus.NEW:        "🆕",
    OrderStatus.PROCESSING: "🚚",
    OrderStatus.DONE:       "✅",
    OrderStatus.CANCELED:   "❌",
}


def admin_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["➕ Mahsulot qo'shish",  "✏️ Mahsulotni tahrirlash"],
            ["🗑 Mahsulot o'chirish", "📦 Buyurtmalar"],
            ["🏪 Ombor",             "📊 Statistika"],
            ["📊 Arxiv statistika",  "🚴 Kuryer statistikasi"],
            ["📢 Broadcast"],
            ["🔙 Asosiy menyu"],
        ],
        resize_keyboard=True,
    )


def admin_categories_kb(categories: Sequence[Category], action: str = "sel") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(cat.name, callback_data=f"adm_cat:{action}:{cat.id}")]
        for cat in categories
    ]
    if action == "sel":
        buttons.append([InlineKeyboardButton("➕ Yangi kategoriya", callback_data="adm_cat:new:0")])
    buttons.append([InlineKeyboardButton("❌ Bekor", callback_data="adm:cancel")])
    return InlineKeyboardMarkup(buttons)


def admin_products_kb(products: Sequence[Product], action: str = "edit") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            f"{'✅' if p.is_active else '❌'} {p.name}  📦{p.stock}",
            callback_data=f"adm_prod:{action}:{p.id}",
        )]
        for p in products
    ]
    buttons.append([InlineKeyboardButton("❌ Bekor", callback_data="adm:cancel")])
    return InlineKeyboardMarkup(buttons)


def admin_edit_fields_kb(product_id: int) -> InlineKeyboardMarkup:
    fields = [
        ("Nomi", "name"), ("Narxi", "price"), ("Tavsif", "description"),
        ("Rasm", "photo"), ("Ombor soni", "stock"), ("Status", "status"),
    ]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"adm_edit:{product_id}:{field}")]
        for label, field in fields
    ]
    buttons.append([InlineKeyboardButton("❌ Bekor", callback_data="adm:cancel")])
    return InlineKeyboardMarkup(buttons)


def admin_status_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aktiv",   callback_data=f"adm_status:{product_id}:1"),
            InlineKeyboardButton("❌ Noaktiv", callback_data=f"adm_status:{product_id}:0"),
        ],
        [InlineKeyboardButton("❌ Bekor", callback_data="adm:cancel")],
    ])


def admin_orders_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🆕 Yangi",        callback_data="adm_orders:new"),
            InlineKeyboardButton("🚚 Yetkazib berilmoqda", callback_data="adm_orders:processing"),
        ],
        [
            InlineKeyboardButton("✅ Muvaffaqiyatli", callback_data="adm_orders:done"),
            InlineKeyboardButton("❌ Bekor qilingan", callback_data="adm_orders:canceled"),
        ],
        [InlineKeyboardButton("📋 Barchasi", callback_data="adm_orders:all")],
    ])


def order_status_actions_kb(
    order_id: int,
    current_status: OrderStatus = OrderStatus.NEW,
) -> InlineKeyboardMarkup:
    """
    Status tugmalari — joriy status bosilmasin (✓ belgi + noop).
    DONE / CANCELED → faqat ⬅️ Orqaga.
    """
    back = InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_orders:back")

    if current_status in (OrderStatus.DONE, OrderStatus.CANCELED):
        return InlineKeyboardMarkup([[back]])

    def _btn(label: str, status_str: str, target_status: OrderStatus) -> InlineKeyboardButton:
        """Agar joriy status bo'lsa — ✓ va noop, aks holda amal."""
        if current_status == target_status:
            return InlineKeyboardButton(f"✓ {label}", callback_data="noop")
        return InlineKeyboardButton(label, callback_data=f"ord_status:{order_id}:{status_str}")

    return InlineKeyboardMarkup([
        [
            _btn("🚚 Yetkazib berish", "processing", OrderStatus.PROCESSING),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"ord_cancel:{order_id}"),
        ],
        [back],
    ])


def skip_kb(cancel: bool = True) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="adm:skip")]]
    if cancel:
        buttons.append([InlineKeyboardButton("❌ Bekor", callback_data="adm:cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Kuryer guruhi tugmalari ────────────────────────────────────────────

def courier_accept_kb(order_id: int) -> InlineKeyboardMarkup:
    """Guruhga yuborilgan xabardagi 'Qabul qilish' tugmasi."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🚴 Yetkazish uchun qabul qilish",
            callback_data=f"courier_accept:{order_id}",
        )]
    ])


def courier_delivered_kb(order_id: int) -> InlineKeyboardMarkup:
    """Kuryer qabul qilgandan keyin 'Yetkazib berildi' tugmasi."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Yetkazib berildi",
            callback_data=f"courier_done:{order_id}",
        )]
    ])
