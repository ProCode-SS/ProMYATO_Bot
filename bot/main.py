import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import settings
from bot.handlers import get_main_router
from bot.middlewares.db import DatabaseMiddleware
from bot.models.database import init_db, seed_default_services
from bot.services.calendar_service import CalendarService
from bot.services.reminder_service import ReminderService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db(settings.DATABASE_PATH)
    await seed_default_services(settings.DATABASE_PATH)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Fetch bot username for deeplinks
    bot_info = await bot.get_me()
    bot_username = bot_info.username

    calendar = CalendarService(
        calendar_id=settings.GOOGLE_CALENDAR_ID,
        service_account_file=settings.GOOGLE_SERVICE_ACCOUNT_FILE,
    )

    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
    reminder_service = ReminderService(
        scheduler=scheduler,
        bot=bot,
        db_path=settings.DATABASE_PATH,
        calendar=calendar,
        admin_ids=settings.admin_ids,
        cancellation_group_id=settings.CANCELLATION_GROUP_ID,
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Inject shared dependencies into all handlers
    dp["calendar"] = calendar
    dp["reminder_service"] = reminder_service
    dp["admin_ids"] = settings.admin_ids
    dp["therapist_name"] = settings.THERAPIST_NAME
    dp["location"] = settings.LOCATION
    dp["cancellation_group_id"] = settings.CANCELLATION_GROUP_ID
    dp["bot_username"] = bot_username

    # DB middleware: opens a connection per request
    dp.message.middleware(DatabaseMiddleware(settings.DATABASE_PATH))
    dp.callback_query.middleware(DatabaseMiddleware(settings.DATABASE_PATH))

    dp.include_router(get_main_router(settings.admin_ids))

    @dp.errors()
    async def error_handler(event: ErrorEvent) -> bool:
        if isinstance(event.exception, TelegramBadRequest) and "message is not modified" in str(event.exception):
            return True  # silently ignore
        logger.error("Unhandled error: %s", event.exception, exc_info=event.exception)
        return False

    scheduler.start()
    await reminder_service.reschedule_all()

    # Startup calendar check
    from datetime import date
    try:
        await calendar.get_busy_slots(date.today(), date.today())
        logger.info("Google Calendar OK — connected to %s", settings.GOOGLE_CALENDAR_ID)
    except Exception as e:
        logger.warning("Google Calendar NOT connected: %s", e)

    logger.info(
        "Bot started. Username: @%s | Admin IDs: %s | Group: %s",
        bot_username,
        settings.admin_ids,
        settings.CANCELLATION_GROUP_ID or "not set",
    )
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
