"""
Kuryer guruhiga xabar yuborish — mustaqil servis.
Barcha kerakli ma'lumotlar DB sессиясidan tashqarida ishlatiladi.
"""
from __future__ import annotations
import html
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


def e(text: str) -> str:
    return html.escape(str(text))

def fmt_price(p: float) -> str:
    return f"{p:,.0f} so'm"


@dataclass
class CourierOrderData:
    """Session yopilgandan keyin ham xavfsiz ishlatiladigan DTO."""
    order_id   : int
    client_name: str
    client_phone: str
    delivery_label: str
    address_text: Optional[str]
    lat         : Optional[float]
    lon         : Optional[float]
    items       : list[dict]          # [{"name": ..., "qty": ..., "subtotal": ...}]
    total       : float
    created_at  : str


def build_courier_data(order) -> CourierOrderData:
    """Order obyektidan CourierOrderData yasaydi (session ichida chaqiriladi)."""
    from db.models import DeliveryType
    DELIVERY_LABELS = {
        DeliveryType.DELIVERY: "🚚 Yetkazib berish",
        DeliveryType.PICKUP:   "🏠 Olib ketish",
    }
    items = []
    for item in order.items:
        sub = float(item.price_snapshot) * float(item.qty)
        items.append({"name": item.product_name_snapshot, "qty": float(item.qty), "subtotal": sub})

    return CourierOrderData(
        order_id      = order.id,
        client_name   = order.user.full_name or "Nomsiz",
        client_phone  = order.user.phone or order.phone,
        delivery_label= DELIVERY_LABELS.get(order.delivery_type, ""),
        address_text  = order.address_text,
        lat           = order.lat,
        lon           = order.lon,
        items         = items,
        total         = float(order.total_price),
        created_at    = order.created_at.strftime("%d.%m.%Y %H:%M"),
    )


def fmt_courier_message(d: CourierOrderData) -> str:
    lines = [
        f"🔔 <b>Yangi buyurtma #{d.order_id}</b>",
        f"📅 {d.created_at}",
        "",
        f"👤 Mijoz: <b>{e(d.client_name)}</b>",
        f"📞 Telefon: <b>{e(d.client_phone)}</b>",
        f"📍 Yetkazish: {e(d.delivery_label)}",
    ]
    if d.lat and d.lon:
        lines.append(
            f'🗺 <a href="https://maps.google.com/?q={d.lat},{d.lon}">Xaritada ko\'rish</a>'
        )
    if d.address_text:
        lines.append(f"📝 Manzil: <b>{e(d.address_text)}</b>")
    lines += ["", "<b>Mahsulotlar:</b>"]
    for item in d.items:
        lines.append(f"• {e(item['name'])} × {item['qty']} kg = {fmt_price(item['subtotal'])}")
    lines.append(f"\n💰 <b>Jami: {fmt_price(d.total)}</b>")
    lines.append("💵 To'lov: Naqd")
    return "\n".join(lines)


async def send_to_courier_group(
    bot,
    group_id: int,
    order_id: int,
    courier_data: CourierOrderData,
    accept_kb,
) -> Optional[int]:
    """
    Guruhga xabar yuboradi.
    Muvaffaqiyatli bo'lsa — message_id qaytaradi.
    """
    try:
        text = fmt_courier_message(courier_data)
        sent = await bot.send_message(
            chat_id=group_id,
            text=text,
            parse_mode="HTML",
            reply_markup=accept_kb,
            disable_web_page_preview=True,
        )
        logger.info(f"✅ Buyurtma #{order_id} kuryer guruhiga yuborildi (msg_id={sent.message_id})")
        return sent.message_id
    except Exception as ex:
        logger.error(f"❌ Kuryer guruhiga yuborishda XATO (group_id={group_id}): {ex}", exc_info=True)
        return None
