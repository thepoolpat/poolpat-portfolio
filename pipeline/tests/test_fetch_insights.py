"""Tests for fetch_insights.py.

Covers:
- parse_totals: escaped flight-data extraction, decoy-window rejection,
  sum validation, login-page (no matches)
- update_files: insights.json write, monotonic plays.json merge,
  no-change short-circuit
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fetch_insights import parse_totals, update_files

# Quotes as they appear in real Next.js flight data (backslash-escaped).
FLIGHT = (
    '{\\"dsp\\":\\"SOUNDCLOUD\\",\\"plays\\":28644,\\"likes\\":270},'
    '{\\"dsp\\":\\"SPOTIFY\\",\\"plays\\":20354,\\"likes\\":0},'
    '{\\"dsp\\":\\"APPLE\\",\\"plays\\":4129,\\"likes\\":0},'
    '{\\"dsp\\":\\"GLOBAL\\",\\"plays\\":53127,\\"likes\\":270}'
)

TOTALS = {"SOUNDCLOUD": 28644, "SPOTIFY": 20354, "APPLE": 4129, "GLOBAL": 53127}


class ParseTotalsTest(unittest.TestCase):
    def test_extracts_escaped_flight_data(self):
        self.assertEqual(parse_totals("prefix" + FLIGHT + "suffix"), TOTALS)

    def test_plain_json_also_matches(self):
        self.assertEqual(parse_totals(FLIGHT.replace("\\", "")), TOTALS)

    def test_skips_decoy_window_that_fails_sum(self):
        # An earlier group (e.g. another timewindow) whose triple doesn't sum.
        decoy = FLIGHT.replace("53127", "99999")
        self.assertEqual(parse_totals(decoy + "," + FLIGHT), TOTALS)

    def test_login_page_returns_none(self):
        self.assertIsNone(parse_totals("<html>Sign in to SoundCloud</html>"))

    def test_bad_sum_returns_none(self):
        self.assertIsNone(parse_totals(FLIGHT.replace("53127", "99999")))


class UpdateFilesTest(unittest.TestCase):
    def _data_dir(self, spotify=20263, am=4119, insights=None):
        d = Path(self.tmp.name)
        plays = {
            "artist": "Poolpat",
            "soundcloud": {"total_plays": 28588},
            "spotify": {"total_streams": spotify},
            "apple_music": {"total_plays": am},
        }
        (d / "plays.json").write_text(json.dumps(plays))
        if insights is not None:
            (d / "insights.json").write_text(json.dumps(insights))
        return d

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_writes_insights_and_bumps_plays(self):
        d = self._data_dir()
        summary = update_files(TOTALS, d, "2026-07-18T00:00:00+00:00")
        self.assertIn("spotify 20263->20354", summary)
        ins = json.loads((d / "insights.json").read_text())
        self.assertEqual(ins["total_plays"], 53127)
        self.assertEqual(ins["fetched_at"], "2026-07-18T00:00:00+00:00")
        plays = json.loads((d / "plays.json").read_text())
        self.assertEqual(plays["spotify"]["total_streams"], 20354)
        self.assertEqual(plays["apple_music"]["total_plays"], 4129)
        # soundcloud untouched — owned by the weekly fetch workflow
        self.assertEqual(plays["soundcloud"]["total_plays"], 28588)

    def test_monotonic_never_decreases(self):
        d = self._data_dir(spotify=99999)
        update_files(TOTALS, d, "2026-07-18T00:00:00+00:00")
        plays = json.loads((d / "plays.json").read_text())
        self.assertEqual(plays["spotify"]["total_streams"], 99999)

    def test_lower_total_raises_instead_of_writing(self):
        stored = {"total_plays": 99999}
        d = self._data_dir(insights=stored)
        with self.assertRaises(ValueError):
            update_files(TOTALS, d, "2026-07-18T00:00:00+00:00")
        # nothing written
        self.assertEqual(json.loads((d / "insights.json").read_text()), stored)
        self.assertEqual(
            json.loads((d / "plays.json").read_text())["spotify"]["total_streams"],
            20263,
        )

    def test_plays_bumped_even_when_insights_current(self):
        # insights.json already matches the scrape, but plays.json lags
        # (e.g. a conflict resolution kept main's plays.json) — the
        # monotonic bump must still run.
        stored = {
            "total_plays": 53127,
            "soundcloud_plays": 28644,
            "spotify_plays": 20354,
            "apple_music_plays": 4129,
        }
        d = self._data_dir(spotify=20263, insights=stored)
        self.assertIsNotNone(update_files(TOTALS, d, "2026-07-18T00:00:00+00:00"))
        plays = json.loads((d / "plays.json").read_text())
        self.assertEqual(plays["spotify"]["total_streams"], 20354)

    def test_no_change_returns_none_and_writes_nothing(self):
        stored = {
            "fetched_at": "old",
            "total_plays": 53127,
            "soundcloud_plays": 28644,
            "spotify_plays": 20354,
            "apple_music_plays": 4129,
        }
        d = self._data_dir(spotify=20354, am=4129, insights=stored)
        before = (d / "insights.json").read_text()
        self.assertIsNone(update_files(TOTALS, d, "2026-07-18T00:00:00+00:00"))
        self.assertEqual((d / "insights.json").read_text(), before)


if __name__ == "__main__":
    unittest.main()
