from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.admin import get_admin_router
from bot.handlers.client import booking, confirmation, group_booking, my_bookings, start
from bot.keyboards.admin_kb import admin_menu_keyboard
from bot.keyboards.client_kb import main_menu_keyboard, main_reply_keyboard
from bot.models.database import get_client_by_telegram_id
from bot.utils.texts import ADMIN_BUTTON, ADMIN_MENU, ALREADY_REGISTERED, MAIN_MENU, MENU_BUTTON, NOT_ADMIN


def get_main_router(admin_ids: list[int]) -> Router:
    router = Router()

    # ── Client routers ──────────────────────────────────────────────────────
    router.include_router(start.router)
    router.include_router(booking.router)
    router.include_router(my_bookings.router)
    router.include_router(confirmation.router)
    router.include_router(group_booking.router)

    # ── Persistent Reply Keyboard handlers ──────────────────────────────────
    # These fire regardless of FSM state because there is no StateFilter here.

    @router.message(F.text == MENU_BUTTON)
    async def main_menu_button(
        message: Message, state: FSMContext, db
    ) -> None:
        await state.clear()
        client = await get_client_by_telegram_id(db, message.from_user.id)
        is_admin = message.from_user.id in admin_ids
        name = client["first_name"] if client else message.from_user.first_name
        await message.answer(
            ALREADY_REGISTERED.format(name=name),
            reply_markup=main_reply_keyboard(is_admin),
        )
        await message.answer(MAIN_MENU, reply_markup=main_menu_keyboard())

    @router.message(F.text == ADMIN_BUTTON)
    async def admin_menu_button(message: Message, state: FSMContext) -> None:
        if message.from_user.id not in admin_ids:
            await message.answer(NOT_ADMIN)
            return
        await state.clear()
        await message.answer(ADMIN_MENU, reply_markup=admin_menu_keyboard())

    # ── /admin command ───────────────────────────────────────────────────────

    @router.message(Command("admin"))
    async def admin_cmd(message: Message, state: FSMContext) -> None:
        if message.from_user.id not in admin_ids:
            await message.answer(NOT_ADMIN)
            return
        await state.clear()
        await message.answer(ADMIN_MENU, reply_markup=admin_menu_keyboard())

    @router.callback_query(F.data == "admin:menu")
    async def admin_menu_back(call: CallbackQuery) -> None:
        await call.message.edit_text(ADMIN_MENU, reply_markup=admin_menu_keyboard())
        await call.answer()

    @router.callback_query(F.data == "noop")
    async def noop(call: CallbackQuery) -> None:
        await call.answer()

    @router.callback_query(F.data == "menu:back")
    async def main_menu_back(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await call.message.edit_text(MAIN_MENU, reply_markup=main_menu_keyboard())
        await call.answer()

    router.include_router(get_admin_router())

    return router
