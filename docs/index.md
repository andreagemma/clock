# GA Clock Documentation

GA Clock is a dependency-free Python package that provides a controllable
datetime source and an internal-time scheduler.

Use GA Clock when production code should run against realtime, but tests and
simulations need deterministic time.

## Installation

```bash
pip install ga-clock
```

For development:

```bash
python -m pip install -e ".[dev]"
```

GA Clock supports Python 3.10 and newer. The distribution name is `ga-clock` and the
import package is `ga_clock`.

## Main Concepts

GA Clock separates wall-clock time from internal time.

- In `realtime` mode, internal time follows real time.
- In `wrap` mode, internal time follows real time multiplied by a factor.
- In `fixed` mode, internal time advances by the same delta on every `step()`.
- In `scheduled` mode, internal time jumps to the next scheduled job on `step()`.
- In `manual` mode, internal time advances by the amount passed to `step()`.

All scheduler operations use internal time.

## API Overview

```python
from ga_clock import Clock

clock = Clock.manual()

clock.now()
clock.elapsed()
clock.elapsed_seconds()
clock.elapsed_minutes()
clock.elapsed_hours()
clock.elapsed_days()
clock.elapsed_months()
clock.elapsed_years()
clock.elapsed_values()
```

## Factory Constructors

```python
Clock.realtime()
Clock.wrap(factor=10)
Clock.fixed(step=timedelta(seconds=1))
Clock.scheduled()
Clock.manual()
```

Each constructor accepts `start_at`. `start_at` may be a `datetime` or an ISO
datetime string.

```python
clock = Clock.manual(start_at="2026-01-01T09:00:00")
```

## Scheduler

The scheduler syntax is fluent and inspired by the `schedule` package. Configuration
operations return new job objects rather than mutating earlier builder values.

```python
clock.every().second.do(job)
clock.every(5).minutes.do(job)
clock.every().hour.at(":15").do(job)
clock.every().day.at("09:30").do(job)
clock.every().monday.at("10:00").do(job)
clock.every().month.at("08:00").do(job)
clock.every().year.at("00:00").do(job)
```

Run jobs due at the current internal time:

```python
clock.run_pending()
```

Run all jobs once:

```python
clock.run_all()
```

Inspect the next scheduled run:

```python
clock.next_run()
```

Cancel and clear jobs:

```python
job = clock.every().minute.do(sync).tag("sync")

clock.cancel(job)
clock.clear("sync")
clock.clear()
```

## Scheduled Mode

Scheduled mode skips idle time.

```python
from datetime import datetime

from ga_clock import Clock

events = []

clock = Clock.scheduled(start_at=datetime(2026, 1, 1, 9, 0, 0))
clock.every(30).minutes.do(lambda: events.append(clock.now()))

clock.step()
clock.step()

assert events == [
    datetime(2026, 1, 1, 9, 30, 0),
    datetime(2026, 1, 1, 10, 0, 0),
]
```

## Elapsed Months and Years

Elapsed months and years are duration approximations. GA Clock uses the average
Gregorian year length, 365.2425 days, and defines one month as one twelfth of
that year.
