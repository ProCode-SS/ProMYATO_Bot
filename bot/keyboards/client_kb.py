import calendar as cal_module
from datetime import date

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.texts import MONTHS_NOMINATIVE_UK, NO_KEEP, WEEKDAY_HEADERS, YES_CANCEL


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поділитись номером телефону", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Записатись", callback_data="menu:book")
    kb.button(text="📋 Мої записи", callback_data="menu:mybookings")
    kb.adjust(2)
    return kb.as_markup()


def services_keyboard(
    services: list[dict], back_callback: str = "menu:back"
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for svc in services:
        price_str = f" — {svc['price']}₴" if svc.get("price") else ""
        kb.button(
            text=f"{svc['name']} {svc['duration_minutes']}хв{price_str}",
            callback_data=f"svc:{svc['id']}",
        )
    kb.button(text="← Назад", callback_data=back_callback)
    kb.adjust(1)
    return kb.as_markup()


def dates_keyboard(
    available_dates: set,
    year: int,
    month: int,
    has_prev: bool = False,
) -> InlineKeyboardMarkup:
    rows = []

    # Navigation row
    prev_data = "month:-1" if has_prev else "noop"
    month_label = f"{MONTHS_NOMINATIVE_UK[month]} {year}"
    rows.append([
        InlineKeyboardButton(text="◀" if has_prev else " ", callback_data=prev_data),
        InlineKeyboardButton(text=month_label, callback_data="noop"),
        InlineKeyboardButton(text="▶", callback_data="month:+1"),
    ])

    # Weekday headers
    rows.append([
        InlineKeyboardButton(text=h, callback_data="noop") for h in WEEKDAY_HEADERS
    ])

    # Day grid
    for week in cal_module.Calendar(firstweekday=0).monthdatescalendar(year, month):
        row = []
        for d in week:
            if d.month != month:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            elif d in available_dates:
                row.append(
                    InlineKeyboardButton(text=str(d.day), callback_data=f"date:{d.isoformat()}")
                )
            else:
                row.append(InlineKeyboardButton(text="·", callback_data="noop"))
        rows.append(row)

    rows.append([InlineKeyboardButton(text="Назад", callback_data="booking:back_to_service")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def times_keyboard(slots: list, selected_date_str: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for slot in slots:
        time_str = slot.strftime("%H:%M")
        kb.button(text=time_str, callback_data=f"time:{time_str}")
    kb.adjust(4)
    kb.button(text="Назад до дат", callback_data="booking:back_to_dates")
    kb.adjust(4, 1)
    return kb.as_markup()


def confirm_keyboard(back_callback: str = "booking:back_to_time") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити", callback_data="confirm:yes")
    kb.button(text="❌ Скасувати", callback_data="confirm:no")
    kb.button(text="← Назад", callback_data=back_callback)
    kb.adjust(2, 1)
    return kb.as_markup()


def my_bookings_keyboard(bookings: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(text="📅 В календар", callback_data=f"ics:{b['id']}")
        kb.button(text="❌ Скасувати", callback_data=f"cancel:{b['id']}")
    kb.button(text="Назад", callback_data="menu:back")
    kb.adjust(*([2] * len(bookings)), 1)
    return kb.as_markup()


def cancel_confirm_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=YES_CANCEL, callback_data=f"cancel_yes:{booking_id}")
    kb.button(text=NO_KEEP, callback_data="cancel_no")
    kb.adjust(2)
    return kb.as_markup()
