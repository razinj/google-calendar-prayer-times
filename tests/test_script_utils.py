import datetime as dt
import os
import types

import pytest
from dateutil import tz

os.environ.setdefault("LATITUDE", "50.0")
os.environ.setdefault("LONGITUDE", "6.0")
os.environ.setdefault("CALENDAR_ID", "calendar-de")
os.environ.setdefault("TIMEZONE", "Europe/Berlin")
os.environ.setdefault("LATITUDE_MOROCCO", "33.6")
os.environ.setdefault("LONGITUDE_MOROCCO", "-7.6")
os.environ.setdefault("CALENDAR_ID_MOROCCO", "calendar-ma")
os.environ.setdefault("TIMEZONE_MOROCCO", "Africa/Casablanca")

from src import script  # noqa: E402


def test_keeps_minute_boundary_unchanged() -> None:
    value = dt.datetime(2026, 2, 10, 10, 15, 0, 0)

    result = script.round_up_to_next_minute(value)

    assert result == value


def test_rounds_when_seconds_present() -> None:
    value = dt.datetime(2026, 2, 10, 10, 15, 1, 0)

    result = script.round_up_to_next_minute(value)

    assert result == dt.datetime(2026, 2, 10, 10, 16, 0, 0)


def test_rounds_when_only_microseconds_present() -> None:
    value = dt.datetime(2026, 2, 10, 10, 15, 0, 1)

    result = script.round_up_to_next_minute(value)

    assert result == dt.datetime(2026, 2, 10, 10, 16, 0, 0)


def test_rounds_across_hour_boundary() -> None:
    value = dt.datetime(2026, 2, 10, 10, 59, 59, 0)

    result = script.round_up_to_next_minute(value)

    assert result == dt.datetime(2026, 2, 10, 11, 0, 0, 0)


def test_rounds_across_day_boundary() -> None:
    value = dt.datetime(2026, 2, 28, 23, 59, 59, 0)

    result = script.round_up_to_next_minute(value)

    assert result == dt.datetime(2026, 3, 1, 0, 0, 0, 0)


def test_preserves_timezone_for_aware_datetimes() -> None:
    berlin_tz = tz.gettz("Europe/Berlin")
    value = dt.datetime(2026, 2, 10, 10, 15, 1, 0, tzinfo=berlin_tz)

    result = script.round_up_to_next_minute(value)

    assert result.tzinfo == value.tzinfo
    assert result.isoformat() == "2026-02-10T10:16:00+01:00"


def test_maps_known_german_spellings_to_canonical_names() -> None:
    assert script.get_prayer_canonical_name("Zuhr") == "dhuhr"
    assert script.get_prayer_canonical_name("assr") == "asr"
    assert script.get_prayer_canonical_name("ishaa") == "isha"


def test_keeps_unmapped_names_unchanged() -> None:
    assert script.get_prayer_canonical_name("Fajr") == "fajr"
    assert script.get_prayer_canonical_name("maghrib") == "maghrib"


class FrozenDateTime:
    frozen_now: dt.datetime

    @classmethod
    def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:
        if tz is None:
            return cls.frozen_now

        return cls.frozen_now.astimezone(tz)


def _fake_dt_module() -> types.SimpleNamespace:
    return types.SimpleNamespace(datetime=FrozenDateTime, timedelta=dt.timedelta)


@pytest.mark.parametrize(
    ("frozen_now", "timezone", "expected_start", "expected_end"),
    [
        (
            dt.datetime(2026, 3, 14, 12, 45, tzinfo=dt.timezone.utc),
            "Europe/Berlin",
            "2026-03-01T00:00:00+01:00",
            "2026-04-01T00:00:00+02:00",
        ),
        (
            dt.datetime(2026, 12, 15, 10, 0, tzinfo=dt.timezone.utc),
            "UTC",
            "2026-12-01T00:00:00+00:00",
            "2027-01-01T00:00:00+00:00",
        ),
    ],
)
def test_get_current_month_bounds_expected_edges(
    frozen_now: dt.datetime,
    timezone: str,
    expected_start: str,
    expected_end: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FrozenDateTime.frozen_now = frozen_now
    monkeypatch.setattr(script, "dt", _fake_dt_module())

    start, end = script.get_current_month_bounds(timezone)

    assert start.isoformat() == expected_start
    assert end.isoformat() == expected_end


def test_now_is_within_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    FrozenDateTime.frozen_now = dt.datetime(2026, 2, 23, 9, 30, tzinfo=dt.timezone.utc)
    berlin_tz = tz.gettz("Europe/Berlin")
    monkeypatch.setattr(script, "dt", _fake_dt_module())

    start, end = script.get_current_month_bounds("Europe/Berlin")
    now_local = FrozenDateTime.frozen_now.astimezone(berlin_tz)

    assert start <= now_local
    assert now_local < end


def test_same_instant_can_produce_different_months_across_timezones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FrozenDateTime.frozen_now = dt.datetime(2026, 3, 1, 0, 30, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(script, "dt", _fake_dt_module())

    berlin_start, _ = script.get_current_month_bounds("Europe/Berlin")
    honolulu_start, _ = script.get_current_month_bounds("Pacific/Honolulu")

    assert berlin_start.date().isoformat() == "2026-03-01"
    assert honolulu_start.date().isoformat() == "2026-02-01"
