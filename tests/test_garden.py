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


def network(cal, events):
    """Stub GitHub: the GraphQL calendar, and the events page (raised if it is an exception)."""
    def urlopen(req, timeout=None):
        if req.full_url.endswith("graphql"):
            return io.BytesIO(json.dumps(cal).encode())
        if isinstance(events, Exception):
            raise events
        return io.BytesIO(json.dumps(events).encode())
    return mock.patch.object(urllib.request, "urlopen", urlopen)


class Activity(unittest.TestCase):
    CAL = calendar(dt.date(2026, 11, 4), [1] * 371)

    def last_push(self, events):
        with network(self.CAL, events):
            return garden.activity("scryst", "x")[2]

    def test_latest_push_skips_other_events(self):
        self.assertEqual(self.last_push([{"type": "WatchEvent", "created_at": "2026-11-04T20:00:00Z"},
                                         {"type": "PushEvent", "created_at": "2026-11-04T17:00:00Z"}]),
                         dt.datetime(2026, 11, 4, 17, tzinfo=UTC))

    def test_no_push_or_a_bad_page_is_none_and_never_fails_the_print(self):
        for events in ([{"type": "WatchEvent", "created_at": "2026-11-04T20:00:00Z"}],
                       OSError("down"), {"message": "rate limited"}, [{"type": "PushEvent"}]):
            with self.subTest(events=events):
                self.assertIsNone(self.last_push(events))


def print_svgs(print_at, counts, end=dt.date(2026, 11, 5)):
    """Run the script as the workflow does, network stubbed; return {theme: svg}."""
    events = [{"type": "PushEvent", "created_at": "2026-11-04T18:00:00Z"}]
    with tempfile.TemporaryDirectory() as out, redirect_stdout(io.StringIO()), network(calendar(end, counts), events), \
            mock.patch.dict(os.environ, {"GH_TOKEN": "x", "PRINT_AT": print_at}), \
            mock.patch.object(sys, "argv", [str(SRC), out]):
        runpy.run_path(str(SRC), run_name="__main__")
        return {t: (Path(out) / f"garden-{t}.svg").read_text() for t in ("light", "dark")}


COUNTS = [(i * 7) % 11 for i in range(371)]


class PrintAt(unittest.TestCase):
    def test_an_offset_or_no_zone_is_the_same_instant_as_utc(self):
        utc = print_svgs("2026-11-04T20:00Z", COUNTS)
        for at in ("2026-11-04T12:00-08:00", "2026-11-04T20:00"):     # an offset; naive reads as UTC
            with self.subTest(at=at):
                self.assertTrue(print_svgs(at, COUNTS) == utc, "the prints differ")   # not assertEqual: its diff of ~430KB runs for minutes


class Today(unittest.TestCase):
    """The calendar's days are UTC, so at night in Los Angeles its last day is already tomorrow."""

    def test_fireworks_on_the_night_of_the_record_day(self):
        for at, counts, fires in (
                ("2026-11-05T05:00Z", COUNTS[:-2] + [50, 2], True),   # 21:00 Nov 4 in LA, the best day; Nov 5 (UTC) has begun
                ("2026-11-05T05:00Z", COUNTS, False),                 # an ordinary night
                ("2026-11-06T05:00Z", COUNTS[:-1] + [50], True)):     # the record on the calendar's last day
            with self.subTest(at=at, fires=fires):
                self.assertEqual('class="burst"' in print_svgs(at, counts)["light"], fires)


if __name__ == "__main__":
    unittest.main()
