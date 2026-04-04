"""VIP client management and batch booking for VIP clients."""
import re
import urllib.parse
from datetime import date, datetime, time, timedelta

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.admin_kb import (
    admin_menu_keyboard,
    vip_confirm_add_keyboard,
    vip_confirm_phone_keyboard,
    vip_list_keyboard,
    vip_menu_keyboard,
    vip_search_results_keyboard,
    vip_select_for_booking_keyboard,
)
from bot.keyboards.client_kb import (
    confirm_keyboard,
    dates_multiselect_keyboard,
    services_keyboard,
)
from bot.models.database import (
    add_vip_client,
    get_active_services,
    get_all_vips,
    get_client_by_phone,
    get_service,
    get_vip_by_phone,
    is_bookings_open,
    remove_vip_client,
    search_clients_by_name,
    upsert_virtual_client,
)
from bot.services.booking_service import create_new_booking
from bot.services.calendar_service import CalendarService
from bot.services.reminder_service import ReminderService
from bot.states.booking import AdminVIPBookingStates, AdminVIPStates
from bot.utils.datetime_helpers import format_date_uk, kyiv_now
from bot.utils.texts import (
    ADMIN_MANUAL_BOOKING_NOTIFY,
    MONTHS_UK,
    VIP_ADD_BY_PHONE,
    VIP_ADDED,
    VIP_ALREADY_EXISTS,
    VIP_BOOKING_CONFIRM,
    VIP_BOOKING_CREATED,
    VIP_BOOKING_ENTER_TIME,
    VIP_BOOKING_INVALID_TIME,
    VIP_BOOKING_NO_DATES,
    VIP_BOOKING_SELECT_DATES,
    VIP_LIST_EMPTY,
    VIP_LIST_HEADER,
    VIP_MENU,
    VIP_NOT_REGISTERED,
    VIP_REMOVED,
    VIP_SEARCH_BY_NAME,
    VIP_SEARCH_NO_RESULTS,
    VIP_SELECT_FOR_BOOKING,
)

router = Router()

# VIP booking uses dates up to 2 years ahead for admin (unlimited for practical purposes)
VIP_BOOKING_DAYS_AHEAD = 365


# ─── VIP Menu ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:vip")
async def vip_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(VIP_MENU, reply_markup=vip_menu_keyboard())
    await call.answer()


# ─── List VIPs ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "vip:list")
async def vip_list(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    vips = await get_all_vips(db)
    if not vips:
        await call.message.edit_text(VIP_LIST_EMPTY, reply_markup=vip_menu_keyboard())
        await call.answer()
        return

    lines = [VIP_LIST_HEADER]
    for v in vips:
        first = v.get("first_name") or ""
        last = v.get("last_name") or ""
        name = f"{first} {last}".strip() or "—"
        phone = v.get("phone") or "—"
        lines.append(f"👑 {name} — {phone}")

    await call.message.edit_text(
        "\n".join(lines), reply_markup=vip_list_keyboard(vips)
    )
    await call.answer()


@router.callback_query(F.data.startswith("vip:remove:"))
async def vip_remove(call: CallbackQuery, db: aiosqlite.Connection) -> None:
    vip_id = int(call.data.split(":")[2])
    await remove_vip_client(db, vip_id)
    await call.answer(VIP_REMOVED, show_alert=True)
    vips = await get_all_vips(db)
    if not vips:
        await call.message.edit_text(VIP_LIST_EMPTY, reply_markup=vip_menu_keyboard())
    else:
        lines = [VIP_LIST_HEADER]
        for v in vips:
            first = v.get("first_name") or ""
            last = v.get("last_name") or ""
            name = f"{first} {last}".strip() or "—"
            phone = v.get("phone") or "—"
            lines.append(f"👑 {name} — {phone}")
        await call.message.edit_text(
            "\n".join(lines), reply_markup=vip_list_keyboard(vips)
        )


# ─── Add VIP by phone ────────────────────────────────────────────────────────

@router.callback_query(F.data == "vip:add_phone")
async def vip_add_phone_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminVIPStates.add_by_phone)
    await call.message.edit_text(VIP_ADD_BY_PHONE, reply_markup=None)
    await call.answer()


@router.message(AdminVIPStates.add_by_phone)
async def vip_add_phone_input(
    message: Message, state: FSMContext, db: aiosqlite.Connection
) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer(VIP_ADD_BY_PHONE)
        return

    existing_vip = await get_vip_by_phone(db, phone)
    if existing_vip:
        await state.clear()
        await message.answer(VIP_ALREADY_EXISTS, reply_markup=vip_menu_keyboard())
        return

    client = await get_client_by_phone(db, phone)
    if client:
        # Client is registered — show confirmation
        name = f"{client['first_name']} {client.get('last_name') or ''}".strip()
        await state.update_data(vip_client_id=client["id"], vip_phone=phone)
        await state.set_state(AdminVIPStates.confirm_add)
        await message.answer(
            f"Клієнт знайдений: {name} ({phone})\nДодати до VIP?",
            reply_markup=vip_confirm_add_keyboard(client["id"]),
        )
    else:
        # Client not registered — offer to save phone for future registration
        await message.answer(
            VIP_NOT_REGISTERED.format(phone=phone),
            reply_markup=vip_confirm_phone_keyboard(phone),
        )
        await state.clear()


@router.callback_query(F.data.startswith("vip:confirm_add:"))
async def vip_confirm_add(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    client_id = int(call.data.split(":")[2])
    data = await state.get_data()
    phone = data.get("vip_phone", "")

    # Get phone from client if not in state
    if not phone:
        async with db.execute("SELECT phone FROM clients WHERE id = ?", (client_id,)) as cur:
            row = await cur.fetchone()
            phone = row[0] if row else ""

    await add_vip_client(db, phone, client_id=client_id)
    await state.clear()
    await call.answer(VIP_ADDED, show_alert=True)
    await call.message.edit_text(VIP_MENU, reply_markup=vip_menu_keyboard())


@router.callback_query(F.data.startswith("vip:confirm_phone:"))
async def vip_confirm_phone(
    call: CallbackQuery, db: aiosqlite.Connection
) -> None:
    encoded = call.data.split(":", 2)[2]
    phone = urllib.parse.unquote(encoded)
    await add_vip_client(db, phone, client_id=None)
    await call.answer(VIP_ADDED, show_alert=True)
    await call.message.edit_text(VIP_MENU, reply_markup=vip_menu_keyboard())


# ─── Search VIP by name ──────────────────────────────────────────────────────

@router.callback_query(F.data == "vip:search_name")
async def vip_search_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminVIPStates.search_by_name)
    await call.message.edit_text(VIP_SEARCH_BY_NAME, reply_markup=None)
    await call.answer()


@router.message(AdminVIPStates.search_by_name)
async def vip_search_input(
    message: Message, state: FSMContext, db: aiosqlite.Connection
) -> None:
    query = (message.text or "").strip()
    if not query:
        return
    clients = await search_clients_by_name(db, query)
    if not clients:
        await message.answer(VIP_SEARCH_NO_RESULTS, reply_markup=vip_menu_keyboard())
        await state.clear()
        return

    await message.answer(
        f"Знайдено {len(clients)} клієнт(ів). Оберіть для зміни VIP-статусу:",
        reply_markup=vip_search_results_keyboard(clients),
    )
    await state.clear()


@router.callback_query(F.data.startswith("vip:select_client:"))
async def vip_select_client(
    call: CallbackQuery, db: aiosqlite.Connection
) -> None:
    client_id = int(call.data.split(":")[2])
    async with db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        await call.answer("Клієнта не знайдено.", show_alert=True)
        return

    client = dict(row)
    name = f"{client['first_name']} {client.get('last_name') or ''}".strip()
    phone = client.get("phone") or ""

    existing = await get_vip_by_phone(db, phone) if phone else None
    if existing:
        await call.answer(VIP_ALREADY_EXISTS, show_alert=True)
        return

    await add_vip_client(db, phone, client_id=client_id)
    await call.answer(f"{name} додано до VIP!", show_alert=True)
    await call.message.edit_text(VIP_MENU, reply_markup=vip_menu_keyboard())


# ─── VIP Batch Booking ───────────────────────────────────────────────────────

@router.callback_query(F.data == "vip:book")
async def vip_book_start(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    vips = await get_all_vips(db)
    if not vips:
        await call.answer(VIP_LIST_EMPTY, show_alert=True)
        return
    await state.set_state(AdminVIPBookingStates.select_client)
    await call.message.edit_text(
        VIP_SELECT_FOR_BOOKING, reply_markup=vip_select_for_booking_keyboard(vips)
    )
    await call.answer()


@router.callback_query(AdminVIPBookingStates.select_client, F.data.startswith("vip_book:client:"))
async def vip_book_select_client(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    vip_id = int(call.data.split(":")[2])
    vips = await get_all_vips(db)
    vip = next((v for v in vips if v["id"] == vip_id), None)
    if not vip:
        await call.answer("VIP клієнта не знайдено.", show_alert=True)
        return

    services = await get_active_services(db, for_admin=True)
    if not services:
        await call.answer("Послуги відсутні.", show_alert=True)
        return

    await state.update_data(vip_id=vip_id, vip_phone=vip.get("phone"), vip_client_id=vip.get("client_id"))
    await state.set_state(AdminVIPBookingStates.select_service)
    await call.message.edit_text(
        "Оберіть послугу для VIP запису:",
        reply_markup=services_keyboard(services, back_callback="admin:vip"),
    )
    await call.answer()


@router.callback_query(AdminVIPBookingStates.select_service, F.data.startswith("svc:"))
async def vip_book_select_service(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    service_id = int(call.data.split(":")[1])
    service = await get_service(db, service_id)
    if not service:
        await call.answer("Послугу не знайдено.", show_alert=True)
        return
    await state.update_data(service_id=service_id)
    await state.set_state(AdminVIPBookingStates.enter_time)
    await call.message.edit_text(VIP_BOOKING_ENTER_TIME, reply_markup=None)
    await call.answer()


@router.message(AdminVIPBookingStates.enter_time)
async def vip_book_enter_time(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not re.match(r"^\d{1,2}:\d{2}$", text):
        await message.answer(VIP_BOOKING_INVALID_TIME)
        return
    h, m = map(int, text.split(":"))
    if h > 23 or m > 59:
        await message.answer(VIP_BOOKING_INVALID_TIME)
        return

    await state.update_data(booking_time=text, selected_dates=[], vip_year=kyiv_now().year, vip_month=kyiv_now().month)
    await state.set_state(AdminVIPBookingStates.select_dates)

    now = kyiv_now()
    from_date = now.date()
    to_date = from_date + timedelta(days=VIP_BOOKING_DAYS_AHEAD)

    # All dates in range are available for admin
    all_dates = set()
    current = from_date
    while current <= to_date:
        all_dates.add(current)
        current += timedelta(days=1)

    year, month = now.year, now.month
    await state.update_data(
        all_dates=[d.isoformat() for d in all_dates],
        vip_year=year,
        vip_month=month,
    )

    await message.answer(
        VIP_BOOKING_SELECT_DATES,
        reply_markup=dates_multiselect_keyboard(
            all_dates=all_dates,
            selected_dates=set(),
            year=year,
            month=month,
            has_prev=False,
            has_next=True,
        ),
    )


@router.callback_query(AdminVIPBookingStates.select_dates, F.data.startswith("vip_month:"))
async def vip_book_navigate_month(call: CallbackQuery, state: FSMContext) -> None:
    direction = int(call.data.split(":")[1])
    data = await state.get_data()
    year, month = data["vip_year"], data["vip_month"]

    month += direction
    if month > 12:
        month, year = 1, year + 1
    elif month < 1:
        month, year = 12, year - 1

    await state.update_data(vip_year=year, vip_month=month)

    now = kyiv_now()
    all_dates = {date.fromisoformat(s) for s in data["all_dates"]}
    selected_dates = {date.fromisoformat(s) for s in data.get("selected_dates", [])}
    has_prev = (year, month) > (now.year, now.month)

    await call.message.edit_reply_markup(
        reply_markup=dates_multiselect_keyboard(
            all_dates=all_dates,
            selected_dates=selected_dates,
            year=year,
            month=month,
            has_prev=has_prev,
            has_next=True,
        )
    )
    await call.answer()


@router.callback_query(AdminVIPBookingStates.select_dates, F.data.startswith("date_toggle:"))
async def vip_book_toggle_date(call: CallbackQuery, state: FSMContext) -> None:
    date_str = call.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("selected_dates", []))

    if date_str in selected:
        selected.discard(date_str)
    else:
        selected.add(date_str)

    await state.update_data(selected_dates=list(selected))

    now = kyiv_now()
    all_dates = {date.fromisoformat(s) for s in data["all_dates"]}
    selected_dates = {date.fromisoformat(s) for s in selected}
    year, month = data["vip_year"], data["vip_month"]
    has_prev = (year, month) > (now.year, now.month)

    await call.message.edit_reply_markup(
        reply_markup=dates_multiselect_keyboard(
            all_dates=all_dates,
            selected_dates=selected_dates,
            year=year,
            month=month,
            has_prev=has_prev,
            has_next=True,
        )
    )
    await call.answer()


@router.callback_query(AdminVIPBookingStates.select_dates, F.data == "dates_confirm")
async def vip_book_confirm_dates(
    call: CallbackQuery, state: FSMContext, db: aiosqlite.Connection
) -> None:
    data = await state.get_data()
    selected = sorted(data.get("selected_dates", []))
    if not selected:
        await call.answer(VIP_BOOKING_NO_DATES, show_alert=True)
        return

    service = await get_service(db, data["service_id"])
    vip_phone = data.get("vip_phone", "")

    # Find VIP client name
    vips = await get_all_vips(db)
    vip = next((v for v in vips if v["id"] == data["vip_id"]), None)
    first = vip.get("first_name") or "" if vip else ""
    last = vip.get("last_name") or "" if vip else ""
    client_name = f"{first} {last}".strip() or vip_phone

    dates_text = "\n".join(
        f"  • {format_date_uk(date.fromisoformat(d), MONTHS_UK)}" for d in selected
    )
    confirm_text = VIP_BOOKING_CONFIRM.format(
        client=client_name,
        service=service["name"],
        duration=service["duration_minutes"],
        time=data["booking_time"],
        count=len(selected),
        dates=dates_text,
    )
    await state.set_state(AdminVIPBookingStates.confirm)
    await call.message.edit_text(confirm_text, reply_markup=confirm_keyboard(back_callback="confirm:no"))
    await call.answer()


@router.callback_query(AdminVIPBookingStates.confirm, F.data == "confirm:yes")
async def vip_book_execute(
    call: CallbackQuery,
    state: FSMContext,
    db: aiosqlite.Connection,
    calendar: CalendarService,
    reminder_service: ReminderService,
    bot: Bot,
    admin_ids: list[int],
) -> None:
    data = await state.get_data()
    service = await get_service(db, data["service_id"])
    selected = sorted(data.get("selected_dates", []))
    h, m = map(int, data["booking_time"].split(":"))
    slot_time = time(h, m)

    # Resolve client_id
    vip_client_id = data.get("vip_client_id")
    vip_phone = data.get("vip_phone", "")
    vips = await get_all_vips(db)
    vip = next((v for v in vips if v["id"] == data["vip_id"]), None)
    first = vip.get("first_name") or "" if vip else ""
    last = vip.get("last_name") or "" if vip else ""
    client_name = f"{first} {last}".strip() or vip_phone

    if vip_client_id:
        client_id = vip_client_id
    elif vip_phone:
        client_id = await upsert_virtual_client(db, client_name, vip_phone)
    else:
        await call.message.edit_text("Помилка: не знайдено клієнта.", reply_markup=admin_menu_keyboard(await is_bookings_open(db)))
        await state.clear()
        await call.answer()
        return

    created = 0
    for date_str in selected:
        d = date.fromisoformat(date_str)
        booking_id = await create_new_booking(
            db, calendar, client_id, service, d, slot_time,
            skip_availability_check=True,
        )
        if booking_id:
            created += 1
            from bot.models.database import get_booking
            booking = await get_booking(db, booking_id)
            if booking:
                from datetime import datetime as dt
                start_utc = dt.fromisoformat(booking["start_time"])
                reminder_service.schedule_reminders(booking_id, start_utc)

    date_label = format_date_uk(date.fromisoformat(selected[0]), MONTHS_UK) if selected else "—"
    notify_text = ADMIN_MANUAL_BOOKING_NOTIFY.format(
        client=client_name,
        service=service["name"],
        date=f"{len(selected)} дат (перша: {date_label})",
        time=data["booking_time"],
        phone=vip_phone or "—",
    )
    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=notify_text)
        except Exception:
            pass

    await call.message.edit_text(
        VIP_BOOKING_CREATED.format(created=created, total=len(selected)),
        reply_markup=admin_menu_keyboard(await is_bookings_open(db)),
    )
    await state.clear()
    await call.answer()


@router.callback_query(AdminVIPBookingStates.confirm, F.data == "confirm:no")
async def vip_book_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(VIP_MENU, reply_markup=vip_menu_keyboard())
    await call.answer()


@router.callback_query(AdminVIPBookingStates.select_dates, F.data == "vip_book:back_time")
async def vip_book_back_to_time(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminVIPBookingStates.enter_time)
    await call.message.edit_text(VIP_BOOKING_ENTER_TIME, reply_markup=None)
    await call.answer()
