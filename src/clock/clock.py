"""Core clock and scheduler implementation."""

from __future__ import annotations

import time as time_module
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any, Callable, Hashable, Literal, Optional, Union

ClockMode = Literal["realtime", "wrap", "fixed", "scheduled", "manual"]
DeltaLike = Union[timedelta, int, float]
DatetimeLike = Union[datetime, str]
TimeSource = Callable[[], float]

SECONDS_PER_DAY = 86_400
DAYS_PER_GREGORIAN_YEAR = 365.2425
SECONDS_PER_GREGORIAN_YEAR = SECONDS_PER_DAY * DAYS_PER_GREGORIAN_YEAR
SECONDS_PER_GREGORIAN_MONTH = SECONDS_PER_GREGORIAN_YEAR / 12


class ClockError(ValueError):
    """Raised when a clock operation is incompatible with the selected mode."""


class _CancelJob:
    """Sentinel returned by a job to remove itself from the scheduler."""


CancelJob = _CancelJob()


@dataclass(frozen=True)
class Elapsed:
    """Elapsed duration represented with several convenient units."""

    delta: timedelta
    seconds: float
    minutes: float
    hours: float
    days: float
    months: float
    years: float


@dataclass
class Job:
    """A scheduled job created by :meth:`Clock.every`.

    Jobs are usually configured fluently:

    ```python
    clock.every(5).minutes.do(send_heartbeat).tag("heartbeat")
    ```
    """

    scheduler: "_Scheduler"
    interval: int = 1
    unit: Optional[str] = None
    at_time: Optional[time] = None
    start_day: Optional[int] = None
    tags: set[Hashable] = field(default_factory=set)
    job_func: Optional[Callable[..., Any]] = None
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    @property
    def second(self) -> "Job":
        return self.seconds

    @property
    def seconds(self) -> "Job":
        return self._with_unit("seconds")

    @property
    def minute(self) -> "Job":
        return self.minutes

    @property
    def minutes(self) -> "Job":
        return self._with_unit("minutes")

    @property
    def hour(self) -> "Job":
        return self.hours

    @property
    def hours(self) -> "Job":
        return self._with_unit("hours")

    @property
    def day(self) -> "Job":
        return self.days

    @property
    def days(self) -> "Job":
        return self._with_unit("days")

    @property
    def week(self) -> "Job":
        return self.weeks

    @property
    def weeks(self) -> "Job":
        return self._with_unit("weeks")

    @property
    def month(self) -> "Job":
        return self.months

    @property
    def months(self) -> "Job":
        return self._with_unit("months")

    @property
    def year(self) -> "Job":
        return self.years

    @property
    def years(self) -> "Job":
        return self._with_unit("years")

    @property
    def monday(self) -> "Job":
        return self._with_weekday(0)

    @property
    def tuesday(self) -> "Job":
        return self._with_weekday(1)

    @property
    def wednesday(self) -> "Job":
        return self._with_weekday(2)

    @property
    def thursday(self) -> "Job":
        return self._with_weekday(3)

    @property
    def friday(self) -> "Job":
        return self._with_weekday(4)

    @property
    def saturday(self) -> "Job":
        return self._with_weekday(5)

    @property
    def sunday(self) -> "Job":
        return self._with_weekday(6)

    def at(self, value: str) -> "Job":
        """Run at a specific clock time within the selected interval."""

        if self.unit is None:
            raise ClockError("Choose a time unit before calling at().")
        self.at_time = _parse_at_time(value, self.unit)
        return self

    def tag(self, *tags: Hashable) -> "Job":
        """Attach one or more tags to the job."""

        self.tags.update(tags)
        return self

    def do(self, job_func: Callable[..., Any], *args: Any, **kwargs: Any) -> "Job":
        """Register the job function and add the job to the scheduler."""

        if self.unit is None:
            raise ClockError("Choose a time unit before calling do().")
        self.job_func = job_func
        self.args = args
        self.kwargs = kwargs
        self.next_run = self._next_after(self.scheduler.now())
        self.scheduler.add(self)
        return self

    def cancel(self) -> "Job":
        """Remove this job from its scheduler."""

        self.scheduler.cancel(self)
        return self

    def run(self) -> Any:
        """Execute the job function once and schedule the next run."""

        if self.job_func is None:
            raise ClockError("Cannot run a job before do() has been called.")

        result = self.job_func(*self.args, **self.kwargs)
        self.last_run = self.scheduler.now()

        if result is CancelJob:
            self.scheduler.cancel(self)
        else:
            self.next_run = self._next_after(self.last_run)

        return result

    def _with_unit(self, unit: str) -> "Job":
        self.unit = unit
        return self

    def _with_weekday(self, weekday: int) -> "Job":
        self.unit = "weeks"
        self.start_day = weekday
        return self

    def _next_after(self, reference: datetime) -> datetime:
        if self.unit is None:
            raise ClockError("A scheduled job needs a time unit.")

        if self.unit == "seconds":
            return reference + timedelta(seconds=self.interval)
        if self.unit == "minutes":
            return self._next_subdaily_after(reference, "minutes")
        if self.unit == "hours":
            return self._next_subdaily_after(reference, "hours")
        if self.unit == "days":
            return self._next_daily_after(reference)
        if self.unit == "weeks":
            return self._next_weekly_after(reference)
        if self.unit == "months":
            return self._next_calendar_after(reference, months=self.interval)
        if self.unit == "years":
            return self._next_calendar_after(reference, years=self.interval)

        raise ClockError(f"Unsupported time unit: {self.unit!r}")

    def _next_subdaily_after(self, reference: datetime, unit: str) -> datetime:
        if self.at_time is None:
            if unit == "minutes":
                return reference + timedelta(minutes=self.interval)
            return reference + timedelta(hours=self.interval)

        if unit == "minutes":
            candidate = reference.replace(second=self.at_time.second, microsecond=0)
            delta = timedelta(minutes=self.interval)
        else:
            candidate = reference.replace(
                minute=self.at_time.minute,
                second=self.at_time.second,
                microsecond=0,
            )
            delta = timedelta(hours=self.interval)

        while candidate <= reference:
            candidate += delta
        return candidate

    def _next_daily_after(self, reference: datetime) -> datetime:
        if self.at_time is None:
            return reference + timedelta(days=self.interval)

        candidate = datetime.combine(reference.date(), self.at_time, tzinfo=reference.tzinfo)
        while candidate <= reference:
            candidate += timedelta(days=self.interval)
        return candidate

    def _next_weekly_after(self, reference: datetime) -> datetime:
        if self.start_day is None:
            if self.at_time is None:
                return reference + timedelta(weeks=self.interval)
            candidate = datetime.combine(reference.date(), self.at_time, tzinfo=reference.tzinfo)
            while candidate <= reference:
                candidate += timedelta(weeks=self.interval)
            return candidate

        days_ahead = (self.start_day - reference.weekday()) % 7
        candidate_date = reference.date() + timedelta(days=days_ahead)
        candidate_time = self.at_time or reference.time().replace(microsecond=0)
        candidate = datetime.combine(candidate_date, candidate_time, tzinfo=reference.tzinfo)

        while candidate <= reference:
            candidate += timedelta(weeks=self.interval)
        return candidate

    def _next_calendar_after(
        self,
        reference: datetime,
        months: int = 0,
        years: int = 0,
    ) -> datetime:
        candidate = reference
        if months:
            candidate = _add_months(candidate, months)
        if years:
            candidate = _add_months(candidate, years * 12)
        if self.at_time is not None:
            candidate = candidate.replace(
                hour=self.at_time.hour,
                minute=self.at_time.minute,
                second=self.at_time.second,
                microsecond=0,
            )
        return candidate


class Clock:
    """A controllable datetime source with an internal-time scheduler."""

    def __init__(
        self,
        mode: ClockMode = "realtime",
        start_at: Optional[DatetimeLike] = None,
        factor: float = 1.0,
        step: DeltaLike = timedelta(seconds=1),
        tz: Optional[tzinfo] = None,
        monotonic: TimeSource = time_module.monotonic,
        auto_run_due: bool = True,
    ) -> None:
        self._mode = _validate_mode(mode)
        self._factor = _validate_factor(factor)
        self._fixed_step = _coerce_delta(step)
        self._start_at = _coerce_datetime(start_at, tz)
        self._current = self._start_at
        self._monotonic = monotonic
        self._real_start = self._monotonic()
        self._scheduler = _Scheduler(self)
        self.auto_run_due = auto_run_due

    @classmethod
    def realtime(
        cls,
        start_at: Optional[DatetimeLike] = None,
        tz: Optional[tzinfo] = None,
    ) -> "Clock":
        """Create a clock that advances at wall-clock speed."""

        return cls(mode="realtime", start_at=start_at, tz=tz)

    @classmethod
    def wrap(
        cls,
        factor: float = 1.0,
        start_at: Optional[DatetimeLike] = None,
        tz: Optional[tzinfo] = None,
    ) -> "Clock":
        """Create a clock that advances at ``factor * real_time``."""

        return cls(mode="wrap", start_at=start_at, factor=factor, tz=tz)

    @classmethod
    def fixed(
        cls,
        step: DeltaLike = timedelta(seconds=1),
        start_at: Optional[DatetimeLike] = None,
        tz: Optional[tzinfo] = None,
    ) -> "Clock":
        """Create a clock that advances by a fixed delta on every step."""

        return cls(mode="fixed", start_at=start_at, step=step, tz=tz)

    @classmethod
    def scheduled(
        cls,
        start_at: Optional[DatetimeLike] = None,
        tz: Optional[tzinfo] = None,
    ) -> "Clock":
        """Create a clock that jumps to the next scheduled job on step."""

        return cls(mode="scheduled", start_at=start_at, tz=tz)

    @classmethod
    def manual(
        cls,
        start_at: Optional[DatetimeLike] = None,
        tz: Optional[tzinfo] = None,
    ) -> "Clock":
        """Create a clock that advances only by explicit step amounts."""

        return cls(mode="manual", start_at=start_at, tz=tz)

    @property
    def mode(self) -> ClockMode:
        """The active clock mode."""

        return self._mode

    @property
    def start_at(self) -> datetime:
        """The datetime used as the internal clock origin."""

        return self._start_at

    def now(self) -> datetime:
        """Return the current internal datetime."""

        if self._mode in {"realtime", "wrap"}:
            elapsed_seconds = (self._monotonic() - self._real_start) * self._factor
            return self._start_at + timedelta(seconds=elapsed_seconds)
        return self._current

    def elapsed(self) -> timedelta:
        """Return the elapsed internal duration since initialization."""

        return self.now() - self._start_at

    def elapsed_seconds(self) -> float:
        return self.elapsed().total_seconds()

    def elapsed_minutes(self) -> float:
        return self.elapsed_seconds() / 60

    def elapsed_hours(self) -> float:
        return self.elapsed_seconds() / 3_600

    def elapsed_days(self) -> float:
        return self.elapsed_seconds() / SECONDS_PER_DAY

    def elapsed_months(self) -> float:
        return self.elapsed_seconds() / SECONDS_PER_GREGORIAN_MONTH

    def elapsed_years(self) -> float:
        return self.elapsed_seconds() / SECONDS_PER_GREGORIAN_YEAR

    def elapsed_values(self) -> Elapsed:
        """Return elapsed time in all supported units."""

        delta = self.elapsed()
        seconds = delta.total_seconds()
        return Elapsed(
            delta=delta,
            seconds=seconds,
            minutes=seconds / 60,
            hours=seconds / 3_600,
            days=seconds / SECONDS_PER_DAY,
            months=seconds / SECONDS_PER_GREGORIAN_MONTH,
            years=seconds / SECONDS_PER_GREGORIAN_YEAR,
        )

    def step(
        self,
        amount: Optional[DeltaLike] = None,
        *,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        days: float = 0,
        weeks: float = 0,
        run_due: Optional[bool] = None,
    ) -> "Clock":
        """Advance the clock according to its mode and return ``self``.

        Fixed clocks ignore wall-clock time and use the configured fixed step.
        Manual clocks require an explicit amount, either as a positional
        `timedelta`/seconds value or as keyword units. Scheduled clocks jump to
        the next scheduled job. Realtime and wrap clocks only run pending jobs.
        """

        should_run = self.auto_run_due if run_due is None else run_due

        if self._mode == "fixed":
            if amount is not None or any([seconds, minutes, hours, days, weeks]):
                raise ClockError("fixed clocks use their configured step; pass no step amount.")
            self._current += self._fixed_step
        elif self._mode == "manual":
            delta = _coerce_delta(
                amount,
                seconds=seconds,
                minutes=minutes,
                hours=hours,
                days=days,
                weeks=weeks,
            )
            if delta == timedelta(0):
                raise ClockError("manual clocks require a non-zero step amount.")
            self._current += delta
        elif self._mode == "scheduled":
            if amount is not None or any([seconds, minutes, hours, days, weeks]):
                raise ClockError("scheduled clocks advance to the next job; pass no step amount.")
            next_run = self.next_run()
            if next_run is not None:
                self._current = next_run
        elif self._mode in {"realtime", "wrap"}:
            if amount is not None or any([seconds, minutes, hours, days, weeks]):
                message = f"{self._mode} clocks advance from real time; pass no step amount."
                raise ClockError(message)
        else:
            raise ClockError(f"Unsupported mode: {self._mode!r}")

        if should_run:
            self.run_pending()
        return self

    def every(self, interval: int = 1) -> Job:
        """Start building a scheduled job."""

        if interval < 1:
            raise ClockError("Job interval must be at least 1.")
        return Job(scheduler=self._scheduler, interval=interval)

    def run_pending(self) -> list[Any]:
        """Run all jobs due at the current internal time."""

        return self._scheduler.run_pending()

    def run_all(self) -> list[Any]:
        """Run all scheduled jobs once, regardless of their next run time."""

        return self._scheduler.run_all()

    def next_run(self) -> Optional[datetime]:
        """Return the next scheduled internal datetime, if any."""

        return self._scheduler.next_run()

    def jobs(self, tag: Optional[Hashable] = None) -> list[Job]:
        """Return scheduled jobs, optionally filtered by tag."""

        return self._scheduler.jobs(tag)

    def cancel(self, job: Job) -> "Clock":
        """Cancel a scheduled job and return ``self``."""

        self._scheduler.cancel(job)
        return self

    def clear(self, *tags: Hashable) -> "Clock":
        """Clear all jobs, or only jobs matching one of the provided tags."""

        self._scheduler.clear(*tags)
        return self


class _Scheduler:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self._jobs: list[Job] = []

    def now(self) -> datetime:
        return self.clock.now()

    def add(self, job: Job) -> None:
        if job not in self._jobs:
            self._jobs.append(job)
        self._sort()

    def cancel(self, job: Job) -> None:
        if job in self._jobs:
            self._jobs.remove(job)

    def clear(self, *tags: Hashable) -> None:
        if not tags:
            self._jobs.clear()
            return

        tag_set = set(tags)
        self._jobs = [job for job in self._jobs if job.tags.isdisjoint(tag_set)]

    def jobs(self, tag: Optional[Hashable] = None) -> list[Job]:
        if tag is None:
            return list(self._jobs)
        return [job for job in self._jobs if tag in job.tags]

    def next_run(self) -> Optional[datetime]:
        scheduled = [job.next_run for job in self._jobs if job.next_run is not None]
        if not scheduled:
            return None
        return min(scheduled)

    def run_pending(self) -> List[Any]:
        now = self.now()
        due_jobs = [
            job
            for job in sorted(self._jobs, key=lambda item: item.next_run or datetime.max)
            if job.next_run is not None and job.next_run <= now
        ]

        results = []
        for job in due_jobs:
            if job in self._jobs:
                results.append(job.run())
        self._sort()
        return results

    def run_all(self) -> List[Any]:
        results = []
        for job in list(self._jobs):
            if job in self._jobs:
                results.append(job.run())
        self._sort()
        return results

    def _sort(self) -> None:
        self._jobs.sort(key=lambda job: job.next_run or datetime.max)


def _validate_mode(mode: str) -> ClockMode:
    if mode not in {"realtime", "wrap", "fixed", "scheduled", "manual"}:
        raise ClockError(
            "mode must be one of: 'realtime', 'wrap', 'fixed', 'scheduled', 'manual'."
        )
    return mode  # type: ignore[return-value]


def _validate_factor(factor: float) -> float:
    if factor <= 0:
        raise ClockError("factor must be greater than zero.")
    return factor


def _coerce_datetime(value: Optional[DatetimeLike], tz: Optional[tzinfo]) -> datetime:
    if value is None:
        return datetime.now(tz)
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if tz is not None and value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value


def _coerce_delta(
    value: Optional[DeltaLike] = None,
    *,
    seconds: float = 0,
    minutes: float = 0,
    hours: float = 0,
    days: float = 0,
    weeks: float = 0,
) -> timedelta:
    if value is None:
        delta = timedelta(0)
    elif isinstance(value, timedelta):
        delta = value
    elif isinstance(value, (int, float)):
        delta = timedelta(seconds=value)
    else:
        raise ClockError("Expected a timedelta or a numeric seconds value.")

    return delta + timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days, weeks=weeks)


def _parse_at_time(value: str, unit: str) -> time:
    parts = value.split(":")
    if unit == "minutes":
        if len(parts) != 2 or parts[0] != "":
            raise ClockError("Minute jobs use at(':SS').")
        return time(second=_bounded_int(parts[1], 0, 59, "second"))

    if unit == "hours":
        if len(parts) == 2 and parts[0] == "":
            return time(minute=_bounded_int(parts[1], 0, 59, "minute"))
        if len(parts) == 3 and parts[0] == "":
            return time(
                minute=_bounded_int(parts[1], 0, 59, "minute"),
                second=_bounded_int(parts[2], 0, 59, "second"),
            )
        raise ClockError("Hourly jobs use at(':MM') or at(':MM:SS').")

    if unit in {"days", "weeks", "months", "years"}:
        if len(parts) == 2:
            return time(
                hour=_bounded_int(parts[0], 0, 23, "hour"),
                minute=_bounded_int(parts[1], 0, 59, "minute"),
            )
        if len(parts) == 3:
            return time(
                hour=_bounded_int(parts[0], 0, 23, "hour"),
                minute=_bounded_int(parts[1], 0, 59, "minute"),
                second=_bounded_int(parts[2], 0, 59, "second"),
            )
        raise ClockError("Daily and larger jobs use at('HH:MM') or at('HH:MM:SS').")

    raise ClockError(f"at() is not supported for {unit} jobs.")


def _bounded_int(value: str, minimum: int, maximum: int, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ClockError(f"{name} must be an integer.") from exc

    if parsed < minimum or parsed > maximum:
        raise ClockError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return value.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - date(year, month, 1)).days
