from datetime import datetime

import aiosqlite
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Contact, Message

from bot.keyboards.client_kb import (
    main_menu_keyboard,
    main_reply_keyboard,
    phone_keyboard,
    remove_keyboard,
)
from bot.models.database import (
    confirm_booking_by_reminder,
    create_booking,
    delete_pending_slot_claim,
    get_client_by_telegram_id,
    get_group_slot,
    get_pending_slot_claim,
    get_service,
    link_vip_to_client,
    mark_group_slot_booked,
    merge_virtual_client,
    update_group_slot_message,
    upsert_client,
)
from bot.services.booking_service import create_new_booking
from bot.services.calendar_service import CalendarService
from bot.services.ics_generator import generate_ics
from bot.services.reminder_service import ReminderService
from bot.states.booking import RegistrationStates
from bot.utils.datetime_helpers import (
    format_date_uk,
    format_time,
    kyiv_to_utc,
    make_kyiv_dt,
    utc_to_kyiv,
)
from bot.utils.texts import (
    ALREADY_REGISTERED,
    GROUP_BOOKING_PENDING_COMPLETE,
    GROUP_BOOKING_PENDING_TAKEN,
    ICS_FILENAME,
    MAIN_MENU,
    MONTHS_UK,
    NEW_BOOKING_ADMIN,
    REGISTER_ENTER_FIRST_NAME,
    REGISTER_ENTER_LAST_NAME,
    REGISTER_SHARE_PHONE,
    URGENT_BOOKING_ADMIN,
    WELCOME,
)

router = Router()


@router.message(CommandStart())
async def start_handler(
    message: Message, state: FSMContext, db: aiosqlite.Connection, admin_ids: list[int]
) -> None:
    await state.clear()

    # Check for deeplink payload (e.g. claim_{slot_id})
    payload = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else ""
    if payload.startswith("claim_"):
        try:
            slot_id = int(payload.split("_", 1)[1])
            await state.update_data(pending_slot_id=slot_id)
        except (ValueError, IndexError):
            pass

    client = await get_client_by_telegram_id(db, message.from_user.id)
    is_admin = message.from_user.id in admin_ids

    if client and client.get("phone"):
        # Already registered — show main menu
        await message.answer(
            ALREADY_REGISTERED.format(name=client["first_name"]),
            reply_markup=main_reply_keyboard(is_admin),
        )
        await message.answer(MAIN_MENU, reply_markup=main_menu_keyboard())

        # Process pending slot claim if came via deeplink
        fsm_data = await state.get_data()
        pending_slot_id = fsm_data.get("pending_slot_id")
        if pending_slot_id:
            await _process_pending_slot(message, db, client, pending_slot_id, state, admin_ids)
    else:
        # Start registration
        await state.set_state(RegistrationStates.enter_first_name)
        await message.answer(WELCOME)
        await message.answer(REGISTER_ENTER_FIRST_NAME)


@router.message(RegistrationStates.enter_first_name)
async def enter_first_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Будь ласка, введіть коректне ім'я (мінімум 2 символи):")
        return
    await state.update_data(reg_first_name=name)
    await state.set_state(RegistrationStates.enter_last_name)
    await message.answer(REGISTER_ENTER_LAST_NAME)


@router.message(RegistrationStates.enter_last_name)
async def enter_last_name(message: Message, state: FSMContext) -> None:
    last = (message.text or "").strip()
    if len(last) < 2:
        await message.answer("Будь ласка, введіть коректне прізвище (мінімум 2 символи):")
        return
    await state.update_data(reg_last_name=last)
    await state.set_state(RegistrationStates.wait_phone)
    await message.answer(REGISTER_SHARE_PHONE, reply_markup=phone_keyboard())


@router.message(RegistrationStates.wait_phone, F.contact)
async def contact_handler(
    message: Message,
    state: FSMContext,
    db: aiosqlite.Connection,
    admin_ids: list[int],
    calendar: CalendarService,
    reminder_service: ReminderService,
    therapist_name: str,
    location: str,
) -> None:
    contact: Contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("Будь ласка, поділіться своїм власним номером телефону.")
        return

    fsm_data = await state.get_data()
    first_name = fsm_data.get("reg_first_name") or message.from_user.first_name
    last_name = fsm_data.get("reg_last_name") or message.from_user.last_name

    real_client_id = await upsert_client(
        db,
        telegram_id=message.from_user.id,
        first_name=first_name,
        last_name=last_name,
        phone=contact.phone_number,
        username=message.from_user.username,
    )
    await merge_virtual_client(db, real_client_id, contact.phone_number)
    await link_vip_to_client(db, contact.phone_number, real_client_id)

    is_admin = message.from_user.id in admin_ids
    await message.answer("Реєстрацію завершено!", reply_markup=remove_keyboard())
    await message.answer(MAIN_MENU, reply_markup=main_reply_keyboard(is_admin))
    await message.answer("Що бажаєте?", reply_markup=main_menu_keyboard())

    # Process pending group slot claim
    pending_slot_id = fsm_data.get("pending_slot_id")
    if pending_slot_id:
        client = await get_client_by_telegram_id(db, message.from_user.id)
        await _process_pending_slot(
            message, db, client, pending_slot_id, state,
            admin_ids, calendar, reminder_service, therapist_name, location,
        )
    else:
        # Check if there's a pending claim saved earlier (before registration)
        claim = await get_pending_slot_claim(db, message.from_user.id)
        if claim and not claim["is_booked"]:
            client = await get_client_by_telegram_id(db, message.from_user.id)
            await _process_pending_slot(
                message, db, client, claim["slot_id"], state,
                admin_ids, calendar, reminder_service, therapist_name, location,
            )
            await delete_pending_slot_claim(db, message.from_user.id)

    await state.clear()


async def _process_pending_slot(
    message: Message,
    db: aiosqlite.Connection,
    client: dict,
    slot_id: int,
    state: FSMContext,
    admin_ids: list[int],
    calendar: CalendarService = None,
    reminder_service: ReminderService = None,
    therapist_name: str = "",
    location: str = "",
) -> None:
    """Book an available group slot for the client after registration/return."""
    from bot.utils.datetime_helpers import KYIV_TZ
    from datetime import datetime, timedelta
    import logging
    logger = logging.getLogger(__name__)

    slot = await get_group_slot(db, slot_id)
    if not slot or slot["is_booked"]:
        await message.answer(GROUP_BOOKING_PENDING_TAKEN)
        return

    start_utc = datetime.fromisoformat(slot["start_time"])
    end_utc = datetime.fromisoformat(slot["end_time"])
    start_kyiv = utc_to_kyiv(start_utc)
    end_kyiv = utc_to_kyiv(end_utc)

    # Create the booking directly (skip availability check — slot was freed by cancellation)
    service = await get_service(db, slot["service_id"])
    if not service:
        return

    try:
        from bot.services.calendar_service import CalendarService as CS
        if calendar:
            from bot.services.booking_service import create_new_booking as cnb
            booking_id = await cnb(
                db, calendar, client["id"], service,
                start_kyiv.date(), start_kyiv.time(),
                skip_availability_check=True,
            )
        else:
            booking_id = None
    except Exception as e:
        logger.error("Failed to create group slot booking: %s", e)
        booking_id = None

    if not booking_id:
        await message.answer(GROUP_BOOKING_PENDING_TAKEN)
        return

    await mark_group_slot_booked(db, slot_id)

    # Edit group message if possible
    if slot.get("group_message_id") and slot.get("group_chat_id"):
        try:
            from bot.utils.texts import GROUP_SLOT_BOOKED
            bot = message.bot
            await bot.edit_message_text(
                chat_id=slot["group_chat_id"],
                message_id=slot["group_message_id"],
                text=GROUP_SLOT_BOOKED,
            )
        except Exception:
            pass

    date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
    time_label = format_time(start_kyiv.time())

    await message.answer(
        GROUP_BOOKING_PENDING_COMPLETE.format(
            service=service["name"],
            date=date_label,
            time_start=time_label,
        )
    )

    # Schedule reminders
    if reminder_service:
        from bot.models.database import get_booking
        booking = await get_booking(db, booking_id)
        if booking:
            booking_start_utc = datetime.fromisoformat(booking["start_time"])
            reminder_service.schedule_reminders(booking_id, booking_start_utc)

    # Send ICS
    if therapist_name is not None:
        ics_bytes = generate_ics(
            service_name=service["name"],
            start=start_kyiv,
            end=end_kyiv,
            therapist_name=therapist_name,
            location=location,
        )
        filename = ICS_FILENAME.format(
            date=start_kyiv.date().isoformat(),
            time=start_kyiv.strftime("%H%M"),
        )
        await message.answer_document(
            BufferedInputFile(ics_bytes, filename=filename),
            caption="Додайте до вашого календаря",
        )

    # Notify admins
    name = f"{client['first_name']} {client.get('last_name') or ''}".strip()
    phone = client.get("phone") or "—"
    notify_text = NEW_BOOKING_ADMIN.format(
        client=name,
        service=service["name"],
        date=date_label,
        time=time_label,
        phone=phone,
    )
    bot = message.bot
    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=notify_text)
        except Exception:
            pass
