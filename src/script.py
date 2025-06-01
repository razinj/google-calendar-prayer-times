from __future__ import annotations

import datetime as dt
import logging
import os
import typing as t
from urllib import parse as urllib_parse

import httpx
from dateutil import tz
from dateutil.parser import parse
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "ERROR").upper(),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("script")


def _required(key: str) -> str:
    return os.environ[key]


def _required_float(key: str) -> float:
    return float(_required(key))


# DE
LATITUDE = _required_float("LATITUDE")
LONGITUDE = _required_float("LONGITUDE")
CALENDAR_ID = _required("CALENDAR_ID")
TIMEZONE = _required("TIMEZONE")

# MA
LATITUDE_MA = _required_float("LATITUDE_MOROCCO")
LONGITUDE_MA = _required_float("LONGITUDE_MOROCCO")
CALENDAR_ID_MA = _required("CALENDAR_ID_MOROCCO")
TIMEZONE_MA = _required("TIMEZONE_MOROCCO")

DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

PRAYERS_DE = ["fajr", "zuhr", "assr", "maghrib", "ishaa"]
PRAYERS_MA = ["fajr", "dhuhr", "asr", "maghrib", "isha"]
PRAYER_NAMES_MAP = {"zuhr": "dhuhr", "assr": "asr", "ishaa": "isha"}


def get_prayer_canonical_name(name: str) -> str:
    return PRAYER_NAMES_MAP.get(name, name)


def round_up_to_next_minute(dt_: dt.datetime) -> dt.datetime:
    if dt_.second == 0 and dt_.microsecond == 0:
        # Already on the minute boundary
        return dt_

    # Move to the next minute, then strip out seconds & microseconds
    return (dt_ + dt.timedelta(minutes=1)).replace(second=0, microsecond=0)


def get_current_month_bounds(timezone: str) -> tuple[dt.datetime, dt.datetime]:
    now = dt.datetime.now(tz.gettz(timezone))

    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + dt.timedelta(days=32)).replace(
        day=1
    )  # represents first day of the next month at midnight

    return start, end


def chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        filename="service-account.json",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def run_in_batches(service, reqs: list, tag: str):
    def callback(request_id, _, exception):
        if exception:
            logger.error("Request '%s' failed, exception: %s", request_id, exception)

    BATCH_SIZE = 50
    for bi, part in enumerate(chunks(reqs, BATCH_SIZE), 1):
        batch = service.new_batch_http_request()
        for ii, req in enumerate(part, 1):
            batch.add(req, request_id=f"{tag}-{bi}-{ii}", callback=callback)
        batch.execute()


def fetch_prayer_times_de() -> list[dict[str, str]]:
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
        "year": str(dt.date.today().year),
    }
    response = httpx.post(api_url, json=body)
    response.raise_for_status()

    prayers = []
    current_month = dt.date.today().month

    for item in response.json().get("calendar", []):
        if parse(item["astro_data"]["gregorian_date"]).month != current_month:
            continue

        prayers.append(item["astro_data"])

    return prayers


def fetch_prayer_times_ma() -> list[dict]:
    current_year = dt.date.today().year
    current_month = str(dt.date.today().month).zfill(2)

    # See: https://aladhan.com/prayer-times-api#tag/Monthly-Annual-Prayer-Times-Calendar/paths/~1v1~1calendar~1%7Byear%7D~1%7Bmonth%7D/get  # noqa: E501
    base_api_url = f"https://api.aladhan.com/v1/calendar/{current_year}/{current_month}"
    query_params = {
        "latitude": LATITUDE_MA,
        "longitude": LONGITUDE_MA,
        "method": 21,  # Morocco
        "iso8601": "true",
        "timezonestring": TIMEZONE_MA,
    }
    api_url = "{}?{}".format(base_api_url, urllib_parse.urlencode(query_params))

    response = httpx.get(api_url)
    response.raise_for_status()

    return response.json().get("data", [])


def delete_current_month_events(
    calendar_id: str, timezone: str, service: t.Any
) -> None:
    start, end = get_current_month_bounds(timezone)
    requests = []
    page_token = None

    while True:
        page = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                showDeleted=False,
                pageToken=page_token,
            )
            .execute()
        )

        for item in page.get("items", []):
            requests.append(
                service.events().delete(calendarId=calendar_id, eventId=item["id"])
            )

        page_token = page.get("nextPageToken")
        if not page_token:
            break

    run_in_batches(service, requests, f"delete-{calendar_id[:10]}-events")


def build_prayer_event(
    summary: str, prayer_datetime: dt.datetime, timezone: str
) -> dict:
    return {
        "summary": summary,
        "start": {
            "dateTime": round_up_to_next_minute(prayer_datetime).strftime(
                DATE_TIME_FORMAT
            ),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": round_up_to_next_minute(
                prayer_datetime + dt.timedelta(minutes=15)
            ).strftime(DATE_TIME_FORMAT),
            "timeZone": timezone,
        },
    }


def create_events_de(service: t.Any) -> None:
    creation_requests = []

    for day in fetch_prayer_times_de():
        for prayer in PRAYERS_DE:
            prayer_datetime = parse(day[prayer])
            event_summary = get_prayer_canonical_name(prayer).capitalize()

            creation_requests.append(
                service.events().insert(
                    calendarId=CALENDAR_ID,
                    body=build_prayer_event(event_summary, prayer_datetime, TIMEZONE),
                )
            )

    run_in_batches(service, creation_requests, "create-events-de")


def create_events_ma(service):
    creation_requests = []

    for day in fetch_prayer_times_ma():
        timings = t.cast(dict[str, str], day.get("timings", {}))

        for prayer_name, prayer_datetime_raw in timings.items():
            prayer_name_normalized = prayer_name.lower()
            if prayer_name_normalized not in PRAYERS_MA:
                continue

            prayer_datetime = parse(prayer_datetime_raw)
            event_summary = f"MA - {prayer_name_normalized.capitalize()}"

            creation_requests.append(
                service.events().insert(
                    calendarId=CALENDAR_ID_MA,
                    body=build_prayer_event(
                        event_summary, prayer_datetime, TIMEZONE_MA
                    ),
                )
            )

    run_in_batches(service, creation_requests, "create-events-ma")


def main():
    service = get_calendar_service()

    delete_current_month_events(CALENDAR_ID, TIMEZONE, service)
    create_events_de(service)
    delete_current_month_events(CALENDAR_ID_MA, TIMEZONE_MA, service)
    create_events_ma(service)


if __name__ == "__main__":
    main()
