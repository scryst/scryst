"""Offline checks for scripts/garden.py: the GitHub API is stubbed, so no network or token."""
import datetime as dt
import importlib.util
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "scripts" / "garden.py"
spec = importlib.util.spec_from_file_location("garden", SRC)
garden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(garden)

UTC = dt.timezone.utc


def calendar(end, counts):
    """A contribution calendar ending on `end`, as the GraphQL API returns it."""
    dates = [end - dt.timedelta(days=len(counts) - 1 - i) for i in range(len(counts))]
    weeks = [{"contributionDays": [{"date": d.isoformat(), "contributionCount": c}
                                   for d, c in zip(dates[i:i + 7], counts[i:i + 7])]} for i in range(0, len(counts), 7)]
    return {"data": {"user": {"contributionsCollection": {"contributionCalendar": {
        "totalContributions": sum(counts), "weeks": weeks}}}}}


def stub(cal, events):
    def api(path, token, body=None):
        if path == "graphql":
            return cal
        if isinstance(events, Exception):
            raise events
        return events
    return api


class Activity(unittest.TestCase):
    def setUp(self):
        self.real = garden.api
        self.cal = calendar(dt.date(2026, 11, 4), [1] * 371)

    def tearDown(self):
        garden.api = self.real

    def test_latest_push_skips_other_events(self):
        garden.api = stub(self.cal, [{"type": "WatchEvent", "created_at": "2026-11-04T20:00:00Z"},
                                     {"type": "PushEvent", "created_at": "2026-11-04T17:00:00Z"}])
        _, _, last = garden.activity("scryst", "x")
        self.assertEqual(last, dt.datetime(2026, 11, 4, 17, tzinfo=UTC))

    def test_no_push_in_the_page_is_none(self):
        garden.api = stub(self.cal, [{"type": "WatchEvent", "created_at": "2026-11-04T20:00:00Z"}])
        self.assertIsNone(garden.activity("scryst", "x")[2])

    def test_events_failure_never_fails_the_print(self):
        for bad in (OSError("down"), {"message": "rate limited"}, [{"type": "PushEvent"}]):
            garden.api = stub(self.cal, bad)
            self.assertIsNone(garden.activity("scryst", "x")[2])


if __name__ == "__main__":
    unittest.main()
