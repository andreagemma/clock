# API Reference

## `Clock`

```python
Clock(
    mode="realtime",
    start_at=None,
    factor=1.0,
    step=timedelta(seconds=1),
    tz=None,
    auto_run_due=True,
)
```

Creates a controllable clock.

### Constructors

- `Clock.realtime(start_at=None, tz=None)`
- `Clock.wrap(factor=1.0, start_at=None, tz=None)`
- `Clock.fixed(step=timedelta(seconds=1), start_at=None, tz=None)`
- `Clock.scheduled(start_at=None, tz=None)`
- `Clock.manual(start_at=None, tz=None)`

### Time Methods

- `now() -> datetime`
- `elapsed() -> timedelta`
- `elapsed_seconds() -> float`
- `elapsed_minutes() -> float`
- `elapsed_hours() -> float`
- `elapsed_days() -> float`
- `elapsed_months() -> float`
- `elapsed_years() -> float`
- `elapsed_values() -> Elapsed`

### Step

```python
clock.step()
clock.step(timedelta(minutes=5))
clock.step(minutes=5, seconds=30)
```

Mode behavior:

- `realtime`: `step()` runs pending jobs but does not move time directly.
- `wrap`: `step()` runs pending jobs but does not move time directly.
- `fixed`: `step()` advances by the configured fixed delta.
- `scheduled`: `step()` jumps to the next scheduled job.
- `manual`: `step(...)` advances by the provided amount.

### Scheduler Methods

- `every(interval=1) -> Job`
- `run_pending() -> list`
- `run_all() -> list`
- `next_run() -> datetime | None`
- `jobs(tag=None) -> list[Job]`
- `cancel(job) -> Clock`
- `clear(*tags) -> Clock`

## `Job`

Jobs are created with `Clock.every()`.

```python
clock.every(10).seconds.do(job)
clock.every().day.at("09:00").do(job).tag("daily")
```

### Units

- `second` / `seconds`
- `minute` / `minutes`
- `hour` / `hours`
- `day` / `days`
- `week` / `weeks`
- `month` / `months`
- `year` / `years`
- `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`

### `at()` Formats

- Minute jobs: `":SS"`
- Hourly jobs: `":MM"` or `":MM:SS"`
- Daily and larger jobs: `"HH:MM"` or `"HH:MM:SS"`

### Tags

```python
job = clock.every().minute.do(sync).tag("io", "sync")

clock.jobs("sync")
clock.clear("sync")
```

### Cancelling from a Job

```python
from ga_clock import CancelJob

def run_once():
    return CancelJob

clock.every().second.do(run_once)
```
