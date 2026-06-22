import unittest
from datetime import datetime, timedelta

from ga_clock import CancelJob, Clock, ClockError, __version__


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class ClockTest(unittest.TestCase):
    def test_package_exposes_version(self) -> None:
        self.assertEqual(__version__, "0.1.0")

    def test_manual_clock_advances_by_explicit_amounts(self) -> None:
        clock = Clock.manual(start_at=datetime(2026, 1, 1, 9, 0, 0))

        clock.step(minutes=5).step(timedelta(seconds=30))

        self.assertEqual(clock.now(), datetime(2026, 1, 1, 9, 5, 30))
        self.assertEqual(clock.elapsed(), timedelta(minutes=5, seconds=30))
        self.assertEqual(clock.elapsed_seconds(), 330)

    def test_fixed_clock_advances_by_configured_step(self) -> None:
        clock = Clock.fixed(step=timedelta(minutes=15), start_at=datetime(2026, 1, 1))

        clock.step().step()

        self.assertEqual(clock.now(), datetime(2026, 1, 1, 0, 30, 0))
        self.assertEqual(clock.elapsed_minutes(), 30)

    def test_wrap_clock_uses_factor_times_real_elapsed_time(self) -> None:
        fake = FakeMonotonic()
        clock = Clock(
            mode="wrap",
            factor=60,
            start_at=datetime(2026, 1, 1, 12, 0, 0),
            monotonic=fake,
        )

        fake.advance(2)

        self.assertEqual(clock.now(), datetime(2026, 1, 1, 12, 2, 0))

    def test_run_pending_uses_internal_time(self) -> None:
        calls = []
        clock = Clock.manual(start_at=datetime(2026, 1, 1, 9, 0, 0))
        clock.every(10).minutes.do(lambda: calls.append(clock.now()))

        clock.step(minutes=9)
        self.assertEqual(calls, [])

        clock.step(minutes=1)
        self.assertEqual(calls, [datetime(2026, 1, 1, 9, 10, 0)])

    def test_scheduled_clock_jumps_to_next_job(self) -> None:
        calls = []
        clock = Clock.scheduled(start_at=datetime(2026, 1, 1, 9, 0, 0))
        clock.every().hour.do(lambda: calls.append(clock.now()))

        clock.step()

        self.assertEqual(clock.now(), datetime(2026, 1, 1, 10, 0, 0))
        self.assertEqual(calls, [datetime(2026, 1, 1, 10, 0, 0)])

    def test_daily_at_schedules_next_matching_time(self) -> None:
        calls = []
        clock = Clock.manual(start_at=datetime(2026, 1, 1, 8, 0, 0))
        clock.every().day.at("09:30").do(lambda: calls.append(clock.now()))

        self.assertEqual(clock.next_run(), datetime(2026, 1, 1, 9, 30, 0))

        clock.step(hours=1, minutes=30)
        self.assertEqual(calls, [datetime(2026, 1, 1, 9, 30, 0)])
        self.assertEqual(clock.next_run(), datetime(2026, 1, 2, 9, 30, 0))

    def test_tags_clear_and_cancel_job_sentinel(self) -> None:
        calls = []
        clock = Clock.manual(start_at=datetime(2026, 1, 1))

        def once():
            calls.append("once")
            return CancelJob

        clock.every().second.do(once).tag("temporary")
        clock.every().second.do(lambda: calls.append("keep")).tag("permanent")

        clock.step(seconds=1)
        self.assertEqual(calls, ["once", "keep"])
        self.assertEqual(len(clock.jobs()), 1)

        clock.clear("permanent")
        self.assertEqual(clock.jobs(), [])

    def test_manual_clock_rejects_empty_step(self) -> None:
        clock = Clock.manual(start_at=datetime(2026, 1, 1))

        with self.assertRaises(ClockError):
            clock.step()


if __name__ == "__main__":
    unittest.main()
