"""Matn formatlash — parse_mode="HTML"."""
from __future__ import annotations
import html
from db.models import Cart, DeliveryType, Order, OrderStatus

STATUS_EMOJI  = {OrderStatus.NEW: "🆕", OrderStatus.PROCESSING: "🚚", OrderStatus.DONE: "✅", OrderStatus.CANCELED: "❌"}
STATUS_LABELS = {OrderStatus.NEW: "Yangi", OrderStatus.PROCESSING: "Yetkazib berilmoqda", OrderStatus.DONE: "Muvaffaqiyatli yakunlangan", OrderStatus.CANCELED: "Bekor qilingan"}
DELIVERY_LABELS = {DeliveryType.DELIVERY: "🚚 Yetkazib berish", DeliveryType.PICKUP: "🏠 Olib ketish"}

def e(text: str) -> str:
    return html.escape(str(text))

def fmt_qty(qty: float) -> str:
    """0.5 → '0.5 kg', 1.0 → '1 kg', 1.5 → '1.5 kg'"""
    q = float(qty)
    return f"{int(q)} kg" if q == int(q) else f"{q:.1f} kg"

def fmt_price(price: float) -> str:
    return f"{price:,.0f} so'm"

def fmt_cart(cart: Cart) -> str:
    if not cart.items:
        return "🛒 Savatingiz bo'sh."
    lines = ["🛒 <b>Savatcha:</b>\n"]
    total = 0.0
    for item in cart.items:
        sub = float(item.product.price) * float(item.qty)
        total += sub
        lines.append(f"• {e(item.product.name)} × {fmt_qty(item.qty)} = {fmt_price(sub)}")
    lines.append(f"\n💰 <b>Jami: {fmt_price(total)}</b>")
    return "\n".join(lines)


def _items_block(order: Order) -> list[str]:
    lines = ["", "<b>Mahsulotlar:</b>"]
    for item in order.items:
        sub = float(item.price_snapshot) * float(item.qty)
        lines.append(f"• {e(item.product_name_snapshot)} × {fmt_qty(item.qty)} = {fmt_price(sub)}")
    lines.append(f"\n💰 <b>Jami: {fmt_price(float(order.total_price))}</b>")
    return lines


def fmt_order_for_user(order: Order) -> str:
    emoji = STATUS_EMOJI[order.status]
    label = STATUS_LABELS[order.status]
    lines = [
        f"📦 <b>Buyurtma #{order.id}</b>",
        f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}",
        f"📍 {e(DELIVERY_LABELS[order.delivery_type])}",
        f"📞 {e(order.phone)}",
        f"Holat: {emoji} <b>{e(label)}</b>",
    ]
    if order.courier_name and order.status == OrderStatus.PROCESSING:
        lines.append(f"🚴 Kuryer: <b>{e(order.courier_name)}</b>")
    if order.status == OrderStatus.CANCELED and order.cancel_reason:
        who = "Siz" if order.canceled_by == "user" else "Sotuvchi"
        lines.append(f"💬 Sabab ({who}): <i>{e(order.cancel_reason)}</i>")
    lines += _items_block(order)
    return "\n".join(lines)


def fmt_order_for_admin(order: Order, show_status: bool = True) -> str:
    user  = order.user
    uname = f"@{e(user.username)}" if user.username else "—"
    emoji = STATUS_EMOJI[order.status]
    label = STATUS_LABELS[order.status]
    lines = []
    if show_status:
        lines += [f"{emoji} <b>Status: {e(label)}</b>", ""]
    lines += [
        f"🔔 <b>Buyurtma #{order.id}</b>",
        f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}",
        "",
        f"👤 {e(user.full_name or 'Nomsiz')} ({uname})",
        f"🆔 TG ID: <code>{user.tg_id}</code>",
        f"📞 Telefon: {e(order.phone)}",
        f"📍 Yetkazish: {e(DELIVERY_LABELS[order.delivery_type])}",
    ]
    if order.delivery_type == DeliveryType.DELIVERY:
        if order.lat and order.lon:
            lines.append(f'🗺 Lokatsiya: <a href="https://maps.google.com/?q={order.lat},{order.lon}">Google Maps</a>')
        if order.address_text:
            lines.append(f"📝 Manzil: {e(order.address_text)}")
    if order.courier_name:
        lines.append(f"🚴 Kuryer: <b>{e(order.courier_name)}</b>")
    if order.status == OrderStatus.CANCELED and order.cancel_reason:
        who = "Xaridor" if order.canceled_by == "user" else "Admin"
        lines.append(f"💬 Bekor sababi ({who}): <i>{e(order.cancel_reason)}</i>")
    lines += _items_block(order)
    lines.append("💵 To'lov: Naqd")
    return "\n".join(lines)


def fmt_order_for_courier(order: Order) -> str:
    """Kuryer guruhiga yuboriladigan format — manzil va telefon aniq ko'rinsin."""
    lines = [
        f"🔔 <b>Yangi buyurtma #{order.id}</b>",
        f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}",
        "",
        f"📞 Mijoz telefon: <b>{e(order.user.phone or order.phone)}</b>",
        f"👤 Ismi: {e(order.user.full_name or 'Nomsiz')}",
        f"📍 Yetkazish: {e(DELIVERY_LABELS[order.delivery_type])}",
    ]
    if order.delivery_type == DeliveryType.DELIVERY:
        if order.lat and order.lon:
            lines.append(f'🗺 <a href="https://maps.google.com/?q={order.lat},{order.lon}">Xaritada ko\'rish</a>')
        if order.address_text:
            lines.append(f"📝 Manzil: <b>{e(order.address_text)}</b>")
    lines += _items_block(order)
    lines.append("💵 To'lov: Naqd")
    return "\n".join(lines)
