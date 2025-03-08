import datetime
import os
import typing as t
from urllib import parse as urllib_parse

import httpx
from dateutil.parser import parse
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore

load_dotenv()

LATITUDE = os.environ["LATITUDE"]
LONGITUDE = os.environ["LONGITUDE"]
CALENDAR_ID = os.environ["CALENDAR_ID"]
TIMEZONE = os.environ["TIMEZONE"]

LATITUDE_MOROCCO = os.environ["LATITUDE_MOROCCO"]
LONGITUDE_MOROCCO = os.environ["LONGITUDE_MOROCCO"]
CALENDAR_ID_MOROCCO = os.environ["CALENDAR_ID_MOROCCO"]
TIMEZONE_MOROCCO = os.environ["TIMEZONE_MOROCCO"]

DATE_TIME_FORMATTING = "%Y-%m-%dT%H:%M:%S"


def get_english_name_for_prayer(german_prayer_name: str) -> str:
    different_prayer_names_map = {"zuhr": "dhuhr", "assr": "asr", "ishaa": "isha"}

    name = different_prayer_names_map.get(german_prayer_name, None)

    return name or german_prayer_name


def round_up_to_next_minute(dt: datetime.datetime) -> datetime.datetime:
    if dt.second == 0 and dt.microsecond == 0:
        # Already on the minute boundary
        return dt

    # Move to the next minute, then strip out seconds & microseconds
    return (dt + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)


def fetch_prayer_times() -> t.Dict[str, t.Any]:
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
        "year": str(datetime.date.today().year),
    }
    response = httpx.post(api_url, json=body)

    response.raise_for_status()

    return response.json()


def fetch_prayer_times_morocco() -> t.Dict[str, t.Any]:
    year = str(datetime.date.today().year)
    month = str(datetime.date.today().month)

    # See: https://aladhan.com/prayer-times-api#tag/Monthly-Annual-Prayer-Times-Calendar/paths/~1v1~1calendar~1%7Byear%7D~1%7Bmonth%7D/get  # noqa: E501

    initial_api_url = f"https://api.aladhan.com/v1/calendar/{year}/{month}"
    query_params = {
        "latitude": LATITUDE_MOROCCO,
        "longitude": LONGITUDE_MOROCCO,
        "method": 21,  # Morocco
        "iso8601": "true",
        "timezonestring": TIMEZONE_MOROCCO,
    }
    api_url = "{}?{}".format(initial_api_url, urllib_parse.urlencode(query_params))

    response = httpx.get(api_url)

    response.raise_for_status()

    return response.json()


def get_current_month_prayer_times(
    prayer_times_calendar: t.List[t.Any],
) -> t.List[t.Dict[str, str]]:
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
) -> None:
    if not prayer_times_days:
        raise ValueError("No prayer times supplied")

    service = build("calendar", "v3", credentials=credentials)

    def create_single_calendar_event(
        summary: str, start_date: datetime.datetime, end_date: datetime.datetime
    ):
        event = {
            "summary": summary,
            "start": {
                "dateTime": round_up_to_next_minute(start_date).strftime(
                    DATE_TIME_FORMATTING
                ),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": round_up_to_next_minute(end_date).strftime(
                    DATE_TIME_FORMATTING
                ),
                "timeZone": TIMEZONE,
            },
        }

        # See: https://developers.google.com/resources/api-libraries/documentation/calendar/v3/python/latest/calendar_v3.events.html#insert # noqa: E501
        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

    for prayer_times_day in prayer_times_days:
        for prayer_name in ["fajr", "zuhr", "assr", "maghrib", "ishaa"]:
            prayer_datetime = parse(prayer_times_day[prayer_name])
            create_single_calendar_event(
                summary=get_english_name_for_prayer(prayer_name).capitalize(),
                start_date=prayer_datetime,
                end_date=prayer_datetime + datetime.timedelta(minutes=15),
            )

    print("[DE] Events created!")


def create_calendar_events_morocco(
    credentials: t.Any, prayer_times_days: t.List[t.Dict[str, str]]
) -> None:
    if not prayer_times_days:
        raise ValueError("No prayer times supplied")

    service = build("calendar", "v3", credentials=credentials)

    def create_single_calendar_event(
        summary: str, start_date: datetime.datetime, end_date: datetime.datetime
    ):
        event = {
            "summary": f"MA - {summary}",
            "start": {
                "dateTime": round_up_to_next_minute(start_date).strftime(
                    DATE_TIME_FORMATTING
                ),
                "timeZone": TIMEZONE_MOROCCO,
            },
            "end": {
                "dateTime": round_up_to_next_minute(end_date).strftime(
                    DATE_TIME_FORMATTING
                ),
                "timeZone": TIMEZONE_MOROCCO,
            },
        }

        # See: https://developers.google.com/resources/api-libraries/documentation/calendar/v3/python/latest/calendar_v3.events.html#insert # noqa: E501
        service.events().insert(calendarId=CALENDAR_ID_MOROCCO, body=event).execute()

    for day in prayer_times_days:
        timings = t.cast(t.Dict[str, str], day.get("timings"))

        if not timings:
            continue

        for prayer_name, prayer_datetime_raw in timings.items():
            if prayer_name.lower() not in ["fajr", "dhuhr", "asr", "maghrib", "isha"]:
                continue

            prayer_datetime = parse(prayer_datetime_raw)

            create_single_calendar_event(
                summary=prayer_name.capitalize(),
                start_date=prayer_datetime,
                end_date=prayer_datetime + datetime.timedelta(minutes=15),
            )

    print("[MA] Events created!")


if __name__ == "__main__":
    # DE
    prayer_times_raw = fetch_prayer_times()
    prayer_times_calendar = prayer_times_raw.get("calendar", [])
    create_calendar_events(
        credentials=get_credentials(),
        prayer_times_days=get_current_month_prayer_times(prayer_times_calendar),
    )

    # MA
    prayer_times_raw_morocco = fetch_prayer_times_morocco()
    prayer_times_data = prayer_times_raw_morocco.get("data", [])
    create_calendar_events_morocco(
        credentials=get_credentials(),
        prayer_times_days=prayer_times_data,
    )
