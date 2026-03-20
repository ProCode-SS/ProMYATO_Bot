import aiosqlite
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Contact, Message

from bot.keyboards.client_kb import main_menu_keyboard, phone_keyboard, remove_keyboard
from bot.models.database import get_client_by_telegram_id, merge_virtual_client, upsert_client
from bot.utils.texts import ALREADY_REGISTERED, MAIN_MENU, WELCOME

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, db: aiosqlite.Connection) -> None:
    client = await get_client_by_telegram_id(db, message.from_user.id)
    if client and client.get("phone"):
        await message.answer(
            ALREADY_REGISTERED.format(name=message.from_user.first_name),
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(WELCOME, reply_markup=phone_keyboard())


@router.message(F.contact)
async def contact_handler(message: Message, db: aiosqlite.Connection) -> None:
    contact: Contact = message.contact
    if contact.user_id != message.from_user.id:
        return

    real_client_id = await upsert_client(
        db,
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        phone=contact.phone_number,
        username=message.from_user.username,
    )
    await merge_virtual_client(db, real_client_id, contact.phone_number)
    await message.answer("Дякуємо!", reply_markup=remove_keyboard())
    await message.answer(MAIN_MENU, reply_markup=main_menu_keyboard())
