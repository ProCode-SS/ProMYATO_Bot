import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.models.database import get_booking, get_pending_reminders, mark_reminder_sent
from bot.utils.datetime_helpers import format_date_uk, format_time, utc_to_kyiv
from bot.utils.texts import MONTHS_UK, REMINDER_24H, REMINDER_2H

logger = logging.getLogger(__name__)
UTC_TZ = ZoneInfo("UTC")


class ReminderService:
    def __init__(
        self, scheduler: AsyncIOScheduler, bot: Bot, db_path: str
    ) -> None:
        self.scheduler = scheduler
        self.bot = bot
        self.db_path = db_path

    def schedule_reminders(self, booking_id: int, start_time_utc: datetime) -> None:
        now = datetime.now(UTC_TZ)
        run_24h = start_time_utc - timedelta(hours=24)
        run_2h = start_time_utc - timedelta(hours=2)

        if run_24h > now:
            self.scheduler.add_job(
                self.send_reminder,
                trigger="date",
                run_date=run_24h,
                args=[booking_id, "24h"],
                id=f"reminder_24h_{booking_id}",
                replace_existing=True,
            )
        if run_2h > now:
            self.scheduler.add_job(
                self.send_reminder,
                trigger="date",
                run_date=run_2h,
                args=[booking_id, "2h"],
                id=f"reminder_2h_{booking_id}",
                replace_existing=True,
            )

    def cancel_reminders(self, booking_id: int) -> None:
        for job_id in [f"reminder_24h_{booking_id}", f"reminder_2h_{booking_id}"]:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

    async def send_reminder(self, booking_id: int, reminder_type: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            booking = await get_booking(db, booking_id)
            if not booking or booking["status"] != "confirmed":
                return

            start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
            template = REMINDER_24H if reminder_type == "24h" else REMINDER_2H
            text = template.format(
                service=booking["service_name"],
                date=format_date_uk(start_kyiv.date(), MONTHS_UK),
                time=format_time(start_kyiv.time()),
            )
            if booking["telegram_id"] <= 0:
                return  # virtual client — no real Telegram account
            try:
                await self.bot.send_message(chat_id=booking["telegram_id"], text=text)
                await mark_reminder_sent(db, booking_id, reminder_type)
            except Exception as e:
                logger.error(
                    "Failed to send reminder for booking %d: %s", booking_id, e
                )

    async def reschedule_all(self) -> None:
        """On bot startup, reschedule all pending reminders."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await get_pending_reminders(db)
            for row in rows:
                start_utc = datetime.fromisoformat(row["start_time"])
                if not row["reminder_24h_sent"] or not row["reminder_2h_sent"]:
                    self.schedule_reminders(row["id"], start_utc)
        logger.info("Rescheduled reminders for %d bookings", len(rows))
