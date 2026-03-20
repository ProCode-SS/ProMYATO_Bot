from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Записи на сьогодні", callback_data="admin:today")
    kb.button(text="📅 Записи на тиждень", callback_data="admin:week")
    kb.button(text="➕ Новий запис", callback_data="admin:new_booking")
    kb.button(text="🛠 Послуги", callback_data="admin:services")
    kb.button(text="⏰ Графік роботи", callback_data="admin:schedule")
    kb.button(text="🚫 Вихідні дні", callback_data="admin:days_off")
    kb.adjust(1)
    return kb.as_markup()


def services_list_keyboard(services: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for svc in services:
        status = "✅" if svc["is_active"] else "❌"
        price_str = f" — {svc['price']}₴" if svc.get("price") else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {svc['name']} {svc['duration_minutes']}хв{price_str}",
                callback_data="noop",
            ),
            InlineKeyboardButton(
                text="Вкл/Викл",
                callback_data=f"admin:toggle_svc:{svc['id']}",
            ),
        ])
    rows.append([InlineKeyboardButton(text="Додати послугу", callback_data="admin:add_service")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Змінити години роботи", callback_data="admin:edit_hours")
    kb.button(text="Змінити робочі дні", callback_data="admin:edit_workdays")
    kb.button(text="Змінити інтервал слотів", callback_data="admin:edit_interval")
    kb.button(text="Змінити перерву між записами", callback_data="admin:edit_break")
    kb.button(text="Назад", callback_data="admin:menu")
    kb.adjust(1)
    return kb.as_markup()


def days_off_keyboard(days_off: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for d in days_off:
        reason_str = f" — {d['reason']}" if d.get("reason") else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{d['date']}{reason_str}", callback_data="noop"
            ),
            InlineKeyboardButton(
                text="Видалити", callback_data=f"admin:del_dayoff:{d['id']}"
            ),
        ])
    rows.append([InlineKeyboardButton(text="Додати вихідний", callback_data="admin:add_dayoff")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def workdays_keyboard(current_days: list[int]) -> InlineKeyboardMarkup:
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    row = []
    for i, name in enumerate(day_names):
        mark = "✅" if i in current_days else "⬜"
        row.append(
            InlineKeyboardButton(
                text=f"{mark} {name}", callback_data=f"admin:toggle_day:{i}"
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [
            InlineKeyboardButton(text="Зберегти", callback_data="admin:save_workdays"),
            InlineKeyboardButton(text="Назад", callback_data="admin:schedule"),
        ],
    ])
