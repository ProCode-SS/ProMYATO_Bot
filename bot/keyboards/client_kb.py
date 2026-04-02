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

from bot.utils.texts import (
    ADMIN_BUTTON,
    MENU_BUTTON,
    MONTHS_NOMINATIVE_UK,
    NO_KEEP,
    REMINDER_CONFIRM_BUTTON,
    WEEKDAY_HEADERS,
    YES_CANCEL,
)


def main_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard always visible to the user."""
    row = [KeyboardButton(text=MENU_BUTTON)]
    if is_admin:
        row.append(KeyboardButton(text=ADMIN_BUTTON))
    return ReplyKeyboardMarkup(
        keyboard=[row],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


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


def dates_multiselect_keyboard(
    all_dates: set,
    selected_dates: set,
    year: int,
    month: int,
    has_prev: bool = False,
    has_next: bool = True,
    back_callback: str = "vip_book:back_time",
) -> InlineKeyboardMarkup:
    """Calendar with multi-select support for VIP batch booking."""
    rows = []

    prev_data = "vip_month:-1" if has_prev else "noop"
    next_data = "vip_month:+1" if has_next else "noop"
    month_label = f"{MONTHS_NOMINATIVE_UK[month]} {year}"
    rows.append([
        InlineKeyboardButton(text="◀" if has_prev else " ", callback_data=prev_data),
        InlineKeyboardButton(text=month_label, callback_data="noop"),
        InlineKeyboardButton(text="▶" if has_next else " ", callback_data=next_data),
    ])

    rows.append([
        InlineKeyboardButton(text=h, callback_data="noop") for h in WEEKDAY_HEADERS
    ])

    for week in cal_module.Calendar(firstweekday=0).monthdatescalendar(year, month):
        row = []
        for d in week:
            if d.month != month:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            elif d in all_dates:
                if d in selected_dates:
                    row.append(InlineKeyboardButton(
                        text=f"✅{d.day}",
                        callback_data=f"date_toggle:{d.isoformat()}",
                    ))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(d.day),
                        callback_data=f"date_toggle:{d.isoformat()}",
                    ))
            else:
                row.append(InlineKeyboardButton(text="·", callback_data="noop"))
        rows.append(row)

    n = len(selected_dates)
    confirm_text = f"✅ Підтвердити ({n})" if n > 0 else "Підтвердити"
    confirm_data = "dates_confirm" if n > 0 else "noop"
    rows.append([
        InlineKeyboardButton(text=back_callback and "← Назад" or "← Назад", callback_data=back_callback),
        InlineKeyboardButton(text=confirm_text, callback_data=confirm_data),
    ])
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


def reminder_confirm_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=REMINDER_CONFIRM_BUTTON, callback_data=f"confirm_reminder:{booking_id}")
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


def group_book_keyboard(slot_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Записатись", callback_data=f"book_slot:{slot_id}")
    return kb.as_markup()


def open_bot_keyboard(bot_username: str, slot_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Відкрити бота",
        url=f"https://t.me/{bot_username}?start=claim_{slot_id}",
    )
    return kb.as_markup()
