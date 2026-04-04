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
                requires_approval BOOLEAN DEFAULT 0,
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
                confirmed_at TIMESTAMP,
                reminder_24h_sent_at TIMESTAMP,
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

            CREATE TABLE IF NOT EXISTS vip_clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER REFERENCES clients(id),
                phone TEXT NOT NULL UNIQUE,
                notes TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS available_group_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL REFERENCES services(id),
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                group_message_id INTEGER,
                group_chat_id INTEGER,
                is_booked BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pending_slot_claims (
                telegram_user_id INTEGER PRIMARY KEY,
                slot_id INTEGER NOT NULL REFERENCES available_group_slots(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await _migrate_existing_db(db)
        await _seed_default_settings(db)
        await db.commit()


async def _migrate_existing_db(db: aiosqlite.Connection) -> None:
    """Add new columns to existing DB tables if they don't exist yet."""
    new_booking_cols = [
        ("confirmed_at", "TIMESTAMP"),
        ("reminder_24h_sent_at", "TIMESTAMP"),
    ]
    async with db.execute("PRAGMA table_info(bookings)") as cur:
        existing = {row[1] for row in await cur.fetchall()}
    for col, col_type in new_booking_cols:
        if col not in existing:
            await db.execute(f"ALTER TABLE bookings ADD COLUMN {col} {col_type}")

    # Services: add requires_approval column; convert existing admin_only services
    async with db.execute("PRAGMA table_info(services)") as cur:
        existing_svc = {row[1] for row in await cur.fetchall()}
    if "requires_approval" not in existing_svc:
        await db.execute(
            "ALTER TABLE services ADD COLUMN requires_approval BOOLEAN DEFAULT 0"
        )
        # Convert all existing admin_only services to client-visible + requires_approval
        await db.execute(
            "UPDATE services SET admin_only = 0, requires_approval = 1 WHERE admin_only = 1"
        )


async def _seed_default_settings(db: aiosqlite.Connection) -> None:
    defaults = {
        "work_start_hour": "9",
        "work_end_hour": "20",
        "slot_interval_minutes": "30",
        "break_between_minutes": "30",
        "work_days": "0,1,2,3,4,5",
        "bookings_open": "1",
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
            # (name, duration, price, desc, admin_only, requires_approval)
            ("Глибокотканинний масаж", 60, 1400,
             "Спина + ноги. Можливе використання блейдів, банок, перкусійного пістолету", 0, 0),
            ("Глибокотканинний масаж", 90, 1800,
             "Робота по всьому тілу. Можливе використання блейдів, банок, перкусійного пістолету", 0, 0),
            ("Лімфодренажний масаж", 60, 1400, "Класичний лімфодренаж", 0, 0),
            ("Лімфодренажний масаж", 90, 1800, "Класичний + магістральний лімфодренаж", 0, 0),
            ("Дитячий масаж 40хв (5-12 років)", 40, 900, None, 0, 0),
            ("Тейпування (1 зона)", 30, 400, None, 0, 0),
            ("Метод сухої голки", 60, 800, "Точкова міофасціальна робота", 0, 0),
            ("Позаробочий / вихідний день", 60, 2000,
             "Прийом в позаробочий час або вихідний за домовленістю", 0, 1),
        ]
        for i, (name, duration, price, desc, admin_only, requires_approval) in enumerate(default_services):
            await db.execute(
                "INSERT INTO services "
                "(name, duration_minutes, price, description, admin_only, requires_approval, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, duration, price, desc, admin_only, requires_approval, i),
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


async def get_client_by_phone(
    db: aiosqlite.Connection, phone: str
) -> Optional[dict]:
    phone = normalize_phone(phone)
    async with db.execute(
        "SELECT * FROM clients WHERE phone = ? AND telegram_id > 0", (phone,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def search_clients_by_name(
    db: aiosqlite.Connection, query: str
) -> list[dict]:
    q = f"%{query}%"
    async with db.execute(
        """
        SELECT c.*, v.id as vip_id
        FROM clients c
        LEFT JOIN vip_clients v ON v.client_id = c.id
        WHERE (c.first_name LIKE ? OR c.last_name LIKE ?) AND c.telegram_id > 0
        ORDER BY c.first_name, c.last_name
        LIMIT 20
        """,
        (q, q),
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


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


async def delete_service(db: aiosqlite.Connection, service_id: int) -> None:
    await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    await db.commit()


async def has_active_bookings_for_service(db: aiosqlite.Connection, service_id: int) -> bool:
    async with db.execute(
        "SELECT 1 FROM bookings WHERE service_id = ? AND status IN ('confirmed', 'pending_approval') LIMIT 1",
        (service_id,),
    ) as cur:
        return await cur.fetchone() is not None


# --- Bookings ---

async def create_booking(
    db: aiosqlite.Connection,
    client_id: int,
    service_id: int,
    start_time: str,
    end_time: str,
    google_event_id: Optional[str] = None,
    status: str = "confirmed",
) -> int:
    async with db.execute(
        """
        INSERT INTO bookings (client_id, service_id, start_time, end_time, google_event_id, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (client_id, service_id, start_time, end_time, google_event_id, status),
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
        WHERE b.client_id = ?
          AND b.status IN ('confirmed', 'pending_approval')
          AND b.start_time > datetime('now')
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


async def set_reminder_24h_sent_at(
    db: aiosqlite.Connection, booking_id: int, sent_at: str
) -> None:
    await db.execute(
        "UPDATE bookings SET reminder_24h_sent_at = ? WHERE id = ?",
        (sent_at, booking_id),
    )
    await db.commit()


async def confirm_booking_by_reminder(
    db: aiosqlite.Connection, booking_id: int, confirmed_at: str
) -> None:
    await db.execute(
        "UPDATE bookings SET confirmed_at = ? WHERE id = ? AND status = 'confirmed'",
        (confirmed_at, booking_id),
    )
    await db.commit()


async def get_pending_reminders(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        """
        SELECT b.id, b.start_time, b.reminder_24h_sent, b.reminder_2h_sent,
               b.confirmed_at, b.reminder_24h_sent_at,
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


async def is_bookings_open(db: aiosqlite.Connection) -> bool:
    return (await get_setting(db, "bookings_open") or "1") == "1"


async def approve_pending_booking(
    db: aiosqlite.Connection,
    booking_id: int,
    google_event_id: Optional[str] = None,
) -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        UPDATE bookings
        SET status = 'confirmed', confirmed_at = ?,
            google_event_id = COALESCE(?, google_event_id)
        WHERE id = ?
        """,
        (now, google_event_id, booking_id),
    )
    await db.commit()


async def reject_pending_booking(db: aiosqlite.Connection, booking_id: int) -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE bookings SET status = 'cancelled', cancelled_at = ? WHERE id = ?",
        (now, booking_id),
    )
    await db.commit()


async def get_pending_approval_bookings(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        """
        SELECT b.*, c.first_name, c.last_name, c.phone, c.telegram_id,
               s.name as service_name, s.duration_minutes
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        JOIN services s ON b.service_id = s.id
        WHERE b.status = 'pending_approval'
        ORDER BY b.created_at
        """
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_unconfirmed_past_deadline(db: aiosqlite.Connection) -> list[dict]:
    """Bookings where 24h reminder was sent 12+ hours ago but not confirmed."""
    async with db.execute(
        """
        SELECT b.id, b.start_time, b.reminder_24h_sent_at,
               c.telegram_id, s.name as service_name
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        JOIN services s ON b.service_id = s.id
        WHERE b.status = 'confirmed'
          AND b.confirmed_at IS NULL
          AND b.reminder_24h_sent_at IS NOT NULL
          AND datetime(b.reminder_24h_sent_at, '+12 hours') <= datetime('now')
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


# --- VIP clients ---

async def add_vip_client(
    db: aiosqlite.Connection,
    phone: str,
    client_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> int:
    phone = normalize_phone(phone)
    async with db.execute(
        """
        INSERT OR IGNORE INTO vip_clients (phone, client_id, notes)
        VALUES (?, ?, ?)
        """,
        (phone, client_id, notes),
    ) as cur:
        await db.commit()
        if cur.lastrowid:
            return cur.lastrowid
    async with db.execute(
        "SELECT id FROM vip_clients WHERE phone = ?", (phone,)
    ) as cur:
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_vip_by_phone(
    db: aiosqlite.Connection, phone: str
) -> Optional[dict]:
    phone = normalize_phone(phone)
    async with db.execute(
        """
        SELECT v.*, c.first_name, c.last_name, c.telegram_id
        FROM vip_clients v
        LEFT JOIN clients c ON v.client_id = c.id
        WHERE v.phone = ?
        """,
        (phone,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_all_vips(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        """
        SELECT v.*, c.first_name, c.last_name, c.telegram_id
        FROM vip_clients v
        LEFT JOIN clients c ON v.client_id = c.id
        ORDER BY v.added_at
        """
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def remove_vip_client(db: aiosqlite.Connection, vip_id: int) -> None:
    await db.execute("DELETE FROM vip_clients WHERE id = ?", (vip_id,))
    await db.commit()


async def link_vip_to_client(
    db: aiosqlite.Connection, phone: str, client_id: int
) -> None:
    """When client registers, link their VIP record to their client_id."""
    phone = normalize_phone(phone)
    await db.execute(
        "UPDATE vip_clients SET client_id = ? WHERE phone = ? AND client_id IS NULL",
        (client_id, phone),
    )
    await db.commit()


async def is_client_vip(db: aiosqlite.Connection, phone: str) -> bool:
    phone = normalize_phone(phone)
    async with db.execute(
        "SELECT 1 FROM vip_clients WHERE phone = ?", (phone,)
    ) as cur:
        return await cur.fetchone() is not None


# --- Group slots ---

async def create_group_slot(
    db: aiosqlite.Connection,
    service_id: int,
    start_time: str,
    end_time: str,
) -> int:
    async with db.execute(
        """
        INSERT INTO available_group_slots (service_id, start_time, end_time)
        VALUES (?, ?, ?)
        """,
        (service_id, start_time, end_time),
    ) as cur:
        await db.commit()
        return cur.lastrowid


async def update_group_slot_message(
    db: aiosqlite.Connection,
    slot_id: int,
    group_message_id: int,
    group_chat_id: int,
) -> None:
    await db.execute(
        "UPDATE available_group_slots SET group_message_id = ?, group_chat_id = ? WHERE id = ?",
        (group_message_id, group_chat_id, slot_id),
    )
    await db.commit()


async def get_group_slot(
    db: aiosqlite.Connection, slot_id: int
) -> Optional[dict]:
    async with db.execute(
        """
        SELECT gs.*, s.name as service_name, s.price, s.duration_minutes
        FROM available_group_slots gs
        JOIN services s ON gs.service_id = s.id
        WHERE gs.id = ?
        """,
        (slot_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def mark_group_slot_booked(db: aiosqlite.Connection, slot_id: int) -> None:
    await db.execute(
        "UPDATE available_group_slots SET is_booked = 1 WHERE id = ?", (slot_id,)
    )
    await db.commit()


async def create_pending_slot_claim(
    db: aiosqlite.Connection, telegram_user_id: int, slot_id: int
) -> None:
    await db.execute(
        """
        INSERT OR REPLACE INTO pending_slot_claims (telegram_user_id, slot_id)
        VALUES (?, ?)
        """,
        (telegram_user_id, slot_id),
    )
    await db.commit()


async def get_pending_slot_claim(
    db: aiosqlite.Connection, telegram_user_id: int
) -> Optional[dict]:
    async with db.execute(
        """
        SELECT psc.*, gs.service_id, gs.start_time, gs.end_time,
               gs.is_booked, gs.group_message_id, gs.group_chat_id,
               s.name as service_name, s.duration_minutes, s.price
        FROM pending_slot_claims psc
        JOIN available_group_slots gs ON psc.slot_id = gs.id
        JOIN services s ON gs.service_id = s.id
        WHERE psc.telegram_user_id = ?
        """,
        (telegram_user_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def delete_pending_slot_claim(
    db: aiosqlite.Connection, telegram_user_id: int
) -> None:
    await db.execute(
        "DELETE FROM pending_slot_claims WHERE telegram_user_id = ?",
        (telegram_user_id,),
    )
    await db.commit()
