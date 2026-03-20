from pathlib import Path
from typing import Optional

import aiosqlite

from bot.utils.datetime_helpers import normalize_phone


async def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT,
                phone TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                price INTEGER,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                admin_only BOOLEAN DEFAULT 0,
                sort_order INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id),
                service_id INTEGER NOT NULL REFERENCES services(id),
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                google_event_id TEXT,
                status TEXT DEFAULT 'confirmed',
                reminder_24h_sent BOOLEAN DEFAULT 0,
                reminder_2h_sent BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cancelled_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS days_off (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                reason TEXT
            );
        """)
        await _seed_default_settings(db)
        await db.commit()


async def _seed_default_settings(db: aiosqlite.Connection) -> None:
    defaults = {
        "work_start_hour": "9",
        "work_end_hour": "20",
        "slot_interval_minutes": "30",
        "break_between_minutes": "30",
        "work_days": "0,1,2,3,4,5",
    }
    for key, value in defaults.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )


async def seed_default_services(db_path: str) -> None:
    """Add default services if the table is empty."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM services") as cur:
            row = await cur.fetchone()
            if row[0] > 0:
                return

        default_services = [
            ("Глибокотканинний масаж", 60, 1400,
             "Спина + ноги. Можливе використання блейдів, банок, перкусійного пістолету", 0),
            ("Глибокотканинний масаж", 90, 1800,
             "Робота по всьому тілу. Можливе використання блейдів, банок, перкусійного пістолету", 0),
            ("Лімфодренажний масаж", 60, 1400, "Класичний лімфодренаж", 0),
            ("Лімфодренажний масаж", 90, 1800, "Класичний + магістральний лімфодренаж", 0),
            ("Дитячий масаж 40хв (5-12 років)", 40, 900, None, 0),
            ("Тейпування (1 зона)", 30, 400, None, 0),
            ("Метод сухої голки", 60, 800, "Точкова міофасціальна робота", 0),
            ("Позаробочий / вихідний день", 60, 2000,
             "Прийом в позаробочий час або вихідний за домовленістю", 1),
        ]
        for i, (name, duration, price, desc, admin_only) in enumerate(default_services):
            await db.execute(
                "INSERT INTO services "
                "(name, duration_minutes, price, description, admin_only, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, duration, price, desc, admin_only, i),
            )
        await db.commit()


async def upsert_virtual_client(
    db: aiosqlite.Connection, name: str, phone: str
) -> int:
    """For admin-created bookings: link to real client if phone matches, else create virtual."""
    phone = normalize_phone(phone)
    async with db.execute("SELECT id FROM clients WHERE phone = ?", (phone,)) as cur:
        row = await cur.fetchone()
        if row:
            return row[0]
    virtual_tid = -(abs(hash(phone)) % (10 ** 9))
    return await upsert_client(db, virtual_tid, name, phone=phone)


async def merge_virtual_client(
    db: aiosqlite.Connection, real_client_id: int, phone: str
) -> None:
    """When a real client registers, transfer their virtual bookings to the real account."""
    phone = normalize_phone(phone)
    async with db.execute(
        "SELECT id FROM clients WHERE phone = ? AND telegram_id < 0", (phone,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return
    virtual_id = row[0]
    await db.execute(
        "UPDATE bookings SET client_id = ? WHERE client_id = ?",
        (real_client_id, virtual_id),
    )
    await db.execute("DELETE FROM clients WHERE id = ?", (virtual_id,))
    await db.commit()


# --- Settings ---

async def get_setting(db: aiosqlite.Connection, key: str) -> Optional[str]:
    async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
        row = await cur.fetchone()
        return row[0] if row else None


async def set_setting(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    await db.commit()


# --- Clients ---

async def upsert_client(
    db: aiosqlite.Connection,
    telegram_id: int,
    first_name: str,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    username: Optional[str] = None,
) -> int:
    if phone:
        phone = normalize_phone(phone)
    await db.execute(
        """
        INSERT INTO clients (telegram_id, first_name, last_name, phone, username)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            phone = COALESCE(excluded.phone, phone),
            username = excluded.username
        """,
        (telegram_id, first_name, last_name, phone, username),
    )
    await db.commit()
    async with db.execute(
        "SELECT id FROM clients WHERE telegram_id = ?", (telegram_id,)
    ) as cur:
        row = await cur.fetchone()
        return row[0]


async def get_client_by_telegram_id(
    db: aiosqlite.Connection, telegram_id: int
) -> Optional[dict]:
    async with db.execute(
        "SELECT * FROM clients WHERE telegram_id = ?", (telegram_id,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


# --- Services ---

async def get_active_services(
    db: aiosqlite.Connection, for_admin: bool = False
) -> list[dict]:
    query = (
        "SELECT * FROM services WHERE is_active = 1 ORDER BY sort_order, id"
        if for_admin
        else "SELECT * FROM services WHERE is_active = 1 AND admin_only = 0 ORDER BY sort_order, id"
    )
    async with db.execute(query) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_services(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        "SELECT * FROM services ORDER BY sort_order, id"
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_service(db: aiosqlite.Connection, service_id: int) -> Optional[dict]:
    async with db.execute(
        "SELECT * FROM services WHERE id = ?", (service_id,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_service(
    db: aiosqlite.Connection,
    name: str,
    duration_minutes: int,
    price: Optional[int],
    description: Optional[str],
) -> int:
    async with db.execute(
        "INSERT INTO services (name, duration_minutes, price, description) VALUES (?, ?, ?, ?)",
        (name, duration_minutes, price, description),
    ) as cur:
        await db.commit()
        return cur.lastrowid


async def toggle_service(db: aiosqlite.Connection, service_id: int) -> None:
    await db.execute(
        "UPDATE services SET is_active = NOT is_active WHERE id = ?", (service_id,)
    )
    await db.commit()


# --- Bookings ---

async def create_booking(
    db: aiosqlite.Connection,
    client_id: int,
    service_id: int,
    start_time: str,
    end_time: str,
    google_event_id: Optional[str] = None,
) -> int:
    async with db.execute(
        """
        INSERT INTO bookings (client_id, service_id, start_time, end_time, google_event_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (client_id, service_id, start_time, end_time, google_event_id),
    ) as cur:
        await db.commit()
        return cur.lastrowid


async def get_booking(db: aiosqlite.Connection, booking_id: int) -> Optional[dict]:
    async with db.execute(
        """
        SELECT b.*, c.first_name, c.last_name, c.phone, c.telegram_id,
               s.name as service_name, s.duration_minutes, s.price
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        JOIN services s ON b.service_id = s.id
        WHERE b.id = ?
        """,
        (booking_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_client_upcoming_bookings(
    db: aiosqlite.Connection, client_id: int
) -> list[dict]:
    async with db.execute(
        """
        SELECT b.*, s.name as service_name, s.duration_minutes, s.price
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.client_id = ? AND b.status = 'confirmed' AND b.start_time > datetime('now')
        ORDER BY b.start_time
        """,
        (client_id,),
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_today_bookings(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        """
        SELECT b.*, c.first_name, c.last_name, c.phone,
               s.name as service_name, s.duration_minutes
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        JOIN services s ON b.service_id = s.id
        WHERE b.status = 'confirmed'
          AND date(b.start_time) = date('now')
        ORDER BY b.start_time
        """
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_week_bookings(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        """
        SELECT b.*, c.first_name, c.last_name, c.phone,
               s.name as service_name, s.duration_minutes
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        JOIN services s ON b.service_id = s.id
        WHERE b.status = 'confirmed'
          AND b.start_time >= datetime('now')
          AND b.start_time <= datetime('now', '+7 days')
        ORDER BY b.start_time
        """
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def cancel_booking(
    db: aiosqlite.Connection, booking_id: int
) -> Optional[str]:
    async with db.execute(
        "SELECT google_event_id FROM bookings WHERE id = ?", (booking_id,)
    ) as cur:
        row = await cur.fetchone()
        if not row:
            return None
        google_event_id = row[0]
    await db.execute(
        """
        UPDATE bookings SET status = 'cancelled', cancelled_at = datetime('now')
        WHERE id = ?
        """,
        (booking_id,),
    )
    await db.commit()
    return google_event_id


async def mark_reminder_sent(
    db: aiosqlite.Connection, booking_id: int, reminder_type: str
) -> None:
    col = "reminder_24h_sent" if reminder_type == "24h" else "reminder_2h_sent"
    await db.execute(f"UPDATE bookings SET {col} = 1 WHERE id = ?", (booking_id,))
    await db.commit()


async def get_pending_reminders(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        """
        SELECT b.id, b.start_time, b.reminder_24h_sent, b.reminder_2h_sent,
               c.telegram_id, s.name as service_name
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        JOIN services s ON b.service_id = s.id
        WHERE b.status = 'confirmed'
          AND b.start_time > datetime('now')
        """
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- Days off ---

async def get_days_off(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute("SELECT * FROM days_off ORDER BY date") as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def add_day_off(
    db: aiosqlite.Connection, date: str, reason: Optional[str] = None
) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO days_off (date, reason) VALUES (?, ?)",
        (date, reason),
    )
    await db.commit()


async def remove_day_off(db: aiosqlite.Connection, day_off_id: int) -> None:
    await db.execute("DELETE FROM days_off WHERE id = ?", (day_off_id,))
    await db.commit()


async def is_day_off(db: aiosqlite.Connection, date: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM days_off WHERE date = ?", (date,)
    ) as cur:
        return await cur.fetchone() is not None
