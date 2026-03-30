import logging
import os

os.environ.setdefault("LATITUDE", "50.0")
os.environ.setdefault("LONGITUDE", "6.0")
os.environ.setdefault("CALENDAR_ID", "calendar-de")
os.environ.setdefault("TIMEZONE", "Europe/Berlin")
os.environ.setdefault("LATITUDE_MOROCCO", "33.6")
os.environ.setdefault("LONGITUDE_MOROCCO", "-7.6")
os.environ.setdefault("CALENDAR_ID_MOROCCO", "calendar-ma")
os.environ.setdefault("TIMEZONE_MOROCCO", "Africa/Casablanca")

from src import script  # noqa: E402


class FakeService:
    def __init__(self) -> None:
        self.insert_calls = 0

    def events(self) -> "FakeService":
        return self

    def insert(self, calendarId: str, body: dict) -> tuple[str, str, dict]:
        self.insert_calls += 1
        return ("insert", calendarId, body)


def _de_sample_day() -> dict[str, str]:
    return {
        "fajr": "2026-02-01T05:10:00+01:00",
        "zuhr": "2026-02-01T12:30:00+01:00",
        "assr": "2026-02-01T15:45:00+01:00",
        "maghrib": "2026-02-01T18:10:00+01:00",
        "ishaa": "2026-02-01T19:40:00+01:00",
    }


def _ma_sample_day() -> dict:
    return {
        "timings": {
            "Fajr": "2026-02-01T05:30:00+01:00",
            "Dhuhr": "2026-02-01T12:40:00+01:00",
            "Asr": "2026-02-01T15:55:00+01:00",
            "Maghrib": "2026-02-01T18:20:00+01:00",
            "Isha": "2026-02-01T19:45:00+01:00",
            "Sunrise": "2026-02-01T07:10:00+01:00",
        }
    }


def test_parse_args_defaults_to_all_without_dry_run() -> None:
    args = script.parse_args([])

    assert args.country == "all"
    assert args.dry_run is False


def test_parse_args_accepts_country_and_dry_run() -> None:
    args = script.parse_args(["--country", "de", "--dry-run"])

    assert args.country == "de"
    assert args.dry_run is True


def test_main_routes_only_de_when_requested(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []
    service = object()

    monkeypatch.setattr(script, "get_calendar_service", lambda: service)
    monkeypatch.setattr(script, "sync_de", lambda svc, dry: calls.append(("de", dry)))
    monkeypatch.setattr(script, "sync_ma", lambda svc, dry: calls.append(("ma", dry)))

    script.main(["--country", "de", "--dry-run"])

    assert calls == [("de", True)]


def test_main_routes_only_ma_when_requested(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []
    service = object()

    monkeypatch.setattr(script, "get_calendar_service", lambda: service)
    monkeypatch.setattr(script, "sync_de", lambda svc, dry: calls.append(("de", dry)))
    monkeypatch.setattr(script, "sync_ma", lambda svc, dry: calls.append(("ma", dry)))

    script.main(["--country", "ma"])

    assert calls == [("ma", False)]


def test_main_routes_both_countries_by_default(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []
    service = object()

    monkeypatch.setattr(script, "get_calendar_service", lambda: service)
    monkeypatch.setattr(script, "sync_de", lambda svc, dry: calls.append(("de", dry)))
    monkeypatch.setattr(script, "sync_ma", lambda svc, dry: calls.append(("ma", dry)))

    script.main([])

    assert calls == [("de", False), ("ma", False)]


def test_main_forces_info_level_for_dry_run(monkeypatch) -> None:
    original_level = script.logger.level
    service = object()

    monkeypatch.setattr(script, "get_calendar_service", lambda: service)
    monkeypatch.setattr(script, "sync_de", lambda svc, dry: None)
    monkeypatch.setattr(script, "sync_ma", lambda svc, dry: None)

    try:
        script.logger.setLevel(logging.ERROR)

        script.main(["--country", "de", "--dry-run"])

        assert script.logger.level == logging.INFO
    finally:
        script.logger.setLevel(original_level)


def test_main_keeps_log_level_for_non_dry_run(monkeypatch) -> None:
    original_level = script.logger.level
    service = object()

    monkeypatch.setattr(script, "get_calendar_service", lambda: service)
    monkeypatch.setattr(script, "sync_de", lambda svc, dry: None)
    monkeypatch.setattr(script, "sync_ma", lambda svc, dry: None)

    try:
        script.logger.setLevel(logging.ERROR)

        script.main(["--country", "de"])

        assert script.logger.level == logging.ERROR
    finally:
        script.logger.setLevel(original_level)


def test_sync_de_dry_run_reads_but_does_not_write(monkeypatch) -> None:
    calls = {"fetch": 0, "list": 0, "delete": 0, "batch": 0}
    service = FakeService()

    def fetch_prayer_times_de() -> list[dict[str, str]]:
        calls["fetch"] += 1
        return [_de_sample_day()]

    def list_current_month_event_ids(
        calendar_id: str, timezone: str, svc: object
    ) -> list[str]:
        calls["list"] += 1
        return ["existing-1", "existing-2"]

    monkeypatch.setattr(script, "fetch_prayer_times_de", fetch_prayer_times_de)
    monkeypatch.setattr(
        script, "list_current_month_event_ids", list_current_month_event_ids
    )
    monkeypatch.setattr(
        script,
        "delete_current_month_events",
        lambda calendar_id, timezone, svc: calls.__setitem__(
            "delete", calls["delete"] + 1
        ),
    )
    monkeypatch.setattr(
        script,
        "run_in_batches",
        lambda svc, reqs, tag: calls.__setitem__("batch", calls["batch"] + 1),
    )

    script.sync_de(service, dry_run=True)

    assert calls == {"fetch": 1, "list": 1, "delete": 0, "batch": 0}
    assert service.insert_calls == 0


def test_sync_ma_dry_run_reads_but_does_not_write(monkeypatch) -> None:
    calls = {"fetch": 0, "list": 0, "delete": 0, "batch": 0}
    service = FakeService()

    def fetch_prayer_times_ma() -> list[dict]:
        calls["fetch"] += 1
        return [_ma_sample_day()]

    def list_current_month_event_ids(
        calendar_id: str, timezone: str, svc: object
    ) -> list[str]:
        calls["list"] += 1
        return ["existing-1"]

    monkeypatch.setattr(script, "fetch_prayer_times_ma", fetch_prayer_times_ma)
    monkeypatch.setattr(
        script, "list_current_month_event_ids", list_current_month_event_ids
    )
    monkeypatch.setattr(
        script,
        "delete_current_month_events",
        lambda calendar_id, timezone, svc: calls.__setitem__(
            "delete", calls["delete"] + 1
        ),
    )
    monkeypatch.setattr(
        script,
        "run_in_batches",
        lambda svc, reqs, tag: calls.__setitem__("batch", calls["batch"] + 1),
    )

    script.sync_ma(service, dry_run=True)

    assert calls == {"fetch": 1, "list": 1, "delete": 0, "batch": 0}
    assert service.insert_calls == 0


def test_sync_de_non_dry_run_writes(monkeypatch) -> None:
    calls = {"delete": 0, "batch": 0}
    service = FakeService()

    monkeypatch.setattr(script, "fetch_prayer_times_de", lambda: [_de_sample_day()])
    monkeypatch.setattr(
        script,
        "list_current_month_event_ids",
        lambda calendar_id, timezone, svc: ["e1"],
    )
    monkeypatch.setattr(
        script,
        "delete_current_month_events",
        lambda calendar_id, timezone, svc: calls.__setitem__(
            "delete", calls["delete"] + 1
        ),
    )

    def run_in_batches(svc: object, reqs: list[object], tag: str) -> None:
        assert tag == "create-events-de"
        calls["batch"] += 1
        assert len(reqs) == 5

    monkeypatch.setattr(script, "run_in_batches", run_in_batches)

    script.sync_de(service, dry_run=False)

    assert calls == {"delete": 1, "batch": 1}
    assert service.insert_calls == 5
