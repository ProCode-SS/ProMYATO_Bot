import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.keyboards.client_kb import reminder_confirm_keyboard
from bot.models.database import (
    cancel_booking,
    get_booking,
    get_pending_reminders,
    get_unconfirmed_past_deadline,
    mark_reminder_sent,
    set_reminder_24h_sent_at,
    create_group_slot,
    update_group_slot_message,
)
from bot.utils.datetime_helpers import format_date_uk, format_time, utc_to_kyiv
from bot.utils.texts import (
    AUTO_CANCELLED_ADMIN,
    AUTO_CANCELLED_CLIENT,
    MONTHS_UK,
    REMINDER_24H,
    REMINDER_2H,
)

logger = logging.getLogger(__name__)
UTC_TZ = ZoneInfo("UTC")


class ReminderService:
    def __init__(
        self,
        scheduler: AsyncIOScheduler,
        bot: Bot,
        db_path: str,
        calendar=None,
        admin_ids: Optional[list] = None,
        cancellation_group_id: str = "",
    ) -> None:
        self.scheduler = scheduler
        self.bot = bot
        self.db_path = db_path
        self.calendar = calendar
        self.admin_ids = admin_ids or []
        self.cancellation_group_id = cancellation_group_id

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

    def schedule_confirmation_deadline(
        self, booking_id: int, sent_at: datetime
    ) -> None:
        """Schedule auto-cancel 12h after the 24h reminder was sent."""
        deadline = sent_at + timedelta(hours=12)
        now = datetime.now(UTC_TZ)
        if deadline > now:
            self.scheduler.add_job(
                self.check_confirmation_deadline,
                trigger="date",
                run_date=deadline,
                args=[booking_id],
                id=f"confirm_deadline_{booking_id}",
                replace_existing=True,
            )

    def cancel_reminders(self, booking_id: int) -> None:
        for job_id in [
            f"reminder_24h_{booking_id}",
            f"reminder_2h_{booking_id}",
            f"confirm_deadline_{booking_id}",
        ]:
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

            kwargs = {}
            if reminder_type == "24h":
                kwargs["reply_markup"] = reminder_confirm_keyboard(booking_id)

            try:
                await self.bot.send_message(
                    chat_id=booking["telegram_id"], text=text, **kwargs
                )
                await mark_reminder_sent(db, booking_id, reminder_type)

                if reminder_type == "24h":
                    sent_at = datetime.now(UTC_TZ)
                    await set_reminder_24h_sent_at(db, booking_id, sent_at.isoformat())
                    self.schedule_confirmation_deadline(booking_id, sent_at)
            except Exception as e:
                logger.error(
                    "Failed to send reminder for booking %d: %s", booking_id, e
                )

    async def check_confirmation_deadline(self, booking_id: int) -> None:
        """Auto-cancel booking if not confirmed within 12h of 24h reminder."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            booking = await get_booking(db, booking_id)

            if not booking or booking["status"] != "confirmed":
                return
            if booking["confirmed_at"]:
                return  # already confirmed — nothing to do

            # Auto-cancel
            google_event_id = await cancel_booking(db, booking_id)

            # Cancel 2h reminder
            self.cancel_reminders(booking_id)

            if google_event_id and self.calendar:
                try:
                    await self.calendar.delete_event(google_event_id)
                except Exception as e:
                    logger.warning("Failed to delete calendar event: %s", e)

            start_kyiv = utc_to_kyiv(datetime.fromisoformat(booking["start_time"]))
            date_label = format_date_uk(start_kyiv.date(), MONTHS_UK)
            time_label = format_time(start_kyiv.time())

            # Notify client
            if booking["telegram_id"] > 0:
                try:
                    await self.bot.send_message(
                        chat_id=booking["telegram_id"],
                        text=AUTO_CANCELLED_CLIENT.format(
                            service=booking["service_name"],
                            date=date_label,
                            time=time_label,
                        ),
                    )
                except Exception as e:
                    logger.error("Failed to notify client of auto-cancel: %s", e)

            # Notify admins
            name = f"{booking['first_name']} {booking.get('last_name') or ''}".strip()
            admin_text = AUTO_CANCELLED_ADMIN.format(
                client=name,
                service=booking["service_name"],
                date=date_label,
                time=time_label,
            )
            for aid in self.admin_ids:
                try:
                    await self.bot.send_message(chat_id=aid, text=admin_text)
                except Exception as e:
                    logger.error("Failed to notify admin of auto-cancel: %s", e)

            # Send to cancellation group
            await self._notify_group(db, booking, date_label, time_label, is_urgent=False)

            logger.info("Auto-cancelled booking %d (no confirmation within 12h)", booking_id)

    async def _notify_group(
        self,
        db,
        booking: dict,
        date_label: str,
        time_label: str,
        is_urgent: bool,
    ) -> None:
        """Send freed slot notification to the cancellation group."""
        if not self.cancellation_group_id:
            return

        from bot.keyboards.client_kb import group_book_keyboard
        from bot.utils.datetime_helpers import utc_to_kyiv
        from bot.utils.texts import (
            GROUP_SLOT_AVAILABLE,
            GROUP_SLOT_AVAILABLE_URGENT,
        )

        start_utc = datetime.fromisoformat(booking["start_time"])
        end_utc = datetime.fromisoformat(booking["end_time"])
        start_kyiv = utc_to_kyiv(start_utc)
        end_kyiv = utc_to_kyiv(end_utc)
        time_end_label = format_time(end_kyiv.time())

        price_line = f"💰 {booking['price']}₴" if booking.get("price") else ""
        template = GROUP_SLOT_AVAILABLE_URGENT if is_urgent else GROUP_SLOT_AVAILABLE
        text = template.format(
            service=booking["service_name"],
            date=date_label,
            time_start=time_label,
            time_end=time_end_label,
            price_line=price_line,
        )

        slot_id = await create_group_slot(
            db,
            service_id=booking["service_id"],
            start_time=booking["start_time"],
            end_time=booking["end_time"],
        )

        try:
            sent = await self.bot.send_message(
                chat_id=int(self.cancellation_group_id),
                text=text,
                reply_markup=group_book_keyboard(slot_id),
            )
            await update_group_slot_message(
                db, slot_id, sent.message_id, sent.chat.id
            )
        except Exception as e:
            logger.error("Failed to send group cancellation notification: %s", e)

    async def reschedule_all(self) -> None:
        """On bot startup, reschedule all pending reminders and confirmation deadlines."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await get_pending_reminders(db)
            now = datetime.now(UTC_TZ)
            for row in rows:
                start_utc = datetime.fromisoformat(row["start_time"])
                if not row["reminder_24h_sent"] or not row["reminder_2h_sent"]:
                    self.schedule_reminders(row["id"], start_utc)

                # Reschedule confirmation deadline if 24h reminder was sent but not confirmed
                if (
                    row["reminder_24h_sent"]
                    and not row["confirmed_at"]
                    and row["reminder_24h_sent_at"]
                ):
                    sent_at = datetime.fromisoformat(row["reminder_24h_sent_at"])
                    if not sent_at.tzinfo:
                        sent_at = sent_at.replace(tzinfo=UTC_TZ)
                    self.schedule_confirmation_deadline(row["id"], sent_at)

        logger.info("Rescheduled reminders for %d bookings", len(rows))
