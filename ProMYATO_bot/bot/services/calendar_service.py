import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
UTC_TZ = ZoneInfo("UTC")


class CalendarService:
    def __init__(self, calendar_id: str, service_account_file: str) -> None:
        self.calendar_id = calendar_id
        self._service_account_file = service_account_file
        self._service = None

    def _get_service(self):
        if self._service is None:
            creds = service_account.Credentials.from_service_account_file(
                self._service_account_file, scopes=SCOPES
            )
            self._service = build(
                "calendar", "v3", credentials=creds, cache_discovery=False
            )
        return self._service

    async def get_busy_slots(
        self, date_from: date, date_to: date
    ) -> list[tuple[datetime, datetime]]:
        """Return all busy periods in UTC for the given date range."""
        for attempt in range(3):
            try:
                service = self._get_service()
                body = {
                    "timeMin": datetime.combine(
                        date_from, datetime.min.time(), tzinfo=UTC_TZ
                    ).isoformat(),
                    "timeMax": datetime.combine(
                        date_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC_TZ
                    ).isoformat(),
                    "items": [{"id": self.calendar_id}],
                }
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: service.freebusy().query(body=body).execute(),
                )
                busy = result["calendars"][self.calendar_id].get("busy", [])
                periods = []
                for period in busy:
                    start = datetime.fromisoformat(
                        period["start"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(
                        period["end"].replace("Z", "+00:00")
                    )
                    periods.append((start, end))
                return periods
            except HttpError as e:
                logger.error(
                    "Google Calendar API error (attempt %d): %s", attempt + 1, e
                )
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        raise RuntimeError("Google Calendar API unavailable after 3 retries")

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
    ) -> str:
        """Create a calendar event. Returns event_id."""
        service = self._get_service()
        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Kyiv"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Kyiv"},
        }
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.events()
                .insert(calendarId=self.calendar_id, body=event_body)
                .execute(),
            )
            return result["id"]
        except Exception as e:
            logger.error("Failed to create calendar event: %s", e)
            raise

    async def delete_event(self, event_id: str) -> None:
        """Delete a calendar event (best-effort on cancellation)."""
        try:
            service = self._get_service()
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.events()
                .delete(calendarId=self.calendar_id, eventId=event_id)
                .execute(),
            )
        except Exception as e:
            logger.warning("Failed to delete calendar event %s: %s", event_id, e)
