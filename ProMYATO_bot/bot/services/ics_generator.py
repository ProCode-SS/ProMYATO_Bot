from datetime import datetime, timedelta

from icalendar import Alarm, Calendar, Event


def generate_ics(
    service_name: str,
    start: datetime,
    end: datetime,
    therapist_name: str = "Масажист",
    location: str = "",
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Massage Booking Bot//UK")
    cal.add("version", "2.0")

    event = Event()
    event.add("summary", f"Масаж: {service_name}")
    event.add("dtstart", start)
    event.add("dtend", end)
    event.add("description", f"Майстер: {therapist_name}")
    if location:
        event.add("location", location)

    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("trigger", timedelta(hours=-2))
    alarm.add("description", f"Масаж через 2 години: {service_name}")
    event.add_component(alarm)

    cal.add_component(event)
    return cal.to_ical()
