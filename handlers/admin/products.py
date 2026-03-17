"""Admin mahsulot boshqaruvi — stock qadami qo'shildi."""
from __future__ import annotations
import logging, warnings
warnings.filterwarnings("ignore", message="If 'per_message=False'")

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters,
)
from config import config
from db.session import get_session
from keyboards.admin_kb import (
    admin_categories_kb, admin_edit_fields_kb, admin_main_kb,
    admin_products_kb, admin_status_kb, skip_kb,
)
from services.product_service import (
    create_category, create_product, delete_product,
    get_all_categories, get_all_products, get_product, update_product,
)
from utils.formatters import fmt_price
from utils.filters import PRIVATE_ONLY
from utils.tg_helpers import safe_edit
from utils.validators import is_valid_price, parse_price

logger = logging.getLogger(__name__)

(
    ADD_CAT_SELECT, ADD_CAT_NEW_NAME, ADD_NAME, ADD_PRICE,
    ADD_DESCRIPTION, ADD_PHOTO, ADD_STOCK, ADD_STATUS,
    EDIT_SELECT_PRODUCT, EDIT_SELECT_FIELD, EDIT_VALUE,
    DEL_SELECT,
) = range(12)

_KEY = "_adm_prod"
_NEW = -1


def _ctx(c): return c.user_data.setdefault(_KEY, {})
def _clear(c): c.user_data.pop(_KEY, None)
def _is_admin(u): return u.effective_user.id in config.ADMIN_IDS


# ══ ADD ══════════════════════════════════════════════════════════

async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update): return ConversationHandler.END
    _clear(context)
    async with get_session() as s:
        cats = await get_all_categories(s)
    await update.message.reply_text(
        "📦 <b>Yangi mahsulot — 1/7</b>\n\nKategoriyani tanlang:",
        parse_mode="HTML",
        reply_markup=admin_categories_kb(cats, action="sel"),
    )
    return ADD_CAT_SELECT


async def add_cat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if parts[1] == "new":
        await safe_edit(query.message, "✏️ Yangi kategoriya nomini kiriting:")
        return ADD_CAT_NEW_NAME
    _ctx(context)["category_id"] = int(parts[2])
    await safe_edit(query.message, "📝 <b>2/7</b> — Mahsulot nomini kiriting:", parse_mode="HTML")
    return ADD_NAME


async def add_cat_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Kamida 2 harf. Qaytadan:"); return ADD_CAT_NEW_NAME
    async with get_session() as s:
        cat = await create_category(s, name)
    _ctx(context)["category_id"] = cat.id
    await update.message.reply_text(f"✅ <b>'{name}'</b> yaratildi.\n\n📝 <b>2/7</b> — Mahsulot nomini kiriting:", parse_mode="HTML")
    return ADD_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Juda qisqa. Qaytadan:"); return ADD_NAME
    _ctx(context)["name"] = name
    await update.message.reply_text("💰 <b>3/7</b> — Narxni kiriting (so'm, faqat raqam):", parse_mode="HTML")
    return ADD_PRICE


async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not is_valid_price(text):
        await update.message.reply_text("❌ Noto'g'ri narx. Musbat raqam kiriting:"); return ADD_PRICE
    _ctx(context)["price"] = parse_price(text)
    await update.message.reply_text("📋 <b>4/7</b> — Tavsif (ixtiyoriy):", parse_mode="HTML", reply_markup=skip_kb())
    return ADD_DESCRIPTION


async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        _ctx(context)["description"] = None
        await safe_edit(update.callback_query.message, "🖼 <b>5/7</b> — Rasm yuklang (ixtiyoriy):", parse_mode="HTML", reply_markup=skip_kb())
    else:
        _ctx(context)["description"] = update.message.text.strip()
        await update.message.reply_text("🖼 <b>5/7</b> — Rasm yuklang (ixtiyoriy):", parse_mode="HTML", reply_markup=skip_kb())
    return ADD_PHOTO


async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        _ctx(context)["photo_file_id"] = None
        await safe_edit(update.callback_query.message, "📦 <b>6/7</b> — Ombordagi boshlang'ich miqdorini kiriting (kg, masalan: 10 yoki 0.5):", parse_mode="HTML")
    else:
        _ctx(context)["photo_file_id"] = update.message.photo[-1].file_id if update.message.photo else None
        await update.message.reply_text("📦 <b>6/7</b> — Ombordagi boshlang'ich miqdorini kiriting (kg, masalan: 10 yoki 0.5):", parse_mode="HTML")
    return ADD_STOCK


async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        stock_val = round(float(text.replace(",", ".")), 1)
        if stock_val < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri miqdor. Musbat son kiriting (masalan: 10 yoki 0.5):"); return ADD_STOCK
    _ctx(context)["stock"] = stock_val
    await update.message.reply_text(
        "📌 <b>7/7</b> — Status tanlang:",
        parse_mode="HTML",
        reply_markup=admin_status_kb(_NEW),
    )
    return ADD_STATUS


async def add_status_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    is_active = query.data.split(":")[2] == "1"
    data = _ctx(context)
    async with get_session() as s:
        product = await create_product(
            session=s,
            category_id=data["category_id"],
            name=data["name"],
            price=data["price"],
            description=data.get("description"),
            photo_file_id=data.get("photo_file_id"),
            is_active=is_active,
            stock=data.get("stock", 0),
        )
    status_str = "✅ Aktiv" if is_active else "❌ Noaktiv"
    await safe_edit(
        query.message,
        f"✅ <b>Mahsulot qo'shildi!</b>\n\n"
        f"📛 {product.name}\n"
        f"💰 {fmt_price(float(product.price))}\n"
        f"📦 Ombor: {product.stock} kg\n"
        f"📌 {status_str}",
        reply_markup=None,
    )
    _clear(context)
    return ConversationHandler.END


# ══ EDIT ═════════════════════════════════════════════════════════

async def edit_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update): return ConversationHandler.END
    _clear(context)
    async with get_session() as s:
        products = await get_all_products(s)
    if not products:
        await update.message.reply_text("📭 Mahsulotlar yo'q."); return ConversationHandler.END
    await update.message.reply_text(
        "✏️ <b>Tahrirlash uchun mahsulot:</b>", parse_mode="HTML",
        reply_markup=admin_products_kb(products, action="edit"),
    )
    return EDIT_SELECT_PRODUCT


async def edit_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    product_id = int(query.data.split(":")[2])
    _ctx(context)["product_id"] = product_id
    async with get_session() as s:
        product = await get_product(s, product_id)
    if not product:
        await safe_edit(query.message, "❌ Topilmadi."); return ConversationHandler.END
    await safe_edit(
        query.message,
        f"✏️ <b>{product.name}</b>\n📦 Ombor: {product.stock} kg\nQaysi maydon?",
        reply_markup=admin_edit_fields_kb(product_id),
    )
    return EDIT_SELECT_FIELD


async def edit_field_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    field = query.data.split(":")[2]
    _ctx(context)["edit_field"] = field
    if field == "status":
        await safe_edit(query.message, "📌 Status:", reply_markup=admin_status_kb(_ctx(context)["product_id"]))
        return EDIT_VALUE
    prompts = {
        "name": "✏️ Yangi nom:", "price": "💰 Yangi narx (so'm):",
        "description": "📝 Yangi tavsif:", "photo": "🖼 Yangi rasm:",
        "stock": "📦 Yangi ombor miqdori (kg, masalan: 10 yoki 0.5):",
    }
    await safe_edit(query.message, prompts.get(field, "Qiymat:"))
    return EDIT_VALUE


async def edit_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_id = _ctx(context)["product_id"]
    field = _ctx(context).get("edit_field")
    if update.callback_query:
        query = update.callback_query; await query.answer()
        is_active = query.data.split(":")[2] == "1"
        async with get_session() as s:
            await update_product(s, product_id, is_active=is_active)
        await safe_edit(query.message, "✅ Status yangilandi.")
        _clear(context); return ConversationHandler.END
    msg = update.message
    kwargs: dict = {}
    if field == "name":
        if len(msg.text.strip()) < 2:
            await msg.reply_text("❌ Juda qisqa. Qaytadan:"); return EDIT_VALUE
        kwargs["name"] = msg.text.strip()
    elif field == "price":
        if not is_valid_price(msg.text):
            await msg.reply_text("❌ Noto'g'ri. Qaytadan:"); return EDIT_VALUE
        kwargs["price"] = parse_price(msg.text)
    elif field == "stock":
        text = msg.text.strip().replace(",", ".")
        try:
            stock_val = round(float(text), 1)
            if stock_val < 0:
                raise ValueError
            kwargs["stock"] = stock_val
        except ValueError:
            await msg.reply_text("❌ Noto'g'ri. Musbat son kiriting (masalan: 10 yoki 0.5):"); return EDIT_VALUE
    elif field == "description":
        kwargs["description"] = msg.text.strip()
    elif field == "photo":
        if not msg.photo:
            await msg.reply_text("❌ Faqat rasm yuboring."); return EDIT_VALUE
        kwargs["photo_file_id"] = msg.photo[-1].file_id
    async with get_session() as s:
        await update_product(s, product_id, **kwargs)
    await msg.reply_text("✅ Yangilandi!", reply_markup=admin_main_kb())
    _clear(context); return ConversationHandler.END


# ══ DELETE ═══════════════════════════════════════════════════════

async def del_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update): return ConversationHandler.END
    async with get_session() as s:
        products = await get_all_products(s)
    if not products:
        await update.message.reply_text("📭 Mahsulotlar yo'q."); return ConversationHandler.END
    await update.message.reply_text(
        "🗑 <b>O'chirish uchun mahsulot:</b>", parse_mode="HTML",
        reply_markup=admin_products_kb(products, action="del"),
    )
    return DEL_SELECT


async def del_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    product_id = int(query.data.split(":")[2])
    async with get_session() as s:
        ok = await delete_product(s, product_id)
    await safe_edit(query.message, "✅ O'chirildi." if ok else "❌ Topilmadi.")
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _clear(context)
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query.message, "❌ Bekor qilindi.")
    else:
        await update.message.reply_text("❌ Bekor qilindi.", reply_markup=admin_main_kb())
    return ConversationHandler.END


# ══ BUILDERS ═════════════════════════════════════════════════════

def build_add_product_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(PRIVATE_ONLY & filters.Regex("^➕ Mahsulot qo'shish$"), add_product_start)],
        states={
            ADD_CAT_SELECT:   [CallbackQueryHandler(add_cat_selected, pattern=r"^adm_cat:(sel|new):\d+$"), CallbackQueryHandler(admin_cancel, pattern=r"^adm:cancel$")],
            ADD_CAT_NEW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cat_new_name)],
            ADD_NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_PRICE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_DESCRIPTION:  [CallbackQueryHandler(add_description, pattern=r"^adm:skip$"), MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)],
            ADD_PHOTO:        [CallbackQueryHandler(add_photo, pattern=r"^adm:skip$"), MessageHandler(filters.PHOTO, add_photo), MessageHandler(filters.TEXT & ~filters.COMMAND, add_photo)],
            ADD_STOCK:        [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock)],
            ADD_STATUS:       [CallbackQueryHandler(add_status_selected, pattern=r"^adm_status:-1:[01]$")],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel), CallbackQueryHandler(admin_cancel, pattern=r"^adm:cancel$")],
        conversation_timeout=300, allow_reentry=True, name="add_product",
    )


def build_edit_product_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(PRIVATE_ONLY & filters.Regex("^✏️ Mahsulotni tahrirlash$"), edit_product_start)],
        states={
            EDIT_SELECT_PRODUCT: [CallbackQueryHandler(edit_product_selected, pattern=r"^adm_prod:edit:\d+$"), CallbackQueryHandler(admin_cancel, pattern=r"^adm:cancel$")],
            EDIT_SELECT_FIELD:   [CallbackQueryHandler(edit_field_selected, pattern=r"^adm_edit:\d+:\w+$"), CallbackQueryHandler(admin_cancel, pattern=r"^adm:cancel$")],
            EDIT_VALUE: [
                CallbackQueryHandler(edit_value_received, pattern=r"^adm_status:\d+:[01]$"),
                CallbackQueryHandler(admin_cancel, pattern=r"^adm:cancel$"),
                MessageHandler(filters.PHOTO, edit_value_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel), CallbackQueryHandler(admin_cancel, pattern=r"^adm:cancel$")],
        conversation_timeout=300, allow_reentry=True, name="edit_product",
    )


def build_del_product_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(PRIVATE_ONLY & filters.Regex("^🗑 Mahsulot o'chirish$"), del_product_start)],
        states={DEL_SELECT: [CallbackQueryHandler(del_product_confirm, pattern=r"^adm_prod:del:\d+$"), CallbackQueryHandler(admin_cancel, pattern=r"^adm:cancel$")]},
        fallbacks=[CommandHandler("cancel", admin_cancel)],
        conversation_timeout=120, allow_reentry=True, name="del_product",
    )
