# All user-facing strings in Ukrainian

# --- Main menu ---
WELCOME = "Ласкаво просимо!\n\nДля запису потрібно пройти коротку реєстрацію."
REGISTER_ENTER_FIRST_NAME = "Як вас звати? Введіть ваше ім'я:"
REGISTER_ENTER_LAST_NAME = "Введіть ваше прізвище:"
REGISTER_SHARE_PHONE = (
    "Залишилось тільки поділитись номером телефону.\n"
    "Натисніть кнопку нижче:"
)
MAIN_MENU = "Головне меню:"
ALREADY_REGISTERED = "З поверненням, {name}! Що бажаєте?"
MENU_BUTTON = "🏠 Меню"
ADMIN_BUTTON = "⚙️ Адмін"

# --- Booking flow ---
SELECT_SERVICE = "Оберіть послугу:"
SELECT_DATE = "Оберіть зручну дату:"
NO_DATES_AVAILABLE = (
    "На жаль, вільних дат на найближчі 2 місяці немає.\n"
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

# --- 24h confirmation ---
REMINDER_24H = (
    "Нагадування! Ваш запис на масаж завтра:\n\n"
    "{service}\n"
    "{date}, {time}\n\n"
    "Будь ласка, підтвердіть, що плануєте прийти.\n"
    "Якщо не підтвердите протягом 12 годин — запис буде автоматично скасовано."
)
REMINDER_CONFIRM_BUTTON = "✅ Підтверджую"
REMINDER_CONFIRMED = "Чудово! Ваш запис підтверджено. До зустрічі!"
REMINDER_CONFIRM_ADMIN = (
    "Клієнт підтвердив запис:\n\n"
    "{client} — {service}\n"
    "{date}, {time}"
)
AUTO_CANCELLED_CLIENT = (
    "Ваш запис на {service} ({date}, {time}) було автоматично скасовано, "
    "оскільки ви не підтвердили його протягом 12 годин.\n\n"
    "Щоб записатись знову — натисніть '🏠 Меню'."
)
AUTO_CANCELLED_ADMIN = (
    "Автоскасування!\n\n"
    "{client} не підтвердив(ла) запис:\n"
    "{service}\n"
    "{date}, {time}"
)

# --- Reminders ---
REMINDER_2H = (
    "Нагадування! Ваш запис на масаж через 2 години:\n\n"
    "{service}\n"
    "{date}, {time}\n\n"
    "До зустрічі!"
)

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

# --- Admin: VIP clients ---
VIP_MENU = "👑 VIP клієнти:"
VIP_LIST_EMPTY = "VIP клієнтів ще немає."
VIP_LIST_HEADER = "👑 VIP клієнти:\n"
VIP_ADD_BY_PHONE = "Введіть номер телефону VIP клієнта (наприклад +380XXXXXXXXX):"
VIP_SEARCH_BY_NAME = "Введіть ім'я або прізвище для пошуку:"
VIP_SEARCH_NO_RESULTS = "Клієнтів не знайдено. Спробуйте інший запит."
VIP_ALREADY_EXISTS = "Цей клієнт вже є у списку VIP."
VIP_ADDED = "Клієнта додано до VIP!"
VIP_REMOVED = "Клієнта видалено з VIP."
VIP_NOT_REGISTERED = (
    "Клієнта з таким номером не знайдено серед зареєстрованих.\n"
    "Додати номер {phone} до VIP-списку (клієнт підключиться при реєстрації)?"
)
VIP_SELECT_FOR_BOOKING = "Оберіть VIP клієнта для запису:"
VIP_BOOKING_ENTER_TIME = (
    "Введіть час для запису у форматі HH:MM\n"
    "Наприклад: 17:00"
)
VIP_BOOKING_INVALID_TIME = "Невірний формат. Введіть час як HH:MM, наприклад 17:00:"
VIP_BOOKING_SELECT_DATES = (
    "Оберіть дати для запису (можна обрати кілька).\n"
    "Натисніть на дату, щоб додати або прибрати її.\n"
    "Коли завершите — натисніть «Підтвердити»."
)
VIP_BOOKING_NO_DATES = "Не обрано жодної дати."
VIP_BOOKING_CONFIRM = (
    "Підтвердження пакетного запису:\n\n"
    "Клієнт: {client}\n"
    "Послуга: {service} ({duration} хв)\n"
    "Час: {time}\n"
    "Дати ({count}):\n{dates}\n\n"
    "Підтвердити?"
)
VIP_BOOKING_CREATED = "Створено {created} з {total} записів."

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

# --- Group cancellation notifications ---
GROUP_SLOT_AVAILABLE = (
    "🔔 Вільне місце!\n\n"
    "💆 {service}\n"
    "📅 {date}\n"
    "🕐 {time_start} — {time_end}\n"
    "{price_line}"
)
GROUP_SLOT_AVAILABLE_URGENT = (
    "🚨 ТЕРМІНОВО! Вільне місце!\n\n"
    "💆 {service}\n"
    "📅 {date}\n"
    "🕐 {time_start} — {time_end}\n"
    "{price_line}"
)
GROUP_SLOT_BOOKED = "✅ Місце вже заброньовано."
GROUP_SLOT_EXPIRED = "Цей слот більше не актуальний."
GROUP_BOOK_BUTTON = "📅 Записатись"
GROUP_BOOKING_SUCCESS = (
    "Вас записано!\n\n"
    "💆 {service}\n"
    "📅 {date}, {time_start}\n\n"
    "Файл для календаря надіслано у ваш чат з ботом."
)
GROUP_BOOKING_NOT_REGISTERED = (
    "Щоб записатись, вам потрібно пройти реєстрацію в боті.\n"
    "Після реєстрації ваш запис буде збережено автоматично.\n\n"
    "Натисніть кнопку нижче:"
)
GROUP_BOOKING_ALREADY_TAKEN = "На жаль, це місце вже зайняте."
GROUP_BOOKING_OPEN_BOT = "Відкрити бота"
GROUP_BOOKING_PENDING_COMPLETE = (
    "Реєстрацію завершено! Записуємо вас на:\n\n"
    "💆 {service}\n"
    "📅 {date}, {time_start}\n\n"
    "Файл для календаря надіслано."
)
GROUP_BOOKING_PENDING_TAKEN = (
    "На жаль, поки ви проходили реєстрацію, місце вже зайняли. "
    "Ви можете записатись на інший час через меню."
)

# --- Bookings open/closed toggle ---
BOOKINGS_CLOSED = (
    "Запис тимчасово недоступний. Спробуйте пізніше або зверніться до майстра."
)
BOOKINGS_TOGGLE_CLOSED = "🔒 Запис закрито для клієнтів."
BOOKINGS_TOGGLE_OPENED = "✅ Запис знову відкрито для клієнтів."

# --- Off-hours (позаробочий) booking flow ---
OFFHOURS_BOOKING_CONFIRM = (
    "Підтвердження запиту:\n\n"
    "{service} ({duration} хв)\n"
    "{date}\n"
    "{time_start} — {time_end}\n"
    "{price}\n\n"
    "⚠️ Запис поза робочими годинами — набуде чинності лише після підтвердження майстром.\n\n"
    "Відправити запит?"
)
OFFHOURS_PENDING_SENT = (
    "Ваш запит надіслано! Майстер розгляне та підтвердить або відхилить його. "
    "Ви отримаєте повідомлення після рішення."
)
OFFHOURS_REQUEST_ADMIN = (
    "🕐 Запит на позаробочий час!\n\n"
    "{client} — {service}\n"
    "{date}, {time}\n"
    "Тел: {phone}\n\n"
    "Підтвердити чи відхилити?"
)
OFFHOURS_APPROVED_CLIENT = (
    "✅ Ваш запит підтверджено!\n\n"
    "💆 {service}\n"
    "📅 {date}, {time_start}\n\n"
    "Файл для календаря надіслано."
)
OFFHOURS_REJECTED_CLIENT = (
    "На жаль, майстер не може прийняти вас в цей час.\n\n"
    "💆 {service}\n"
    "📅 {date}, {time}\n\n"
    "Зверніться для уточнення іншого часу."
)
OFFHOURS_REQUEST_CANCELLED = "Запит скасовано."
OFFHOURS_REQUEST_CANCELLED_ADMIN = (
    "❌ Клієнт скасував запит на позаробочий час:\n\n"
    "{client} — {service}\n"
    "{date}, {time}"
)
OFFHOURS_APPROVED_ADMIN = "Запис підтверджено."
OFFHOURS_REJECTED_ADMIN = "Запис відхилено."
NO_PENDING_APPROVALS = "Немає запитів, що очікують підтвердження."

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
