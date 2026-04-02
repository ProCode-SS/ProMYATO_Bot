from aiogram import Router
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.handlers.admin import bookings, manual_booking, schedule, services, vip


class AdminFilter(Filter):
    async def __call__(self, event: TelegramObject, admin_ids: list[int]) -> bool:
        if isinstance(event, (Message, CallbackQuery)):
            return event.from_user is not None and event.from_user.id in admin_ids
        return False


def get_admin_router() -> Router:
    router = Router()
    router.message.filter(AdminFilter())
    router.callback_query.filter(AdminFilter())

    router.include_router(services.router)
    router.include_router(schedule.router)
    router.include_router(bookings.router)
    router.include_router(manual_booking.router)
    router.include_router(vip.router)

    return router
