"""Tests for the SoundCloud track-details (engagement + metadata) path.

Unlike play counts, engagement is deliberately NOT monotonic: likes/reposts can
genuinely decrease (unlikes). Safety against bad fetches comes from gating —
details merge only from a fetch that returned real play counts, and only for
tracks present in that fetch. These tests pin down that policy, the metadata
precedence (fetched v2 > existing > RSS fallback), and the one-time
history.csv header migration for the new engagement columns.
"""

import csv
import tempfile
import unicodedata
import unittest
from unittest.mock import patch

import fetch_plays


def _details(**overrides):
    d = {
        "likes": 10, "reposts": 2, "comments": 1, "downloads": 3,
        "permalink_url": "https://soundcloud.com/poolpat/track",
        "artwork_url": "https://i1.sndcdn.com/artworks-abc-large.jpg",
        "created_at": "2024-01-01T00:00:00Z",
        "genre": "Hip-hop",
    }
    d.update(overrides)
    return d


# ─── merge_track_details ─────────────────────────────────────────────────────

class TestMergeTrackDetails(unittest.TestCase):
    def test_new_track_from_fetch_gets_full_details(self):
        merged = fetch_plays.merge_track_details(
            {}, {"Track A": _details()}, {}, {"Track A": 100})
        self.assertEqual(merged["Track A"]["likes"], 10)
        self.assertEqual(merged["Track A"]["genre"], "Hip-hop")

    def test_track_absent_from_fetch_keeps_existing_verbatim(self):
        """Partial-response safety: a track the API didn't return this run must
        keep its existing details untouched — the load-bearing gating case."""
        existing = {"Track A": _details(likes=44)}
        merged = fetch_plays.merge_track_details(
            existing, {"Track B": _details(likes=5)}, {},
            {"Track A": 100, "Track B": 50})
        self.assertEqual(merged["Track A"], existing["Track A"])
        self.assertEqual(merged["Track B"]["likes"], 5)

    def test_fetched_lower_engagement_wins(self):
        """Policy test (non-monotonic by design): a real fetch reporting fewer
        likes (unlikes) replaces the higher stored value."""
        merged = fetch_plays.merge_track_details(
            {"Track A": _details(likes=44)},
            {"Track A": _details(likes=40)},
            {}, {"Track A": 100})
        self.assertEqual(merged["Track A"]["likes"], 40)

    def test_fetched_zero_engagement_wins(self):
        """Zero from a successful fetch is data, not a miss — unlike the plays
        merge, which skips zeros."""
        merged = fetch_plays.merge_track_details(
            {"Track A": _details(likes=44)},
            {"Track A": _details(likes=0)},
            {}, {"Track A": 100})
        self.assertEqual(merged["Track A"]["likes"], 0)

    def test_non_numeric_fetched_engagement_preserves_existing(self):
        merged = fetch_plays.merge_track_details(
            {"Track A": _details(likes=44)},
            {"Track A": _details(likes="lots")},
            {}, {"Track A": 100})
        self.assertEqual(merged["Track A"]["likes"], 44)

    def test_title_variants_collapse_to_final_tracks_key(self):
        """NFC/NFD, curly-apostrophe, and case variants of one title must all
        resolve to the merged tracks dict's display key (same semantics as
        monotonic_merge_tracks)."""
        nfc = unicodedata.normalize("NFC", "Déjà 30 Piges")
        nfd = unicodedata.normalize("NFD", "Déjà 30 Piges")
        merged = fetch_plays.merge_track_details(
            {nfd.upper(): _details(comments=7)},
            {nfd: _details(likes=12, comments=None)},
            {}, {nfc: 1355})
        self.assertEqual(list(merged.keys()), [nfc])
        self.assertEqual(merged[nfc]["likes"], 12)
        self.assertEqual(merged[nfc]["comments"], 7)  # non-numeric fetched -> existing

    def test_metadata_precedence_fetched_then_existing_then_rss(self):
        existing = {"Track A": {"artwork_url": "https://old/art.jpg",
                                "created_at": "2023-01-01"}}
        fetched = {"Track A": {"likes": 1, "artwork_url": "https://new/art.jpg",
                               "created_at": ""}}  # empty falls through
        rss = {fetch_plays._canon_key("Track A"): {
            "permalink_url": "https://soundcloud.com/poolpat/rss-only",
            "created_at": "Mon, 01 Jan 2024 00:00:00 +0000"}}
        merged = fetch_plays.merge_track_details(
            existing, fetched, rss, {"Track A": 100})
        self.assertEqual(merged["Track A"]["artwork_url"], "https://new/art.jpg")  # fetched wins
        self.assertEqual(merged["Track A"]["created_at"], "2023-01-01")  # empty fetched -> existing
        self.assertEqual(merged["Track A"]["permalink_url"],
                         "https://soundcloud.com/poolpat/rss-only")  # only RSS has it

    def test_rss_only_track_gets_rss_metadata(self):
        """A brand-new release the v2 API doesn't list yet (added at 0 plays by
        the RSS discovery path) gets its link/artwork/date from the feed."""
        rss_tracks = [{"title": "Brand New", "link": "https://soundcloud.com/poolpat/new",
                       "artwork": "https://i1.sndcdn.com/artworks-new.jpg",
                       "pub_date": "Mon, 09 Jun 2026 00:00:00 +0000"}]
        rss = fetch_plays._rss_track_details(rss_tracks)
        merged = fetch_plays.merge_track_details(
            {}, {}, rss, {"Brand New": 0})
        self.assertEqual(merged["Brand New"]["permalink_url"],
                         "https://soundcloud.com/poolpat/new")
        self.assertEqual(merged["Brand New"]["artwork_url"],
                         "https://i1.sndcdn.com/artworks-new.jpg")
        self.assertEqual(merged["Brand New"]["created_at"],
                         "Mon, 09 Jun 2026 00:00:00 +0000")
        self.assertNotIn("likes", merged["Brand New"])  # RSS never supplies engagement

    def test_track_with_no_data_gets_no_entry(self):
        merged = fetch_plays.merge_track_details({}, {}, {}, {"Silent": 5})
        self.assertEqual(merged, {})

    def test_inputs_are_not_mutated(self):
        existing = {"Track A": _details(likes=44)}
        fetched = {"Track A": _details(likes=50)}
        existing_copy = {t: dict(d) for t, d in existing.items()}
        fetched_copy = {t: dict(d) for t, d in fetched.items()}
        fetch_plays.merge_track_details(existing, fetched, {}, {"Track A": 100})
        self.assertEqual(existing, existing_copy)
        self.assertEqual(fetched, fetched_copy)

    def test_malformed_existing_entry_tolerated(self):
        """plays.json is occasionally hand-edited; a non-dict entry must not crash."""
        merged = fetch_plays.merge_track_details(
            {"Track A": "oops"}, {"Track A": _details(likes=3)}, {},
            {"Track A": 100})
        self.assertEqual(merged["Track A"]["likes"], 3)


class TestRssTrackDetails(unittest.TestCase):
    def test_empty_fields_skipped(self):
        rss = fetch_plays._rss_track_details(
            [{"title": "T", "link": "", "artwork": "", "pub_date": ""}])
        self.assertEqual(rss, {})

    def test_keys_are_canonical(self):
        rss = fetch_plays._rss_track_details(
            [{"title": "  Track A  ", "link": "https://x"}])
        self.assertIn(fetch_plays._canon_key("track a"), rss)


class TestSumEngagement(unittest.TestCase):
    def test_sums_all_four_fields(self):
        totals = fetch_plays.sum_engagement({
            "A": _details(likes=10, reposts=2, comments=1, downloads=3),
            "B": _details(likes=5, reposts=1, comments=0, downloads=0),
        })
        self.assertEqual(totals, {"likes": 15, "reposts": 3, "comments": 1, "downloads": 3})

    def test_tolerates_malformed_entries_and_empty_map(self):
        self.assertEqual(fetch_plays.sum_engagement({}),
                         {"likes": 0, "reposts": 0, "comments": 0, "downloads": 0})
        totals = fetch_plays.sum_engagement({
            "A": "not-a-dict",
            "B": {"likes": "many", "reposts": None},
            "C": {"likes": 4},
        })
        self.assertEqual(totals["likes"], 4)
        self.assertEqual(totals["reposts"], 0)


# ─── fetch_soundcloud_all wiring ─────────────────────────────────────────────

class TestFetchSoundcloudAllEngagement(unittest.TestCase):
    @patch("fetch_plays._save_sc_client_id_cache")
    @patch("fetch_plays.fetch_soundcloud_profile", return_value={})
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss", return_value=[])
    @patch("fetch_plays.resolve_soundcloud_client_id", return_value=("cid", "scrape"))
    def test_success_populates_details_and_aggregate(self, _cid, _rss, mock_v2, _profile, _save):
        mock_v2.return_value = (
            {"Track A": 100, "Track B": 50},
            {"Track A": _details(likes=4, reposts=1, comments=0, downloads=2),
             "Track B": _details(likes=6, reposts=0, comments=3, downloads=0)},
        )
        sc_data, _, got = fetch_plays.fetch_soundcloud_all({"tracks": {}, "total_plays": 0})
        self.assertTrue(got)
        self.assertEqual(sc_data["track_details"]["Track A"]["likes"], 4)
        self.assertEqual(sc_data["engagement"],
                         {"likes": 10, "reposts": 1, "comments": 3, "downloads": 2})

    @patch("fetch_plays.fetch_soundcloud_profile", return_value={})
    @patch("fetch_plays.fetch_soundcloud_plays_v2", return_value=({}, {}))
    @patch("fetch_plays.fetch_soundcloud_rss", return_value=[])
    @patch("fetch_plays.resolve_soundcloud_client_id", return_value=(None, "scrape"))
    def test_api_failure_preserves_details_and_manual_totals(self, _cid, _rss, _v2, _profile):
        existing = {
            "tracks": {"Track A": 100},
            "total_plays": 100,
            "track_details": {"Track A": _details(likes=44)},
            "engagement": {"likes": 44, "reposts": 6, "comments": 2, "downloads": 10},
            "total_downloads": 3690,  # manual Insights key must survive untouched
        }
        sc_data, _, got = fetch_plays.fetch_soundcloud_all(existing)
        self.assertFalse(got)
        self.assertEqual(sc_data["fetch_status"], "api_failed_preserved")
        self.assertEqual(sc_data["track_details"], existing["track_details"])
        self.assertEqual(sc_data["engagement"], existing["engagement"])
        self.assertEqual(sc_data["total_downloads"], 3690)

    @patch("fetch_plays._save_sc_client_id_cache")
    @patch("fetch_plays.fetch_soundcloud_profile", return_value={})
    @patch("fetch_plays.fetch_soundcloud_plays_v2")
    @patch("fetch_plays.fetch_soundcloud_rss", return_value=[])
    @patch("fetch_plays.resolve_soundcloud_client_id", return_value=("cid", "scrape"))
    def test_pre_migration_data_without_track_details(self, _cid, _rss, mock_v2, _profile, _save):
        """The live plays.json predates track_details; the first successful run
        must populate it without crashing."""
        mock_v2.return_value = ({"Track A": 150}, {"Track A": _details(likes=9)})
        existing = {"tracks": {"Track A": 100}, "total_plays": 100}  # no track_details
        sc_data, _, got = fetch_plays.fetch_soundcloud_all(existing)
        self.assertTrue(got)
        self.assertEqual(sc_data["track_details"]["Track A"]["likes"], 9)
        self.assertEqual(sc_data["engagement"]["likes"], 9)


# ─── history.csv engagement columns + header migration ──────────────────────

LEGACY_HEADER = ("timestamp,soundcloud_total_plays,soundcloud_track_count,"
                 "spotify_total_streams,spotify_track_count,"
                 "apple_music_total_plays,apple_music_track_count")


def _row(ts, sc_total, eng=None):
    data = {
        "last_updated": ts,
        "soundcloud": {"total_plays": sc_total, "tracks": {}},
        "spotify": {"total_streams": 0, "tracks": {}},
        "apple_music": {"total_plays": 0, "tracks": {}},
    }
    if eng is not None:
        data["soundcloud"]["engagement"] = eng
    return data


class TestHistoryEngagementColumns(unittest.TestCase):
    def setUp(self):
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
        with open(fetch_plays.HISTORY_CSV) as f:
            return list(csv.DictReader(f))

    def test_fresh_file_gets_full_header(self):
        fetch_plays.append_history_csv(
            _row("2026-01-01T00:00:00Z", 100,
                 {"likes": 5, "reposts": 1, "comments": 0, "downloads": 2}))
        with open(fetch_plays.HISTORY_CSV) as f:
            header = f.readline().strip()
        self.assertEqual(header, ",".join(fetch_plays.HISTORY_FIELDNAMES))
        rows = self._read_rows()
        self.assertEqual(rows[0]["soundcloud_likes"], "5")
        self.assertEqual(rows[0]["soundcloud_downloads"], "2")

    def test_legacy_header_migrated_with_rows_intact(self):
        """The production file (CRLF terminators, canonical 7-column header) must
        be migrated in place: new header, old data rows byte-identical and
        readable by DictReader, appended row carries the engagement columns."""
        with open(fetch_plays.HISTORY_CSV, "w", newline="") as f:
            f.write(LEGACY_HEADER + "\r\n")
            f.write("2026-01-01T00:00:00Z,5000,40,10,5,20,7\r\n")

        fetch_plays.append_history_csv(
            _row("2026-01-02T00:00:00Z", 5100,
                 {"likes": 8, "reposts": 2, "comments": 1, "downloads": 0}))

        with open(fetch_plays.HISTORY_CSV, newline="") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(",".join(fetch_plays.HISTORY_FIELDNAMES) + "\r\n"))
        self.assertIn("2026-01-01T00:00:00Z,5000,40,10,5,20,7\r\n", raw)  # untouched

        rows = self._read_rows()
        self.assertEqual(len(rows), 2)
        # Old row: absent engagement columns read back as empty, plays intact.
        self.assertEqual(rows[0]["soundcloud_total_plays"], "5000")
        self.assertEqual(rows[0].get("soundcloud_likes") or "", "")
        # New row: engagement recorded, monotonic plays clamp still applies.
        self.assertEqual(rows[1]["soundcloud_likes"], "8")
        self.assertEqual(rows[1]["soundcloud_total_plays"], "5100")

    def test_unknown_legacy_header_left_alone(self):
        """The spotify_total_popularity-era header isn't the canonical legacy
        form — it must not be rewritten (status-quo positional append)."""
        odd_header = LEGACY_HEADER.replace("spotify_total_streams", "spotify_total_popularity")
        with open(fetch_plays.HISTORY_CSV, "w", newline="") as f:
            f.write(odd_header + "\r\n")
            f.write("2026-01-01T00:00:00Z,0,0,42,5,0,0\r\n")

        fetch_plays.append_history_csv(_row("2026-01-02T00:00:00Z", 10))

        with open(fetch_plays.HISTORY_CSV, newline="") as f:
            first = f.readline()
        self.assertEqual(first.strip(), odd_header)

    def test_already_migrated_header_is_noop(self):
        fetch_plays.append_history_csv(_row("2026-01-01T00:00:00Z", 100))
        with open(fetch_plays.HISTORY_CSV) as f:
            before = f.read()
        fetch_plays._migrate_history_header()
        with open(fetch_plays.HISTORY_CSV) as f:
            self.assertEqual(f.read(), before)

    def test_engagement_decrease_recorded_as_is(self):
        """No max-guard on engagement columns: a real decrease (unlikes) must be
        recorded honestly, unlike the play-count columns."""
        fetch_plays.append_history_csv(
            _row("2026-01-01T00:00:00Z", 100,
                 {"likes": 50, "reposts": 5, "comments": 3, "downloads": 9}))
        fetch_plays.append_history_csv(
            _row("2026-01-02T00:00:00Z", 100,
                 {"likes": 45, "reposts": 5, "comments": 3, "downloads": 9}))
        rows = self._read_rows()
        self.assertEqual(rows[1]["soundcloud_likes"], "45")  # NOT clamped to 50

    def test_missing_engagement_writes_zeros(self):
        fetch_plays.append_history_csv(_row("2026-01-01T00:00:00Z", 100))
        rows = self._read_rows()
        for col in ("soundcloud_likes", "soundcloud_reposts",
                    "soundcloud_comments", "soundcloud_downloads"):
            self.assertEqual(rows[0][col], "0")


if __name__ == "__main__":
    unittest.main()
