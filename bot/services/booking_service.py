import logging
from datetime import date, datetime, time, timedelta
from typing import Optional

import aiosqlite

from bot.models.database import (
    cancel_booking,
    create_booking,
    get_booking,
    get_days_off,
    get_setting,
    is_day_off,
)
from bot.services.calendar_service import CalendarService
from bot.utils.datetime_helpers import (
    KYIV_TZ,
    generate_time_slots,
    kyiv_now,
    kyiv_to_utc,
    make_kyiv_dt,
)

logger = logging.getLogger(__name__)


def get_admin_only_slots(d: date, interval_minutes: int, service_duration: int) -> list[time]:
    """All start times for a full 24h day — used for admin-only services."""
    slots = []
    current = datetime.combine(d, time(0, 0))
    end = current + timedelta(days=1)
    step = timedelta(minutes=interval_minutes)
    duration = timedelta(minutes=service_duration)
    while current + duration <= end:
        slots.append(current.time())
        current += step
    return slots


def get_admin_only_dates(from_date: date, to_date: date) -> set[date]:
    """All dates in range — used for admin-only services."""
    result: set[date] = set()
    current = from_date
    while current <= to_date:
        result.add(current)
        current += timedelta(days=1)
    return result


async def _load_schedule(db: aiosqlite.Connection) -> dict:
    return {
        "work_start": int(await get_setting(db, "work_start_hour") or "9"),
        "work_end": int(await get_setting(db, "work_end_hour") or "20"),
        "interval": int(await get_setting(db, "slot_interval_minutes") or "30"),
        "break_mins": int(await get_setting(db, "break_between_minutes") or "15"),
        "work_days": [
            int(x)
            for x in (await get_setting(db, "work_days") or "0,1,2,3,4,5").split(",")
        ],
    }


async def get_available_slots(
    db: aiosqlite.Connection,
    calendar: CalendarService,
    d: date,
    service_duration: int,
) -> list[time]:
    """Return available time slots for a given date."""
    if await is_day_off(db, d.isoformat()):
        return []

    sched = await _load_schedule(db)
    if d.weekday() not in sched["work_days"]:
        return []

    candidates = generate_time_slots(
        d,
        sched["work_start"],
        sched["work_end"],
        sched["interval"],
        service_duration,
        sched["break_mins"],
    )

    # Filter out slots less than 15 minutes away
    now = kyiv_now()
    if d == now.date():
        candidates = [
            t for t in candidates
            if make_kyiv_dt(d, t) > now + timedelta(minutes=15)
        ]

    if not candidates:
        return []

    try:
        busy = await calendar.get_busy_slots(d, d)
    except Exception:
        # Calendar unavailable — treat as no existing bookings (log warning, show slots)
        logger.warning("Calendar unavailable for %s, showing slots without conflict check", d)
        busy = []

    break_td = timedelta(minutes=sched["break_mins"])
    available = []
    for slot_time in candidates:
        slot_start = make_kyiv_dt(d, slot_time)
        slot_end = slot_start + timedelta(minutes=service_duration + sched["break_mins"])
        slot_start_utc = kyiv_to_utc(slot_start)
        slot_end_utc = kyiv_to_utc(slot_end)
        if not any(slot_start_utc < be + break_td and slot_end_utc > bs for bs, be in busy):
            available.append(slot_time)

    return available


async def get_available_dates(
    db: aiosqlite.Connection,
    calendar: CalendarService,
    from_date: date,
    to_date: date,
    service_duration: int,
) -> set[date]:
    """
    Return all dates with at least one free slot in the range.
    Uses a single Google Calendar API call for the whole period.
    """
    sched = await _load_schedule(db)
    days_off_rows = await get_days_off(db)
    days_off = {row["date"] for row in days_off_rows}

    try:
        busy = await calendar.get_busy_slots(from_date, to_date)
    except Exception:
        logger.warning("Calendar unavailable, showing dates without conflict check")
        busy = []

    break_td = timedelta(minutes=sched["break_mins"])
    available_dates: set[date] = set()
    current = from_date
    while current <= to_date:
        if current.weekday() in sched["work_days"] and current.isoformat() not in days_off:
            candidates = generate_time_slots(
                current,
                sched["work_start"],
                sched["work_end"],
                sched["interval"],
                service_duration,
                sched["break_mins"],
            )
            for slot_time in candidates:
                slot_start = make_kyiv_dt(current, slot_time)
                slot_end = slot_start + timedelta(minutes=service_duration + sched["break_mins"])
                slot_start_utc = kyiv_to_utc(slot_start)
                slot_end_utc = kyiv_to_utc(slot_end)
                if not any(
                    slot_start_utc < be + break_td and slot_end_utc > bs for bs, be in busy
                ):
                    available_dates.add(current)
                    break
        current += timedelta(days=1)

    return available_dates


async def create_new_booking(
    db: aiosqlite.Connection,
    calendar: CalendarService,
    client_id: int,
    service: dict,
    d: date,
    slot_time: time,
    skip_availability_check: bool = False,
) -> Optional[int]:
    """
    Double-check availability, create Google Calendar event, save to DB.
    Returns booking_id or None if the slot was taken.
    Pass skip_availability_check=True for admin-only services (any day/time allowed).
    """
    if not skip_availability_check:
        available = await get_available_slots(db, calendar, d, service["duration_minutes"])
        if slot_time not in available:
            return None

    start_dt = make_kyiv_dt(d, slot_time)
    end_dt = start_dt + timedelta(minutes=service["duration_minutes"])

    try:
        event_id = await calendar.create_event(
            summary=f"Масаж: {service['name']}",
            start=start_dt,
            end=end_dt,
        )
    except Exception as e:
        logger.error("Failed to create calendar event: %s", e)
        return None

    booking_id = await create_booking(
        db,
        client_id=client_id,
        service_id=service["id"],
        start_time=kyiv_to_utc(start_dt).isoformat(),
        end_time=kyiv_to_utc(end_dt).isoformat(),
        google_event_id=event_id,
    )
    return booking_id


async def cancel_existing_booking(
    db: aiosqlite.Connection,
    calendar: CalendarService,
    booking_id: int,
    client_id: Optional[int] = None,
) -> bool:
    """
    Cancel booking: update DB, delete Google Calendar event.
    If client_id is given, verifies ownership. Returns True on success.
    """
    booking = await get_booking(db, booking_id)
    if not booking or booking["status"] != "confirmed":
        return False
    if client_id is not None and booking["client_id"] != client_id:
        return False

    google_event_id = await cancel_booking(db, booking_id)
    if google_event_id:
        await calendar.delete_event(google_event_id)
    return True
