import calendar as cal_module
import re
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")
UTC_TZ = ZoneInfo("UTC")


def kyiv_now() -> datetime:
    return datetime.now(KYIV_TZ)


def utc_to_kyiv(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(KYIV_TZ)


def kyiv_to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV_TZ)
    return dt.astimezone(UTC_TZ)


def make_kyiv_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=KYIV_TZ)


def generate_time_slots(
    d: date,
    work_start: int,
    work_end: int,
    interval_minutes: int,
    service_duration: int,
    break_minutes: int,
) -> list[time]:
    slots = []
    current = datetime.combine(d, time(work_start, 0), tzinfo=KYIV_TZ)
    end_boundary = datetime.combine(d, time(work_end, 0), tzinfo=KYIV_TZ)
    slot_total = timedelta(minutes=service_duration + break_minutes)

    while current + slot_total <= end_boundary:
        slots.append(current.time())
        current += timedelta(minutes=interval_minutes)

    return slots


def format_date_uk(d: date, months: dict) -> str:
    from bot.utils.texts import WEEKDAYS_UK
    return f"{d.day} {months[d.month]} {d.year}, {WEEKDAYS_UK[d.weekday()]}"


def format_time(t: time) -> str:
    return t.strftime("%H:%M")


def normalize_phone(phone: str) -> str:
    """Normalize Ukrainian phone to +380XXXXXXXXX format."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("380") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 10:
        return "+38" + digits
    return phone  # unknown format — leave as-is


def parse_date(s: str) -> Optional[date]:
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None
