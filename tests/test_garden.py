"""Offline checks for scripts/garden.py: the GitHub API is stubbed, so no network or token."""
import datetime as dt
import importlib.util
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import urllib.request
from contextlib import redirect_stdout
from unittest import mock
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


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def print_svgs(print_at, counts, end=dt.date(2026, 11, 5), events=()):
    """Run the script as the workflow does, network stubbed; return {theme: svg}."""
    cal = calendar(end, counts)
    events = list(events) or [{"type": "PushEvent", "created_at": "2026-11-04T18:00:00Z"}]
    fake = lambda req, timeout=None: Response(json.dumps(cal if req.full_url.endswith("graphql") else events).encode())
    with tempfile.TemporaryDirectory() as out, redirect_stdout(io.StringIO()), \
            mock.patch.object(urllib.request, "urlopen", fake), \
            mock.patch.dict(os.environ, {"GH_TOKEN": "x", "PRINT_AT": print_at}), \
            mock.patch.object(sys, "argv", [str(SRC), out]):
        runpy.run_path(str(SRC), run_name="__main__")
        return {t: (Path(out) / f"garden-{t}.svg").read_text() for t in ("light", "dark")}


COUNTS = [(i * 7) % 11 for i in range(371)]


class PrintAt(unittest.TestCase):
    def assertSame(self, a, b):
        self.assertTrue(a == b, "the prints differ")

    def test_offset_is_the_same_instant_as_utc(self):
        self.assertSame(print_svgs("2026-11-04T12:00-08:00", COUNTS), print_svgs("2026-11-04T20:00Z", COUNTS))

    def test_naive_is_utc(self):
        self.assertSame(print_svgs("2026-11-04T20:00", COUNTS), print_svgs("2026-11-04T20:00Z", COUNTS))



class Today(unittest.TestCase):
    """The calendar's days are UTC, so at night in Los Angeles its last day is already tomorrow."""
    LA_NIGHT = "2026-11-05T05:00Z"                    # 21:00 on Nov 4 in Los Angeles

    def fireworks(self, *args, **kw):
        return 'class="burst"' in print_svgs(*args, **kw)["light"]

    def test_record_day_ends_in_fireworks_after_utc_midnight(self):
        counts = COUNTS[:-2] + [50, 2]                # Nov 4 is the year's best; Nov 5 (UTC) has begun
        self.assertTrue(self.fireworks(self.LA_NIGHT, counts))

    def test_ordinary_night_has_none(self):
        self.assertFalse(self.fireworks(self.LA_NIGHT, COUNTS))

    def test_record_on_the_last_day_still_fires(self):
        counts = COUNTS[:-1] + [50]
        self.assertTrue(self.fireworks("2026-11-06T05:00Z", counts))


if __name__ == "__main__":
    unittest.main()
