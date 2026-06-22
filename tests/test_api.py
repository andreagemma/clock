from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from ga_clock import CancelJob, Clock, ClockError, GAClockError, GAClockWarning


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_manual_clock_advances_and_reports_elapsed_units() -> None:
    clock = Clock.manual(start_at=datetime(2026, 1, 1, 9, 0, 0))

    clock.step(minutes=5).step(timedelta(seconds=30))

    assert clock.now() == datetime(2026, 1, 1, 9, 5, 30)
    assert clock.elapsed() == timedelta(minutes=5, seconds=30)
    assert clock.elapsed_seconds() == 330
    assert clock.elapsed_minutes() == 5.5
    assert clock.elapsed_hours() == pytest.approx(5.5 / 60)

    values = clock.elapsed_values()
    assert values.delta == clock.elapsed()
    assert values.seconds == 330
    assert values.minutes == 5.5


def test_elapsed_calendar_units_use_average_gregorian_year() -> None:
    clock = Clock.manual(start_at=datetime(2026, 1, 1))

    clock.step(days=365.2425)

    assert clock.elapsed_days() == pytest.approx(365.2425)
    assert clock.elapsed_months() == pytest.approx(12)
    assert clock.elapsed_years() == pytest.approx(1)


def test_fixed_clock_advances_by_configured_step() -> None:
    clock = Clock.fixed(step=timedelta(minutes=15), start_at=datetime(2026, 1, 1))

    assert clock.step().step() is clock
    assert clock.now() == datetime(2026, 1, 1, 0, 30)


def test_realtime_and_wrap_clocks_use_monotonic_time() -> None:
    fake = FakeMonotonic()
    realtime = Clock(
        mode="realtime",
        start_at=datetime(2026, 1, 1, 12, 0),
        monotonic=fake,
    )
    wrapped = Clock(
        mode="wrap",
        factor=60,
        start_at=datetime(2026, 1, 1, 12, 0),
        monotonic=fake,
    )

    fake.advance(2)

    assert realtime.now() == datetime(2026, 1, 1, 12, 0, 2)
    assert wrapped.now() == datetime(2026, 1, 1, 12, 2)


def test_start_at_accepts_iso_datetime_and_timezone() -> None:
    clock = Clock.manual(start_at="2026-01-01T09:00:00", tz=timezone.utc)

    assert clock.start_at == datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    assert clock.mode == "manual"


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: Clock(mode="invalid"), "mode must be one of"),
        (lambda: Clock.wrap(factor=0), "factor must be greater than zero"),
        (lambda: Clock.fixed(step="bad"), "Expected a timedelta"),
    ],
)
def test_invalid_initialization_is_rejected(factory: object, message: str) -> None:
    with pytest.raises(ClockError, match=message):
        factory()  # type: ignore[operator]


def test_mode_specific_step_validation() -> None:
    with pytest.raises(ClockError, match="non-zero"):
        Clock.manual(start_at=datetime(2026, 1, 1)).step()
    with pytest.raises(ClockError, match="configured step"):
        Clock.fixed(start_at=datetime(2026, 1, 1)).step(seconds=1)
    with pytest.raises(ClockError, match="next job"):
        Clock.scheduled(start_at=datetime(2026, 1, 1)).step(seconds=1)
    with pytest.raises(ClockError, match="real time"):
        Clock.realtime(start_at=datetime(2026, 1, 1)).step(seconds=1)


def test_job_configuration_is_immutable() -> None:
    clock = Clock.manual(start_at=datetime(2026, 1, 1, 9, 0))
    base = clock.every(5)
    by_minutes = base.minutes
    timed = by_minutes.at(":30")
    scheduled = timed.do(lambda: None)
    tagged = scheduled.tag("heartbeat")

    assert base.unit is None
    assert by_minutes.unit == "minutes"
    assert by_minutes.at_time is None
    assert timed.at_time is not None
    assert scheduled.tags == frozenset()
    assert tagged.tags == frozenset({"heartbeat"})
    assert clock.jobs() == [tagged]

    with pytest.raises(FrozenInstanceError):
        base.unit = "hours"

    with pytest.raises(ClockError, match="cannot be reconfigured"):
        _ = scheduled.hours


def test_stale_job_handle_can_cancel_reconfigured_job() -> None:
    clock = Clock.manual(start_at=datetime(2026, 1, 1))
    scheduled = clock.every().minute.do(lambda: None)
    tagged = scheduled.tag("tagged")

    assert clock.jobs() == [tagged]
    scheduled.cancel()
    assert clock.jobs() == []


def test_pending_jobs_use_internal_time() -> None:
    calls: list[datetime] = []
    clock = Clock.manual(start_at=datetime(2026, 1, 1, 9, 0))
    clock.every(10).minutes.do(lambda: calls.append(clock.now()))

    clock.step(minutes=9)
    assert calls == []

    clock.step(minutes=1)
    assert calls == [datetime(2026, 1, 1, 9, 10)]


def test_scheduled_clock_jumps_to_all_jobs_at_next_time() -> None:
    calls: list[str] = []
    clock = Clock.scheduled(start_at=datetime(2026, 1, 1, 9, 0))
    clock.every().hour.do(lambda: calls.append("first"))
    clock.every().hour.do(lambda: calls.append("second"))

    clock.step()

    assert clock.now() == datetime(2026, 1, 1, 10, 0)
    assert calls == ["first", "second"]


def test_scheduled_clock_without_jobs_is_a_noop() -> None:
    start = datetime(2026, 1, 1)
    clock = Clock.scheduled(start_at=start)

    assert clock.step().now() == start
    assert clock.next_run() is None


def test_daily_weekly_monthly_and_yearly_schedules() -> None:
    daily = Clock.manual(start_at=datetime(2026, 1, 1, 8, 0))
    daily.every().day.at("09:30").do(lambda: None)
    assert daily.next_run() == datetime(2026, 1, 1, 9, 30)

    weekly = Clock.manual(start_at=datetime(2026, 1, 1, 8, 0))
    weekly.every().monday.at("10:00").do(lambda: None)
    assert weekly.next_run() == datetime(2026, 1, 5, 10, 0)

    monthly = Clock.manual(start_at=datetime(2026, 1, 31, 9, 0))
    monthly.every().month.do(lambda: None)
    assert monthly.next_run() == datetime(2026, 2, 28, 9, 0)

    yearly = Clock.manual(start_at=datetime(2024, 2, 29, 9, 0))
    yearly.every().year.do(lambda: None)
    assert yearly.next_run() == datetime(2025, 2, 28, 9, 0)


def test_subdaily_at_formats() -> None:
    minute_clock = Clock.manual(start_at=datetime(2026, 1, 1, 8, 0, 10))
    minute_clock.every().minute.at(":15").do(lambda: None)
    assert minute_clock.next_run() == datetime(2026, 1, 1, 8, 0, 15)

    hour_clock = Clock.manual(start_at=datetime(2026, 1, 1, 8, 10))
    hour_clock.every().hour.at(":30:15").do(lambda: None)
    assert hour_clock.next_run() == datetime(2026, 1, 1, 8, 30, 15)


@pytest.mark.parametrize(
    "configure",
    [
        lambda clock: clock.every().second.at(":10"),
        lambda clock: clock.every().minute.at("10"),
        lambda clock: clock.every().hour.at("10:00"),
        lambda clock: clock.every().day.at("25:00"),
        lambda clock: clock.every().day.at("bad:00"),
    ],
)
def test_invalid_at_formats_are_rejected(configure: object) -> None:
    clock = Clock.manual(start_at=datetime(2026, 1, 1))
    with pytest.raises(ClockError):
        configure(clock)  # type: ignore[operator]


def test_run_all_returns_results_and_reschedules() -> None:
    clock = Clock.manual(start_at=datetime(2026, 1, 1))
    clock.every().hour.do(lambda: "hourly")

    assert clock.run_all() == ["hourly"]
    assert clock.next_run() == datetime(2026, 1, 1, 1, 0)


def test_tags_clear_cancel_and_cancel_job_sentinel() -> None:
    calls: list[str] = []
    clock = Clock.manual(start_at=datetime(2026, 1, 1))

    def once() -> object:
        calls.append("once")
        return CancelJob

    clock.every().second.do(once).tag("temporary")
    permanent = clock.every().second.do(lambda: calls.append("keep")).tag("permanent")

    clock.step(seconds=1)
    assert calls == ["once", "keep"]
    assert clock.jobs() == [permanent]
    assert clock.jobs("permanent") == [permanent]

    clock.clear("permanent")
    assert clock.jobs() == []
    assert clock.cancel(permanent).clear() is clock


def test_job_interval_must_be_positive() -> None:
    clock = Clock.manual(start_at=datetime(2026, 1, 1))
    with pytest.raises(ClockError, match="at least 1"):
        clock.every(0)


def test_exception_hierarchy_is_public() -> None:
    assert issubclass(ClockError, GAClockError)
    assert issubclass(ClockError, ValueError)
    assert issubclass(GAClockWarning, UserWarning)
