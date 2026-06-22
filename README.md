# GA Clock

GA Clock is a small Python library for building applications and tests around a
controllable clock. It can behave like real time, accelerated real time, fixed
ticks, scheduled jumps, or fully manual simulated time.

The package is designed for schedulers, simulations, deterministic tests, and
systems where "now" should be a dependency you can control.

## Features

- Five modes: `realtime`, `wrap`, `fixed`, `scheduled`, and `manual`
- Start at the current datetime or at a precise datetime
- Read the current internal datetime
- Read elapsed time as a `timedelta`, seconds, minutes, hours, days, months, or years
- Schedule jobs with a fluent syntax inspired by the `schedule` package
- Run scheduled jobs against internal clock time, not wall-clock time
- Use method chaining where it makes workflows concise
- No runtime dependencies

## Installation

From PyPI, once published:

```bash
pip install ga-clock
```

Install the latest wheel built from `main` directly from GitHub:

```bash
pip install https://github.com/andreagemma/ga-clock/releases/download/wheel-latest/ga_clock-0.1.0-py3-none-any.whl
```

Wheel filenames must include the distribution version and compatibility tags;
`ga_clock.whl` alone is not a valid wheel filename accepted by `pip`.

For local development from this repository:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Quick Start

```python
from datetime import datetime, timedelta

from ga_clock import Clock

clock = Clock.manual(start_at=datetime(2026, 1, 1, 9, 0, 0))

clock.step(hours=2)

print(clock.now())
print(clock.elapsed())
print(clock.elapsed_hours())
```

## GA Clock Modes

### Realtime

Realtime mode advances at normal wall-clock speed.

```python
clock = Clock.realtime()
print(clock.now())
```

### Wrap

Wrap mode advances at `factor * real_time`. A factor of `60` means one real
second advances the internal clock by one simulated minute.

```python
clock = Clock.wrap(factor=60)
```

### Fixed

Fixed mode advances by a configured fixed delta every time `step()` is called.

```python
clock = Clock.fixed(step=timedelta(minutes=15))

clock.step().step()

print(clock.elapsed_minutes())  # 30.0
```

### Scheduled

Scheduled mode advances directly to the next scheduled event when `step()` is
called. This is useful for simulations where idle time should be skipped.

```python
events = []

clock = Clock.scheduled(start_at=datetime(2026, 1, 1, 9, 0, 0))
clock.every().hour.do(lambda: events.append(clock.now()))

clock.step()

print(events)       # [datetime(2026, 1, 1, 10, 0)]
print(clock.now())  # 2026-01-01 10:00:00
```

### Manual

Manual mode advances by the amount passed to `step()`.

```python
clock = Clock.manual()

clock.step(minutes=5).step(seconds=30)
```

## Scheduling

The scheduler uses the clock's internal time. The syntax is intentionally close
to the popular `schedule` package:

```python
clock = Clock.manual(start_at=datetime(2026, 1, 1, 8, 0, 0))

clock.every(10).seconds.do(send_heartbeat)
clock.every().day.at("09:30").do(open_market)
clock.every().monday.at("10:00").do(weekly_report).tag("reports")

clock.step(minutes=10)
clock.run_pending()
```

Useful scheduler methods:

```python
clock.every(5).minutes.do(job)
clock.run_pending()
clock.run_all()
clock.next_run()
clock.clear()
clock.clear("reports")
```

Jobs can be tagged and cancelled:

```python
job = clock.every().hour.do(sync).tag("sync")

clock.cancel(job)
clock.clear("sync")
```

Returning `CancelJob` from a job removes it after it runs:

```python
from ga_clock import CancelJob

def run_once():
    print("done")
    return CancelJob

clock.every().second.do(run_once)
```

## Elapsed Time

```python
clock.elapsed()          # datetime.timedelta
clock.elapsed_seconds()  # float
clock.elapsed_minutes()  # float
clock.elapsed_hours()    # float
clock.elapsed_days()     # float
clock.elapsed_months()   # float, average Gregorian month
clock.elapsed_years()    # float, average Gregorian year
clock.elapsed_values()   # immutable dataclass with all values
```

Months and years are reported as duration approximations using the average
Gregorian year length of 365.2425 days.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
python -m compileall src tests
pytest
python -m build
```

## Releases

Releases are created by the `Release` GitHub Actions workflow.

The `Build Wheel` workflow also maintains the rolling `wheel-latest`
prerelease and prints its direct `pip install` URL in the workflow summary.

Create a release from a tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Or run the workflow manually from GitHub Actions. If no version is provided,
the workflow uses the version declared in `pyproject.toml` and checks that it
matches `ga_clock.__version__`.

### Publishing to PyPI

The `Publish to PyPI` workflow runs automatically after a successful `Release`
workflow, and it can also be started manually. It uses PyPI Trusted Publishing,
so no API token or password is stored in GitHub.

Configure a Trusted Publisher for the project on PyPI with these values:

- PyPI project name: `ga-clock`
- GitHub owner: `andreagemma`
- GitHub repository: `ga-clock`
- Workflow filename: `pypi.yml`
- GitHub environment: `pypi`

Before publishing, update both `project.version` in `pyproject.toml` and
`ga_clock.__version__` in `src/ga_clock/_version.py` to the same new version.

## Python Support

GA Clock supports Python 3.9 and newer.
