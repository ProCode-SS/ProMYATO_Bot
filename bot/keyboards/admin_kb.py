from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu_keyboard(bookings_open: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Записи на сьогодні", callback_data="admin:today")
    kb.button(text="📅 Записи на тиждень", callback_data="admin:week")
    kb.button(text="⏳ Запити на схвалення", callback_data="admin:pending")
    kb.button(text="➕ Новий запис", callback_data="admin:new_booking")
    kb.button(text="👑 VIP клієнти", callback_data="admin:vip")
    kb.button(text="🛠 Послуги", callback_data="admin:services")
    kb.button(text="⏰ Графік роботи", callback_data="admin:schedule")
    kb.button(text="🚫 Вихідні дні", callback_data="admin:days_off")
    toggle_text = "🔒 Закрити запис для клієнтів" if bookings_open else "🔓 Відкрити запис для клієнтів"
    kb.button(text=toggle_text, callback_data="admin:toggle_bookings")
    kb.adjust(1)
    return kb.as_markup()


def services_list_keyboard(services: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for svc in services:
        status = "✅" if svc["is_active"] else "❌"
        price_str = f" — {svc['price']}₴" if svc.get("price") else ""
        approval_mark = " 🕐" if svc.get("requires_approval") else ""
        label = f"{status} {svc['name']} {svc['duration_minutes']}хв{price_str}{approval_mark}"
        rows.append([InlineKeyboardButton(text=label, callback_data="noop")])
        rows.append([
            InlineKeyboardButton(text="Вкл/Викл", callback_data=f"admin:toggle_svc:{svc['id']}"),
            InlineKeyboardButton(text="🗑 Видалити", callback_data=f"admin:del_svc:{svc['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ Додати послугу", callback_data="admin:add_service")])
    rows.append([InlineKeyboardButton(text="← Назад", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_delete_confirm_keyboard(service_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, видалити", callback_data=f"admin:confirm_del_svc:{service_id}")
    kb.button(text="← Назад", callback_data="admin:services")
    kb.adjust(1)
    return kb.as_markup()


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


# --- VIP keyboards ---

def vip_menu_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Додати VIP (по телефону)", callback_data="vip:add_phone")
    kb.button(text="🔍 Знайти клієнта по імені", callback_data="vip:search_name")
    kb.button(text="📋 Список VIP", callback_data="vip:list")
    kb.button(text="📅 Записати VIP", callback_data="vip:book")
    kb.button(text="← Назад", callback_data="admin:menu")
    kb.adjust(1)
    return kb.as_markup()


def vip_list_keyboard(vips: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for v in vips:
        first = v.get("first_name") or ""
        last = v.get("last_name") or ""
        name = f"{first} {last}".strip() or "—"
        phone = v.get("phone") or "—"
        rows.append([
            InlineKeyboardButton(
                text=f"👑 {name} ({phone})", callback_data="noop"
            ),
            InlineKeyboardButton(
                text="✖ Видалити", callback_data=f"vip:remove:{v['id']}"
            ),
        ])
    rows.append([InlineKeyboardButton(text="← Назад", callback_data="admin:vip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vip_search_results_keyboard(clients: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in clients:
        name = f"{c['first_name']} {c.get('last_name') or ''}".strip()
        vip_mark = " 👑" if c.get("vip_id") else ""
        phone = c.get("phone") or "—"
        kb.button(
            text=f"{name} ({phone}){vip_mark}",
            callback_data=f"vip:select_client:{c['id']}",
        )
    kb.button(text="← Назад", callback_data="admin:vip")
    kb.adjust(1)
    return kb.as_markup()


def vip_confirm_add_keyboard(client_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Додати як VIP", callback_data=f"vip:confirm_add:{client_id}")
    kb.button(text="← Скасувати", callback_data="admin:vip")
    kb.adjust(1)
    return kb.as_markup()


def vip_confirm_phone_keyboard(phone: str) -> InlineKeyboardMarkup:
    """For adding VIP by phone when client not yet registered."""
    import urllib.parse
    encoded = urllib.parse.quote(phone)
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, додати", callback_data=f"vip:confirm_phone:{encoded}")
    kb.button(text="← Скасувати", callback_data="admin:vip")
    kb.adjust(1)
    return kb.as_markup()


def offhours_approve_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Підтвердити", callback_data=f"offhours:approve:{booking_id}")
    kb.button(text="❌ Відхилити", callback_data=f"offhours:reject:{booking_id}")
    kb.adjust(2)
    return kb.as_markup()


def vip_select_for_booking_keyboard(vips: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for v in vips:
        first = v.get("first_name") or ""
        last = v.get("last_name") or ""
        name = f"{first} {last}".strip() or v.get("phone") or "—"
        phone = v.get("phone") or "—"
        kb.button(
            text=f"👑 {name} ({phone})",
            callback_data=f"vip_book:client:{v['id']}",
        )
    kb.button(text="← Назад", callback_data="admin:vip")
    kb.adjust(1)
    return kb.as_markup()
