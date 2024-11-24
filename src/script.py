import datetime
import os
import typing as t

import httpx
from dateutil.parser import parse
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore

load_dotenv()

LATITUDE = os.getenv("LATITUDE")
LONGITUDE = os.getenv("LONGITUDE")
CALENDAR_ID = os.getenv("CALENDAR_ID")
TIMEZONE = os.getenv("TIMEZONE")


def fetch_prayer_times() -> t.Dict[str, t.Any]:
    if not LATITUDE or not LONGITUDE:
        raise ValueError("LATITUDE and LONGITUDE are required")

    api_url = "https://prayer-times-api.izaachen.de"
    body = {
        "taqdir_method": "new_method",
        "natural_motion_alignment_interpolation": True,
        "longest_day_check": True,
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "gmt_diff_hours": 1,
        "fajr_no_taqdir": False,
        "observe_dst": True,
        "dst_deviation": 1,
    }
    response = httpx.post(api_url, json=body)

    response.raise_for_status()

    return response.json()


def get_current_month_prayer_times(
    prayer_times_calendar: t.List[t.Any],
) -> t.List[t.Dict[str, str]]:
    if not prayer_times_calendar:
        raise ValueError("No prayer times supplied.")

    result: t.List[t.Dict[str, str]] = []
    current_month = datetime.date.today().month

    for day in prayer_times_calendar:
        day_month = parse(day["astro_data"]["gregorian_date"]).month
        if day_month == current_month:
            result.append(day["astro_data"])

    return result


def get_credentials() -> t.Any:
    credentials = service_account.Credentials.from_service_account_file(
        filename="service-account.json",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )

    return credentials


def create_calendar_events(
    credentials: t.Any, prayer_times_days: t.List[t.Dict[str, str]]
):
    if not CALENDAR_ID or not TIMEZONE:
        raise ValueError("CALENDAR_ID and TIMEZONE are required.")

    service = build("calendar", "v3", credentials=credentials)

    def create_single_calendar_event(
        summary: str, start_date: datetime.datetime, end_date: datetime.datetime
    ):
        event = {
            "summary": summary,
            "start": {
                "dateTime": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": TIMEZONE,
            },
        }

        # See: https://developers.google.com/resources/api-libraries/documentation/calendar/v3/python/latest/calendar_v3.events.html#insert
        event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        print(f"Event created: {event.get('summary')}")

    for day in prayer_times_days:
        for prayer_name in ["fajr", "zuhr", "assr", "maghrib", "ishaa"]:
            prayer_datetime = parse(day[prayer_name])
            create_single_calendar_event(
                summary=prayer_name.capitalize(),
                start_date=prayer_datetime,
                end_date=prayer_datetime + datetime.timedelta(minutes=10),
            )


if __name__ == "__main__":
    prayer_times_raw = fetch_prayer_times()
    prayer_times_calendar = prayer_times_raw.get("calendar", [])
    create_calendar_events(
        credentials=get_credentials(),
        prayer_times_days=get_current_month_prayer_times(prayer_times_calendar),
    )
