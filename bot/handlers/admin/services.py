import aiosqlite
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.admin_kb import admin_menu_keyboard, services_list_keyboard
from bot.models.database import add_service, get_all_services, toggle_service
from bot.states.booking import AdminServiceStates
from bot.utils.texts import (
    NO_SERVICES,
    SERVICE_ADD_DESC,
    SERVICE_ADD_DURATION,
    SERVICE_ADD_NAME,
    SERVICE_ADD_PRICE,
    SERVICE_ADDED,
    SERVICE_TOGGLED,
    SERVICES_LIST,
)

router = Router()


@router.callback_query(F.data == "admin:services")
async def services_menu(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    services = await get_all_services(db)
    if not services:
        kb = InlineKeyboardBuilder()
        kb.button(text="Додати послугу", callback_data="admin:add_service")
        kb.button(text="Назад", callback_data="admin:menu")
        kb.adjust(1)
        await call.message.edit_text(NO_SERVICES, reply_markup=kb.as_markup())
    else:
        await call.message.edit_text(SERVICES_LIST, reply_markup=services_list_keyboard(services))
    await call.answer()


@router.callback_query(F.data.startswith("admin:toggle_svc:"))
async def toggle_service_handler(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    service_id = int(call.data.split(":")[-1])
    await toggle_service(db, service_id)
    services = await get_all_services(db)
    await call.message.edit_text(SERVICES_LIST, reply_markup=services_list_keyboard(services))
    await call.answer(SERVICE_TOGGLED)


@router.callback_query(F.data == "admin:add_service")
async def add_service_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminServiceStates.add_name)
    await call.message.answer(SERVICE_ADD_NAME)
    await call.answer()


@router.message(AdminServiceStates.add_name)
async def add_service_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(SERVICE_ADD_NAME)
        return
    await state.update_data(name=name)
    await state.set_state(AdminServiceStates.add_duration)
    await message.answer(SERVICE_ADD_DURATION)


@router.message(AdminServiceStates.add_duration)
async def add_service_duration(message: Message, state: FSMContext) -> None:
    try:
        duration = int((message.text or "").strip())
        if duration <= 0:
            raise ValueError
    except ValueError:
        await message.answer(SERVICE_ADD_DURATION)
        return
    await state.update_data(duration=duration)
    await state.set_state(AdminServiceStates.add_price)
    await message.answer(SERVICE_ADD_PRICE)


@router.message(AdminServiceStates.add_price)
async def add_service_price(message: Message, state: FSMContext) -> None:
    try:
        price = int((message.text or "").strip())
    except ValueError:
        await message.answer(SERVICE_ADD_PRICE)
        return
    await state.update_data(price=price if price > 0 else None)
    await state.set_state(AdminServiceStates.add_description)
    await message.answer(SERVICE_ADD_DESC)


@router.message(AdminServiceStates.add_description)
async def add_service_description(
    message: Message, state: FSMContext, db: aiosqlite.Connection
) -> None:
    desc = (message.text or "").strip()
    if desc == "-":
        desc = None
    data = await state.get_data()
    await add_service(db, data["name"], data["duration"], data.get("price"), desc)
    await state.clear()
    services = await get_all_services(db)
    await message.answer(SERVICE_ADDED, reply_markup=services_list_keyboard(services))
