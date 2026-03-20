# All user-facing strings in Ukrainian

# --- Main menu ---
WELCOME = (
    "Ласкаво просимо!\n\n"
    "Натисніть кнопку нижче, щоб поділитися номером телефону для запису."
)
MAIN_MENU = "Головне меню:"
ALREADY_REGISTERED = "З поверненням, {name}! Що бажаєте?"

# --- Booking flow ---
SELECT_SERVICE = "Оберіть послугу:"
SELECT_DATE = "Оберіть зручну дату:"
NO_DATES_AVAILABLE = (
    "На жаль, вільних дат на найближчі 60 днів немає.\n"
    "Зверніться до адміністратора."
)
SELECT_TIME = "Оберіть зручний час на {date}:"
NO_SLOTS_AVAILABLE = "На жаль, на цей день немає вільних слотів. Оберіть іншу дату."
BOOKING_CONFIRM = (
    "Підтвердження запису:\n\n"
    "{service} ({duration} хв)\n"
    "{date}\n"
    "{time_start} - {time_end}\n"
    "{price}\n\n"
    "Все вірно?"
)
BOOKING_CONFIRMED = (
    "Запис підтверджено!\n\n"
    "{service}\n"
    "{date}, {time_start}\n\n"
    "Надсилаємо файл для вашого календаря..."
)
SLOT_TAKEN = "На жаль, цей час вже зайнятий. Оберіть інший час."
ICS_FILENAME = "massage_{date}_{time}.ics"

# --- My bookings ---
MY_BOOKINGS_EMPTY = "У вас немає майбутніх записів."
MY_BOOKINGS_HEADER = "Ваші майбутні записи:"
CANCEL_CONFIRM_Q = "Ви впевнені, що хочете скасувати запис на {date} {time}?"
BOOKING_CANCELLED = "Запис скасовано."
YES_CANCEL = "Так, скасувати"
NO_KEEP = "Ні, залишити"

# --- Admin ---
ADMIN_MENU = "Адмін-панель:"
NOT_ADMIN = "У вас немає доступу до цієї команди."
NO_BOOKINGS_TODAY = "Сьогодні записів немає."
NO_BOOKINGS_WEEK = "На цьому тижні записів немає."

# --- Admin: services ---
SERVICES_LIST = "Послуги:"
SERVICE_ADD_NAME = "Введіть назву послуги:"
SERVICE_ADD_DURATION = "Введіть тривалість у хвилинах (наприклад 60):"
SERVICE_ADD_PRICE = "Введіть ціну в гривнях (або 0 якщо безкоштовно):"
SERVICE_ADD_DESC = 'Введіть опис послуги (або "-" щоб пропустити):'
SERVICE_ADDED = "Послугу додано!"
SERVICE_TOGGLED = "Статус послуги змінено."
NO_SERVICES = "Послуг ще немає. Додайте першу послугу."

# --- Admin: schedule ---
SCHEDULE_INFO = (
    "Поточний графік:\n\n"
    "Години роботи: {start}:00 - {end}:00\n"
    "Робочі дні: {days}\n"
    "Інтервал слотів: {interval} хв\n"
    "Перерва між записами: {break_} хв"
)
SCHEDULE_EDIT_START = "Введіть час початку роботи (число від 0 до 23):"
SCHEDULE_EDIT_END = "Введіть час кінця роботи (число від 0 до 23):"
SCHEDULE_EDIT_INTERVAL = (
    "Інтервал слотів — кожні скільки хвилин може починатись запис.\n"
    "Наприклад, 30 = записи о 9:00, 9:30, 10:00...\n\n"
    "Введіть значення в хвилинах (наприклад 30):"
)
SCHEDULE_EDIT_BREAK = (
    "Перерва між записами — буфер після закінчення масажу.\n"
    "Наприклад, 15 = після 60хв масажу наступний клієнт не раніше ніж через 75 хв від початку.\n\n"
    "Введіть значення в хвилинах (0, 15, 30...):"
)
SCHEDULE_SAVED = "Графік збережено."
# --- Admin: manual booking ---
ADMIN_BOOKING_SELECT_SERVICE = "Оберіть послугу для запису:"
ADMIN_BOOKING_ENTER_DATE = "Введіть дату запису (DD.MM.YYYY):"
ADMIN_BOOKING_ENTER_NAME = "Введіть ім'я клієнта:"
ADMIN_BOOKING_ENTER_PHONE = "Введіть номер телефону клієнта:"
ADMIN_BOOKING_CONFIRM = (
    "Підтвердження нового запису:\n\n"
    "Клієнт: {name}\n"
    "Тел: {phone}\n"
    "Послуга: {service} ({duration} хв)\n"
    "Дата: {date}\n"
    "Час: {time_start} - {time_end}\n\n"
    "Підтвердити?"
)
ADMIN_BOOKING_CREATED = "Запис створено!"
ADMIN_BOOKING_NO_SLOTS = "На цей день немає вільних слотів. Введіть іншу дату:"

DAYS_OFF_HEADER = "Вихідні дні:"
NO_DAYS_OFF = "Вихідних днів не заплановано."
DAY_OFF_ADD = "Введіть дату вихідного у форматі DD.MM.YYYY:"
DAY_OFF_REASON = 'Введіть причину (або "-" щоб пропустити):'
DAY_OFF_ADDED = "Вихідний день додано."
DAY_OFF_REMOVED = "Вихідний день видалено."

# --- Reminders ---
REMINDER_24H = (
    "Нагадування! Ваш запис на масаж завтра:\n\n"
    "{service}\n"
    "{date}, {time}\n\n"
    "До зустрічі!"
)
REMINDER_2H = (
    "Нагадування! Ваш запис на масаж через 2 години:\n\n"
    "{service}\n"
    "{date}, {time}\n\n"
    "До зустрічі!"
)

# --- Admin notifications ---
NEW_BOOKING_ADMIN = (
    "Новий запис!\n\n"
    "{client} — {service}\n"
    "{date}, {time}\n"
    "Тел: {phone}"
)
URGENT_BOOKING_ADMIN = (
    "ТЕРМІНОВО! Запис менш ніж за 30 хвилин!\n\n"
    "{client} — {service}\n"
    "{date}, {time}\n"
    "Тел: {phone}"
)
ADMIN_MANUAL_BOOKING_NOTIFY = (
    "Запис додано вручну:\n\n"
    "{client} — {service}\n"
    "{date}, {time}\n"
    "Тел: {phone}"
)
CANCEL_BOOKING_ADMIN = (
    "Скасування!\n\n"
    "{client} скасував(ла) запис:\n"
    "{service}\n"
    "{date}, {time}"
)

# --- Errors ---
ERROR_GOOGLE_CALENDAR = (
    "Помилка з'єднання з календарем. Спробуйте пізніше або "
    "зверніться до адміністратора."
)
ERROR_GENERAL = "Щось пішло не так. Спробуйте ще раз."

# --- Ukrainian locale ---
MONTHS_UK = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня",
}
MONTHS_NOMINATIVE_UK = {
    1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень",
    5: "Травень", 6: "Червень", 7: "Липень", 8: "Серпень",
    9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень",
}
WEEKDAYS_UK = {
    0: "понеділок", 1: "вівторок", 2: "середа",
    3: "четвер", 4: "п'ятниця", 5: "субота", 6: "неділя",
}
WEEKDAY_HEADERS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
