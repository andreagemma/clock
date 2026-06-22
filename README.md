# GA Clock

[![CI](https://github.com/andreagemma/ga-clock/actions/workflows/ci.yml/badge.svg)](https://github.com/andreagemma/ga-clock/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ga-clock.svg)](https://pypi.org/project/ga-clock/)
[![Python](https://img.shields.io/pypi/pyversions/ga-clock.svg)](https://pypi.org/project/ga-clock/)

GA Clock provides a controllable datetime source and an internal-time scheduler for
applications, simulations, and deterministic tests. A clock can follow wall time,
accelerate it, advance in fixed or manual steps, or jump directly between scheduled
events. The scheduler always uses the selected clock's internal time.

## Installation

The PyPI distribution is named `ga-clock`; the import package is named `ga_clock`.

```bash
python -m pip install ga-clock
```

GA Clock has no runtime dependencies. Development and test tools are available as
extras:

```bash
python -m pip install -e ".[test]"
python -m pip install -e ".[dev]"
```

## Quick Start

```python
from datetime import datetime

from ga_clock import Clock

clock = Clock.manual(start_at=datetime(2026, 1, 1, 9, 0))
clock.step(hours=2)

assert clock.now() == datetime(2026, 1, 1, 11, 0)
assert clock.elapsed_hours() == 2
```

When `start_at` is omitted, the clock starts at the current datetime. It also accepts
an ISO datetime string and an optional `tzinfo` object.

## Clock Modes

| Mode | Internal-time behavior | `step()` behavior |
| --- | --- | --- |
| `realtime` | Advances at wall-clock speed | Runs due jobs without moving time directly |
| `wrap` | Advances at `factor * wall time` | Runs due jobs without moving time directly |
| `fixed` | Changes only when stepped | Advances by the configured fixed duration |
| `scheduled` | Changes only when stepped | Jumps to the next scheduled event |
| `manual` | Changes only when stepped | Advances by the supplied duration |

### Realtime and Wrap

```python
from ga_clock import Clock

realtime = Clock.realtime()
accelerated = Clock.wrap(factor=60)
```

A wrap factor of `60` advances internal time by one minute for every elapsed wall-time
second. Factors must be greater than zero.

### Fixed and Manual

```python
from datetime import timedelta

from ga_clock import Clock

fixed = Clock.fixed(step=timedelta(minutes=15))
fixed.step().step()
assert fixed.elapsed_minutes() == 30

manual = Clock.manual()
manual.step(minutes=5).step(seconds=30)
assert manual.elapsed_seconds() == 330
```

### Scheduled

```python
from datetime import datetime

from ga_clock import Clock

events: list[datetime] = []
clock = Clock.scheduled(start_at=datetime(2026, 1, 1, 9, 0))
clock.every().hour.do(lambda: events.append(clock.now()))

clock.step()

assert events == [datetime(2026, 1, 1, 10, 0)]
```

Calling `step()` with no jobs scheduled is a no-op.

## Scheduling

The fluent API is inspired by `schedule`, but all configuration operations return new
objects instead of mutating earlier builder values.

```python
from datetime import datetime

from ga_clock import Clock

calls: list[str] = []
clock = Clock.manual(start_at=datetime(2026, 1, 1, 8, 0))

heartbeat = clock.every(10).seconds.do(lambda: calls.append("heartbeat"))
report = clock.every().monday.at("10:00").do(
    lambda: calls.append("report")
).tag("reports")

clock.step(seconds=10)
assert calls == ["heartbeat"]

clock.cancel(heartbeat)
clock.clear("reports")
assert clock.jobs() == []
```

Supported units are seconds, minutes, hours, days, weeks, months, and years. Weekday
properties from `monday` through `sunday` are also available. `at()` accepts:

- `:SS` for minute jobs;
- `:MM` or `:MM:SS` for hourly jobs;
- `HH:MM` or `HH:MM:SS` for daily and larger jobs.

Returning `CancelJob` removes a job immediately after it runs:

```python
from ga_clock import CancelJob


def run_once() -> object:
    return CancelJob
```

## Elapsed Time

```python
clock.elapsed()          # datetime.timedelta
clock.elapsed_seconds()  # float
clock.elapsed_minutes()  # float
clock.elapsed_hours()    # float
clock.elapsed_days()     # float
clock.elapsed_months()   # float
clock.elapsed_years()    # float
clock.elapsed_values()   # immutable Elapsed dataclass
```

Months and years are duration approximations based on the average Gregorian year of
365.2425 days; they are not calendar-boundary counts.

## Errors

Invalid modes, factors, durations, schedule formats, and mode-specific operations raise
`ClockError`. It derives from both `GAClockError` and `ValueError`. Non-fatal package
warnings derive from `GAClockWarning`.

Scheduled job callbacks propagate their exceptions to the caller of `step()`,
`run_pending()`, or `run_all()`; GA Clock does not silently suppress callback failures.

## Security

GA Clock does not deserialize data or load executable content. Scheduled callbacks are
ordinary Python callables and execute with the permissions of the current process. Only
schedule callbacks from trusted application code.

## Development

GA Clock supports Python 3.10 and newer.

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src
python -m pytest --cov=ga_clock --cov-report=term-missing
ruff check .
mypy
python -m pip check
python -m build
python -m twine check dist/*
```

## Releases

`src/ga_clock/_version.py` is the only version source. To publish a release:

1. Update `__version__` in `_version.py` and commit the release changes.
2. Push `main` and wait for CI to pass.
3. Configure the PyPI Trusted Publisher with project `ga-clock`, owner `andreagemma`,
   repository `ga-clock`, workflow `release.yml`, and environment `pypi`.
4. Run the **Create release** GitHub Actions workflow. With no override it creates the
   `v<version>` tag, creates release notes, and explicitly dispatches the build and PyPI
   publication workflow.

PyPI versions are immutable. Increment `_version.py` before publishing different
content.

## License

GA Clock is distributed under the MIT License. See [LICENSE](LICENSE).
