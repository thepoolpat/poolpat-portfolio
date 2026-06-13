"""Tests for fetch_plays.py orchestration paths.

These cover the higher-level fetch_*_all functions that combine API calls
with the monotonic invariant. The monotonic helpers themselves are tested
in test_fetch_plays_monotonic.py.

Each platform fetcher must:
- preserve existing data when the API fails / returns zeros
- merge real data monotonically (never decrease counts)
- not crash on malformed / partial responses
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

import fetch_plays


def _resp(status=200, json_body=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_body if json_body is not None else {}
    r.text = text
    r.content = text.encode() if text else b""
    return r


# ─── SoundCloud orchestration ────────────────────────────────────────────────

class TestFetchSoundcloudAll(unittest.TestCase):
    @patch("fetch_plays.fetch_soundcloud_profile")
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss")
    @patch("fetch_plays._get_soundcloud_client_id")
    def test_api_zero_plays_preserves_existing(self, _cid, mock_rss, mock_v2, mock_profile):
        """When the API returns no real plays, existing data must be preserved verbatim."""
        mock_rss.return_value = []
        mock_v2.return_value = {}  # API failed / returned nothing
        mock_profile.return_value = {}

        existing = {
            "tracks": {"old_track": 5000},
            "total_plays": 5000,
            "followers": 100,
            "total_streams_sc": 5000,
        }
        sc_data, _, got_plays = fetch_plays.fetch_soundcloud_all(existing)

        self.assertFalse(got_plays)
        self.assertEqual(sc_data["fetch_status"], "api_failed_preserved")
        self.assertEqual(sc_data["tracks"]["old_track"], 5000)
        self.assertEqual(sc_data["total_plays"], 5000)
        # Manually-curated keys stay
        self.assertEqual(sc_data["total_streams_sc"], 5000)

    @patch("fetch_plays.fetch_soundcloud_profile")
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss")
    @patch("fetch_plays._get_soundcloud_client_id")
    def test_api_returns_higher_counts_merges(self, _cid, mock_rss, mock_v2, mock_profile):
        mock_rss.return_value = []
        mock_v2.return_value = {"track_a": 1500, "track_b": 200}
        mock_profile.return_value = {"track_count": 2, "followers_count": 50}

        existing = {"tracks": {"track_a": 1000, "track_b": 100}, "total_plays": 1100}
        sc_data, _, got_plays = fetch_plays.fetch_soundcloud_all(existing)

        self.assertTrue(got_plays)
        self.assertEqual(sc_data["fetch_status"], "success")
        self.assertEqual(sc_data["tracks"]["track_a"], 1500)
        self.assertEqual(sc_data["tracks"]["track_b"], 200)
        self.assertEqual(sc_data["total_plays"], 1700)

    @patch("fetch_plays.fetch_soundcloud_profile")
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss")
    @patch("fetch_plays._get_soundcloud_client_id")
    def test_api_returns_lower_counts_does_not_decrease(self, _cid, mock_rss, mock_v2, mock_profile):
        """The load-bearing case: API briefly returns lower numbers — totals must not regress."""
        mock_rss.return_value = []
        mock_v2.return_value = {"track_a": 50}  # API hiccup
        mock_profile.return_value = {}

        existing = {"tracks": {"track_a": 10000}, "total_plays": 10000}
        sc_data, _, got_plays = fetch_plays.fetch_soundcloud_all(existing)

        self.assertTrue(got_plays)  # Got *some* data
        self.assertEqual(sc_data["tracks"]["track_a"], 10000)  # but didn't lower it
        self.assertEqual(sc_data["total_plays"], 10000)

    @patch("fetch_plays.fetch_soundcloud_profile")
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss")
    @patch("fetch_plays._get_soundcloud_client_id")
    def test_rss_only_new_release_added_with_zero(self, _cid, mock_rss, mock_v2, mock_profile):
        """RSS feed publishes a new track before the API knows about it. Add it with 0 plays."""
        mock_rss.return_value = [{"title": "brand_new_track"}]
        mock_v2.return_value = {"old_track": 100}
        mock_profile.return_value = {}

        sc_data, _, _ = fetch_plays.fetch_soundcloud_all({"tracks": {"old_track": 100}, "total_plays": 100})

        self.assertIn("brand_new_track", sc_data["tracks"])
        self.assertEqual(sc_data["tracks"]["brand_new_track"], 0)
        # Pre-existing track keeps its count
        self.assertEqual(sc_data["tracks"]["old_track"], 100)

    @patch("fetch_plays.fetch_soundcloud_profile")
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss")
    @patch("fetch_plays._get_soundcloud_client_id")
    def test_rss_fuzzy_match_does_not_duplicate(self, _cid, mock_rss, mock_v2, mock_profile):
        """If RSS title matches an existing track case-insensitively, do not re-add."""
        mock_rss.return_value = [{"title": "  Track A  "}]
        mock_v2.return_value = {"track a": 500}
        mock_profile.return_value = {}

        sc_data, _, _ = fetch_plays.fetch_soundcloud_all({"tracks": {}, "total_plays": 0})

        # Only the API-provided form should remain, not a duplicate
        self.assertIn("track a", sc_data["tracks"])
        self.assertNotIn("  Track A  ", sc_data["tracks"])

    @patch("fetch_plays.fetch_soundcloud_profile")
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss")
    @patch("fetch_plays._get_soundcloud_client_id")
    def test_rss_nfd_title_does_not_duplicate_nfc_track(self, _cid, mock_rss, mock_v2, mock_profile):
        """An NFD-form RSS title must not re-create a row for an existing NFC track."""
        import unicodedata
        nfc = unicodedata.normalize("NFC", "Déjà 30 Piges")
        nfd = unicodedata.normalize("NFD", "Déjà 30 Piges")
        mock_rss.return_value = [{"title": nfd}]
        mock_v2.return_value = {nfc: 1355}
        mock_profile.return_value = {}

        sc_data, _, _ = fetch_plays.fetch_soundcloud_all({"tracks": {nfc: 1300}, "total_plays": 1300})

        self.assertEqual(sc_data["tracks"], {nfc: 1355})  # one row, NFC form, max value


# ─── Spotify orchestration ───────────────────────────────────────────────────

class TestFetchSpotifyAll(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays._get_spotify_token", return_value=None)
    def test_no_token_no_user_auth_returns_failed(self, _tok):
        existing = {"tracks": {"t": 100}, "total_streams": 100}
        sp_data, got = fetch_plays.fetch_spotify_all(existing)

        self.assertFalse(got)
        self.assertEqual(sp_data["fetch_status"], "failed")
        # Existing data is preserved
        self.assertEqual(sp_data["tracks"]["t"], 100)

    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays._get_spotify_token", return_value="fake_token")
    def test_client_credentials_path_merges_popularity(self, _tok, mock_get):
        """Client-credentials fallback: fetch albums → tracks → popularity scores."""
        # 1st call (album group "album"), then "single", "appears_on", "compilation"
        # then album-batch fetch, then track-batch fetch.
        album_resp = _resp(200, {
            "items": [{"id": "alb1"}],
            "next": None,
        })
        empty_album_resp = _resp(200, {"items": [], "next": None})
        album_batch_resp = _resp(200, {
            "albums": [{
                "tracks": {"items": [
                    {"id": "trk1", "artists": [{"id": fetch_plays.SPOTIFY_ARTIST_ID}]},
                ]},
            }],
        })
        track_batch_resp = _resp(200, {
            "tracks": [{"name": "Hit Song", "popularity": 75}],
        })
        mock_get.side_effect = [
            album_resp, empty_album_resp, empty_album_resp, empty_album_resp,
            album_batch_resp, track_batch_resp,
        ]

        existing = {"tracks": {"Hit Song": 50}, "total_streams": 0}
        sp_data, got = fetch_plays.fetch_spotify_all(existing)

        self.assertTrue(got)
        self.assertEqual(sp_data["fetch_status"], "success")
        # Monotonic merge: 75 > 50, so 75 wins
        self.assertEqual(sp_data["tracks"]["Hit Song"], 75)
        self.assertEqual(sp_data["auth_method"], "client_credentials")

    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays._get_spotify_token", return_value="fake_token")
    def test_track_filtered_out_if_not_by_artist(self, _tok, mock_get):
        """Tracks on an 'appears_on' album where the artist isn't a credit must not leak in."""
        album_resp = _resp(200, {"items": [{"id": "alb1"}], "next": None})
        empty = _resp(200, {"items": [], "next": None})
        album_batch_resp = _resp(200, {
            "albums": [{"tracks": {"items": [
                {"id": "trk1", "artists": [{"id": "some_other_artist"}]},
            ]}}],
        })
        track_batch_resp = _resp(200, {"tracks": []})
        mock_get.side_effect = [album_resp, empty, empty, empty, album_batch_resp, track_batch_resp]

        sp_data, got = fetch_plays.fetch_spotify_all({"tracks": {}, "total_streams": 0})

        self.assertEqual(sp_data["tracks"], {})

    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays._get_spotify_token", return_value="fake_token")
    def test_album_endpoint_500_swallows_error(self, _tok, mock_get):
        """Catalog endpoint errors should not propagate — orchestration logs and continues."""
        mock_get.side_effect = Exception("network down")

        existing = {"tracks": {"existing": 100}, "total_streams": 12345}
        sp_data, got = fetch_plays.fetch_spotify_all(existing)

        self.assertFalse(got)  # No tracks fetched
        self.assertEqual(sp_data["fetch_status"], "failed")
        # total_streams from existing is preserved (manually entered)
        self.assertEqual(sp_data.get("tracks", {}).get("existing"), 100)

    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays._get_spotify_token", return_value="fake_token")
    def test_total_streams_preserved_from_existing(self, _tok, mock_get):
        """total_streams is manually entered and must never be overwritten."""
        album_resp = _resp(200, {"items": [{"id": "alb1"}], "next": None})
        empty = _resp(200, {"items": [], "next": None})
        album_batch_resp = _resp(200, {"albums": [{"tracks": {"items": [
            {"id": "t1", "artists": [{"id": fetch_plays.SPOTIFY_ARTIST_ID}]},
        ]}}]})
        track_batch_resp = _resp(200, {"tracks": [{"name": "Song", "popularity": 50}]})
        mock_get.side_effect = [album_resp, empty, empty, empty, album_batch_resp, track_batch_resp]

        existing = {"tracks": {}, "total_streams": 999999, "monthly_listeners": 5000}
        sp_data, _ = fetch_plays.fetch_spotify_all(existing)

        self.assertEqual(sp_data["total_streams"], 999999)
        self.assertEqual(sp_data["monthly_listeners"], 5000)


# ─── Apple Music orchestration ───────────────────────────────────────────────

class TestFetchAppleMusicAll(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    def test_no_token_falls_back_to_scrape(self, mock_get):
        html = """
        <html><script type="application/ld+json">
        {"@type": "MusicGroup", "track": [{"name": "Scraped Song"}]}
        </script></html>
        """
        mock_get.return_value = _resp(200, text=html)

        existing = {"tracks": {}, "total_tracks": 0}
        am_data, got = fetch_plays.fetch_apple_music_all(existing)

        self.assertTrue(got)
        self.assertIn("Scraped Song", am_data["tracks"])
        self.assertEqual(am_data["fetch_status"], "catalog_only")

    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    def test_existing_manual_data_preserved(self, mock_get):
        """If we already have manual play counts, never overwrite them."""
        mock_get.return_value = _resp(200, text="")  # Scrape returns nothing

        existing = {"tracks": {"My Song": 50000}, "total_plays": 50000}
        am_data, got = fetch_plays.fetch_apple_music_all(existing)

        self.assertTrue(got)
        self.assertEqual(am_data["tracks"]["My Song"], 50000)
        self.assertEqual(am_data["fetch_status"], "preserved")

    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    def test_malformed_json_ld_does_not_crash(self, mock_get):
        html = """<script type="application/ld+json">not json</script>"""
        mock_get.return_value = _resp(200, text=html)

        am_data, got = fetch_plays.fetch_apple_music_all({"tracks": {}})

        self.assertFalse(got)
        self.assertEqual(am_data["fetch_status"], "failed")

    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.get")
    def test_timeout_does_not_propagate(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        am_data, got = fetch_plays.fetch_apple_music_all({"tracks": {"s": 100}})

        # Existing manual data preserved despite timeout
        self.assertTrue(got)
        self.assertEqual(am_data["tracks"]["s"], 100)

    @patch.dict(os.environ, {"APPLE_MUSIC_TOKEN": "tok"}, clear=True)
    @patch("fetch_plays.requests.get")
    def test_api_token_path(self, mock_get):
        mock_get.return_value = _resp(200, {
            "data": [{"attributes": {"name": "API Song"}}],
        })
        am_data, got = fetch_plays.fetch_apple_music_all({"tracks": {}})

        self.assertTrue(got)
        self.assertIn("API Song", am_data["tracks"])

    @patch.dict(os.environ, {"APPLE_MUSIC_TOKEN": "expired"}, clear=True)
    @patch("fetch_plays.requests.get")
    def test_expired_token_falls_back_to_scrape(self, mock_get):
        api_401 = _resp(401)
        scrape_html = '<script type="application/ld+json">{"@type": "MusicGroup", "track": [{"name": "Fallback Song"}]}</script>'
        mock_get.side_effect = [api_401, _resp(200, text=scrape_html)]

        am_data, got = fetch_plays.fetch_apple_music_all({"tracks": {}})

        self.assertTrue(got)
        self.assertIn("Fallback Song", am_data["tracks"])


# ─── History CSV orchestration ───────────────────────────────────────────────

class TestAppendHistoryCsv(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.TemporaryDirectory()
        self._orig_data_dir = fetch_plays.DATA_DIR
        self._orig_history = fetch_plays.HISTORY_CSV
        fetch_plays.DATA_DIR = type(fetch_plays.DATA_DIR)(self.tmpdir.name)
        fetch_plays.HISTORY_CSV = fetch_plays.DATA_DIR / "history.csv"

    def tearDown(self):
        fetch_plays.DATA_DIR = self._orig_data_dir
        fetch_plays.HISTORY_CSV = self._orig_history
        self.tmpdir.cleanup()

    def _read_rows(self):
        import csv
        with open(fetch_plays.HISTORY_CSV) as f:
            return list(csv.DictReader(f))

    def test_first_write_creates_header_and_row(self):
        data = {
            "last_updated": "2026-01-01T00:00:00Z",
            "soundcloud": {"total_plays": 100, "tracks": {"a": 100}},
            "spotify": {"total_streams": 50, "tracks": {}},
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        fetch_plays.append_history_csv(data)
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["soundcloud_total_plays"], "100")
        self.assertEqual(rows[0]["spotify_total_streams"], "50")

    def test_lower_total_does_not_regress_in_csv(self):
        """If a fetch hiccup writes a lower total, the CSV row must keep the prior max."""
        first = {
            "last_updated": "2026-01-01T00:00:00Z",
            "soundcloud": {"total_plays": 5000, "tracks": {}},
            "spotify": {"total_streams": 0, "tracks": {}},
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        second = {
            "last_updated": "2026-01-02T00:00:00Z",
            "soundcloud": {"total_plays": 100, "tracks": {}},  # API hiccup
            "spotify": {"total_streams": 0, "tracks": {}},
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        fetch_plays.append_history_csv(first)
        fetch_plays.append_history_csv(second)

        rows = self._read_rows()
        self.assertEqual(rows[1]["soundcloud_total_plays"], "5000")  # NOT 100

    def test_legacy_popularity_column_used_as_fallback(self):
        """Old rows used spotify_total_popularity; the function must fall back to it."""
        # Manually seed a CSV with the legacy column
        with open(fetch_plays.HISTORY_CSV, "w") as f:
            f.write("timestamp,soundcloud_total_plays,soundcloud_track_count,"
                    "spotify_total_popularity,spotify_track_count,"
                    "apple_music_total_plays,apple_music_track_count\n")
            f.write("2026-01-01T00:00:00Z,0,0,42,5,0,0\n")

        new_data = {
            "last_updated": "2026-01-02T00:00:00Z",
            "soundcloud": {"total_plays": 0, "tracks": {}},
            "spotify": {"total_streams": 10, "tracks": {}},  # lower than legacy 42
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        fetch_plays.append_history_csv(new_data)

        # Read the raw last line — the file header is still legacy, but we want to
        # confirm the spotify column (4th position) was written as the legacy max (42).
        import csv
        with open(fetch_plays.HISTORY_CSV) as f:
            rows = list(csv.reader(f))
        spotify_col = rows[-1][3]  # 4th column = spotify total
        self.assertGreaterEqual(int(spotify_col), 42)

    def test_float_prev_total_does_not_crash_next_run(self):
        """A hand-edited float total (e.g. 4108.0) must not crash int() on the
        NEXT run's read-back, and the written column must parse as an int."""
        first = {
            "last_updated": "2026-01-01T00:00:00Z",
            "soundcloud": {"total_plays": 0, "tracks": {}},
            "spotify": {"total_streams": 4108.0, "tracks": {}},  # float, as hand-edited
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        second = {
            "last_updated": "2026-01-02T00:00:00Z",
            "soundcloud": {"total_plays": 0, "tracks": {}},
            "spotify": {"total_streams": 4200, "tracks": {}},  # normal int data
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        fetch_plays.append_history_csv(first)
        # The second call reads the first row back; it must not raise ValueError.
        fetch_plays.append_history_csv(second)

        rows = self._read_rows()
        # The written value parses cleanly as an int (no stray ".0").
        self.assertEqual(int(rows[-1]["spotify_total_streams"]), 4200)

    def test_track_count_does_not_dip_on_failed_fetch(self):
        """A transient failure yields an empty tracks dict; the *_track_count
        column must clamp to the prior value rather than dipping to 0."""
        first = {
            "last_updated": "2026-01-01T00:00:00Z",
            "soundcloud": {
                "total_plays": 5000,
                "tracks": {"a": 1, "b": 1, "c": 1, "d": 1, "e": 1},  # 5 tracks
            },
            "spotify": {"total_streams": 0, "tracks": {}},
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        second = {
            "last_updated": "2026-01-02T00:00:00Z",
            "soundcloud": {
                "total_plays": 5000,  # same/higher total
                "tracks": {},  # transient failure — empty
                "fetch_status": "failed",
            },
            "spotify": {"total_streams": 0, "tracks": {}},
            "apple_music": {"total_plays": 0, "tracks": {}},
        }
        fetch_plays.append_history_csv(first)
        fetch_plays.append_history_csv(second)

        rows = self._read_rows()
        self.assertEqual(int(rows[0]["soundcloud_track_count"]), 5)
        # The clamp holds: count did not drop below the first row.
        self.assertGreaterEqual(
            int(rows[1]["soundcloud_track_count"]),
            int(rows[0]["soundcloud_track_count"]),
        )
        self.assertEqual(int(rows[1]["soundcloud_track_count"]), 5)


# ─── Alert issue creation ────────────────────────────────────────────────────

class TestCreateAlertIssue(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("fetch_plays.requests.post")
    def test_no_github_token_skips_call(self, mock_post):
        fetch_plays.create_alert_issue("SoundCloud", 3)
        mock_post.assert_not_called()

    @patch.dict(os.environ, {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "u/r"}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays.requests.post")
    def test_posts_when_creds_present(self, mock_post, mock_get):
        mock_get.return_value = _resp(200, [])  # no open alert issues
        mock_post.return_value = _resp(201, {"number": 42})
        fetch_plays.create_alert_issue("Spotify", 5)
        self.assertEqual(mock_post.call_count, 1)
        url = mock_post.call_args[0][0]
        self.assertIn("u/r", url)
        body = mock_post.call_args.kwargs["json"]
        self.assertIn("Spotify", body["title"])
        self.assertIn("5", body["title"])

    @patch.dict(os.environ, {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "u/r"}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays.requests.post")
    def test_existing_open_issue_skips_post(self, mock_post, mock_get):
        mock_get.return_value = _resp(
            200, [{"title": "🔴 Spotify fetch failed 3x consecutively"}]
        )
        fetch_plays.create_alert_issue("Spotify", 4)
        mock_post.assert_not_called()

    @patch.dict(os.environ, {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "u/r"}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays.requests.post")
    def test_open_issue_for_other_platform_does_not_block(self, mock_post, mock_get):
        mock_get.return_value = _resp(
            200, [{"title": "🔴 SoundCloud fetch failed 3x consecutively"}]
        )
        mock_post.return_value = _resp(201, {"number": 43})
        fetch_plays.create_alert_issue("Spotify", 3)
        self.assertEqual(mock_post.call_count, 1)

    @patch.dict(os.environ, {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "u/r"}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays.requests.post")
    def test_lookup_failure_still_posts(self, mock_post, mock_get):
        mock_get.side_effect = Exception("network down")
        mock_post.return_value = _resp(201, {"number": 44})
        fetch_plays.create_alert_issue("Spotify", 3)
        self.assertEqual(mock_post.call_count, 1)

    @patch.dict(os.environ, {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "u/r"}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays.requests.post")
    def test_non_201_response_does_not_raise(self, mock_post, mock_get):
        mock_get.return_value = _resp(200, [])
        mock_post.return_value = _resp(403, {"message": "forbidden"})
        # Must not raise
        fetch_plays.create_alert_issue("Spotify", 3)

    @patch.dict(os.environ, {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "u/r"}, clear=True)
    @patch("fetch_plays.requests.get")
    @patch("fetch_plays.requests.post")
    def test_post_failure_does_not_raise(self, mock_post, mock_get):
        mock_get.return_value = _resp(200, [])
        mock_post.side_effect = Exception("boom")
        # Must not raise
        fetch_plays.create_alert_issue("Apple Music", 3)


# ─── Failure tracker & atomic writes ─────────────────────────────────────────

class TestFailureTracker(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        from pathlib import Path
        self.tracker_path = Path(self._dir.name) / ".fetch_failures.json"
        patcher = patch.object(fetch_plays, "FAIL_TRACKER", self.tracker_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_file_returns_defaults(self):
        self.assertEqual(
            fetch_plays.load_failure_tracker(),
            {"soundcloud": 0, "spotify": 0, "apple_music": 0},
        )

    def test_corrupt_file_returns_defaults_instead_of_raising(self):
        self.tracker_path.write_text('{"soundcloud": 2, "spo')  # truncated
        self.assertEqual(
            fetch_plays.load_failure_tracker(),
            {"soundcloud": 0, "spotify": 0, "apple_music": 0},
        )

    def test_partial_file_backfills_missing_platforms(self):
        self.tracker_path.write_text('{"soundcloud": 2}')
        tracker = fetch_plays.load_failure_tracker()
        self.assertEqual(tracker["soundcloud"], 2)
        self.assertEqual(tracker["spotify"], 0)
        self.assertEqual(tracker["apple_music"], 0)

    def test_save_roundtrip_and_no_tmp_left_behind(self):
        fetch_plays.save_failure_tracker({"soundcloud": 1, "spotify": 0, "apple_music": 0})
        self.assertEqual(fetch_plays.load_failure_tracker()["soundcloud"], 1)
        leftovers = list(self.tracker_path.parent.glob("*.tmp"))
        self.assertEqual(leftovers, [])


class TestAtomicWriteJson(unittest.TestCase):
    def test_failed_serialization_leaves_existing_file_intact(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "plays.json"
            target.write_text('{"good": true}')
            with self.assertRaises(TypeError):
                fetch_plays._atomic_write_json(target, {"bad": object()})
            # Original content untouched, no temp debris
            self.assertEqual(json.loads(target.read_text()), {"good": True})
            self.assertEqual(list(Path(d).glob("*.tmp")), [])


# ─── SoundCloud RSS parsing ──────────────────────────────────────────────────

class TestFetchSoundcloudRss(unittest.TestCase):
    @patch("fetch_plays.requests.get")
    def test_parses_well_formed_feed(self, mock_get):
        rss = b"""<?xml version="1.0"?>
        <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
          <item>
            <title>Track One</title>
            <link>https://example.com/t1</link>
            <pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>
            <itunes:duration>180</itunes:duration>
            <enclosure url="https://example.com/t1.mp3"/>
          </item>
        </channel></rss>
        """
        r = MagicMock()
        r.content = rss
        r.raise_for_status = MagicMock()
        mock_get.return_value = r

        tracks = fetch_plays.fetch_soundcloud_rss()
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]["title"], "Track One")
        self.assertEqual(tracks[0]["stream_url"], "https://example.com/t1.mp3")

    @patch("fetch_plays.requests.get")
    def test_malformed_xml_returns_empty_list(self, mock_get):
        r = MagicMock()
        r.content = b"<not valid xml"
        r.raise_for_status = MagicMock()
        mock_get.return_value = r

        tracks = fetch_plays.fetch_soundcloud_rss()
        self.assertEqual(tracks, [])

    @patch("fetch_plays.requests.get")
    def test_http_error_returns_empty_list(self, mock_get):
        mock_get.side_effect = Exception("network down")
        tracks = fetch_plays.fetch_soundcloud_rss()
        self.assertEqual(tracks, [])


# ─── SoundCloud v2 API pagination ────────────────────────────────────────────

class TestFetchSoundcloudPlaysV2(unittest.TestCase):
    @patch("fetch_plays.requests.get")
    def test_paginates_until_empty(self, mock_get):
        page1 = _resp(200, {
            "collection": [{"title": f"t{i}", "playback_count": i} for i in range(50)],
            "next_href": "https://api/next",
        })
        page2 = _resp(200, {
            "collection": [{"title": "t50", "playback_count": 50}],
            "next_href": None,
        })
        mock_get.side_effect = [page1, page2]

        tracks = fetch_plays.fetch_soundcloud_plays_v2(client_id="cid")
        self.assertEqual(len(tracks), 51)
        self.assertEqual(tracks["t50"], 50)

    @patch("fetch_plays.requests.get")
    def test_http_error_at_offset_returns_partial(self, mock_get):
        page1 = _resp(200, {
            "collection": [{"title": "t0", "playback_count": 100}] * 50,
            "next_href": "https://api/next",
        })
        # use unique titles to avoid dict collapse
        page1 = _resp(200, {
            "collection": [{"title": f"t{i}", "playback_count": i} for i in range(50)],
            "next_href": "https://api/next",
        })
        page2 = _resp(500)
        mock_get.side_effect = [page1, page2]

        tracks = fetch_plays.fetch_soundcloud_plays_v2(client_id="cid")
        self.assertEqual(len(tracks), 50)  # only the first page

    @patch("fetch_plays.requests.get")
    def test_null_playback_count_becomes_zero(self, mock_get):
        mock_get.return_value = _resp(200, {
            "collection": [{"title": "t1", "playback_count": None}],
            "next_href": None,
        })
        tracks = fetch_plays.fetch_soundcloud_plays_v2(client_id="cid")
        self.assertEqual(tracks["t1"], 0)


if __name__ == "__main__":
    unittest.main()
