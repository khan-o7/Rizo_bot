"""Food Bot — asosiy ishga tushurish nuqtasi."""
from __future__ import annotations
import logging, sys, warnings
warnings.filterwarnings("ignore", message="If 'per_message=False'")

from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

from config import config
from db.session import init_db
from handlers.admin.broadcast import build_broadcast_conv
from handlers.admin.menu import register_admin_menu_handlers
from handlers.admin.orders import register_admin_order_handlers
from handlers.admin.products import (
    build_add_product_conv, build_del_product_conv, build_edit_product_conv,
)
from handlers.admin.warehouse import register_warehouse_handlers
from handlers.admin.archive_stats import register_archive_handlers
from handlers.admin.courier_archive import register_courier_archive_handlers
from handlers.cart import register_cart_handlers
from handlers.catalog import register_catalog_handlers
from handlers.checkout import build_checkout_conv
from handlers.courier import register_courier_handlers
from handlers.orders import register_orders_handlers
from handlers.start import register_start_handlers

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO, stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logger = logging.getLogger("food_bot")


async def post_init(app: Application) -> None:
    await init_db()
    logger.info("✅ DB tayyor.")
    logger.info(f"👑 Adminlar: {config.ADMIN_IDS}")
    if config.has_courier_group():
        logger.info(f"🚴 Kuryer guruhi: {config.COURIER_GROUP_ID}")
    else:
        logger.warning("⚠️  Kuryer guruhi sozlanmagan (COURIER_GROUP_ID yo'q)")

    # Arxiv — o'tkazib yuborilgan oy/yillarni to'ldirish
    from services.archive_service import run_missing_archives
    try:
        await run_missing_archives()
    except Exception as e:
        logger.warning(f"⚠️ Arxiv tekshiruv xatosi: {e}")

    # Scheduler — oylik va yillik avtomatik arxivlash
    _setup_archive_scheduler(app)


async def group_message_filter(update: object, context) -> bool:
    """
    Guruh/supergroup xabarlarini filtrlash.
    Faqat inline keyboard callbacklari (courier_accept/courier_done) o'tkaziladi.
    Boshqa barcha guruh xabarlari (matnlar, buyruqlar) ignore.
    """
    from telegram import Update as TGUpdate
    if not isinstance(update, TGUpdate):
        return True  # error updates o'tsin

    chat = update.effective_chat
    if chat is None:
        return True

    # Guruh yoki supergroup
    if chat.type in ("group", "supergroup"):
        # Faqat courier callbacklar ruxsat
        if update.callback_query:
            data = update.callback_query.data or ""
            if data.startswith("courier_accept:") or data.startswith("courier_done:"):
                return True  # ruxsat beramiz
        # Boshqa barcha guruh xabarlari — jim o'tkazib yuboramiz
        return False

    return True  # private, channel — o'tsin


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("🚨 Exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Texnik xatolik yuz berdi. Qaytadan urinib ko'ring yoki /start bosing."
            )
        except Exception:
            pass
    if config.ADMIN_IDS:
        try:
            import traceback
            tb = "".join(traceback.format_exception(
                type(context.error), context.error, context.error.__traceback__
            ))
            await context.bot.send_message(
                chat_id=config.ADMIN_IDS[0],
                text=f"🚨 <b>Bot xatosi:</b>\n<code>{tb[-2000:]}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass


def _setup_archive_scheduler(app: Application) -> None:
    """APScheduler yordamida oylik va yillik arxivni avtomatlashtirish."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from services.archive_service import job_monthly_archive, job_yearly_archive

        scheduler = AsyncIOScheduler()
        # Har oy 1-sanasi soat 00:05 — oylik arxiv
        scheduler.add_job(
            job_monthly_archive,
            CronTrigger(day=1, hour=0, minute=5),
            id="monthly_archive", replace_existing=True,
        )
        # Har yil 1-yanvar soat 00:10 — yillik arxiv
        scheduler.add_job(
            job_yearly_archive,
            CronTrigger(month=1, day=1, hour=0, minute=10),
            id="yearly_archive", replace_existing=True,
        )
        scheduler.start()
        logger.info("✅ Arxiv scheduler ishga tushdi (oylik: 1-san 00:05, yillik: 1-yan 00:10)")
    except ImportError:
        logger.warning("⚠️  apscheduler o'rnatilmagan. Arxiv avtomatlashmaydi. pip install apscheduler")
    except Exception as e:
        logger.warning(f"⚠️  Scheduler xatosi: {e}")


def main() -> None:
    logger.info("🚀 Bot ishga tushmoqda...")
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    # Guruh filtr — birinchi! Guruhdan kelgan barcha xabarlar (courier_accept/done bundan mustasno) ignore
    from telegram.ext import TypeHandler as _TypeHandler
    async def _group_guard(upd, ctx):
        from telegram import Update as _U
        if not isinstance(upd, _U):
            return
        chat = upd.effective_chat
        if chat and chat.type in ("group", "supergroup"):
            if upd.callback_query:
                d = upd.callback_query.data or ""
                if d.startswith("courier_accept:") or d.startswith("courier_done:"):
                    return  # ruxsat — boshqa handlerlar davom ettirsin
            # Guruh xabari — jim turib o'tkazib yuborish
            if upd.message or upd.edited_message:
                return  # hech narsa qilmaymiz

    # ConversationHandler'lar (priority: birinchi qo'shilgani ustunlik oladi)
    app.add_handler(build_checkout_conv())
    app.add_handler(build_add_product_conv())
    app.add_handler(build_edit_product_conv())
    app.add_handler(build_del_product_conv())
    app.add_handler(build_broadcast_conv())

    # Oddiy handler'lar
    register_start_handlers(app)
    register_catalog_handlers(app)
    register_cart_handlers(app)
    register_orders_handlers(app)         # user_cancel_conv ichida
    register_admin_order_handlers(app)    # admin_cancel_conv ichida
    register_admin_menu_handlers(app)
    register_warehouse_handlers(app)
    register_archive_handlers(app)        # 📊 Arxiv statistika
    register_courier_archive_handlers(app)  # kuryer arxiv + admin kuryer stat
    register_courier_handlers(app)        # kuryer guruh callbacklari

    app.add_error_handler(error_handler)
    logger.info("✅ Barcha handler'lar tayyor!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()