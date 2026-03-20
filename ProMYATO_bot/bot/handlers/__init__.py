from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.handlers.admin import get_admin_router
from bot.handlers.client import booking, my_bookings, start
from bot.keyboards.admin_kb import admin_menu_keyboard
from bot.utils.texts import ADMIN_MENU, NOT_ADMIN


def get_main_router(admin_ids: list[int]) -> Router:
    router = Router()

    router.include_router(start.router)
    router.include_router(booking.router)
    router.include_router(my_bookings.router)

    @router.message(Command("admin"))
    async def admin_cmd(message: Message) -> None:
        if message.from_user.id not in admin_ids:
            await message.answer(NOT_ADMIN)
            return
        await message.answer(ADMIN_MENU, reply_markup=admin_menu_keyboard())

    @router.callback_query(F.data == "admin:menu")
    async def admin_menu_back(call: CallbackQuery) -> None:
        await call.message.edit_text(ADMIN_MENU, reply_markup=admin_menu_keyboard())
        await call.answer()

    @router.callback_query(F.data == "noop")
    async def noop(call: CallbackQuery) -> None:
        await call.answer()

    router.include_router(get_admin_router())

    return router
