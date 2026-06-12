"""Tests for the monotonic invariant in fetch_plays.

Streaming counts are MONOTONICALLY INCREASING. A failed fetch (zeros, missing
keys, malformed values) must NEVER reduce a previously recorded count. Once
this invariant slips, history is wrong forever — these tests are the only
safety net.
"""

import unicodedata
import unittest

from fetch_plays import monotonic_merge_tracks, monotonic_total

# The same accented title in both Unicode forms — composed (NFC) and
# decomposed (NFD). They print identically but are different dict keys.
NFC_TITLE = unicodedata.normalize("NFC", "Déjà 30 Piges")
NFD_TITLE = unicodedata.normalize("NFD", "Déjà 30 Piges")


class TestUnicodeNormalizedMerge(unittest.TestCase):
    """NFC/NFD variants of one track must merge to a single NFC row.

    Insights exports and the public-page scrape disagree on normalization for
    accented titles; before normalization the merge carried both forms forever
    as duplicate rows."""

    def test_titles_differ_as_raw_keys(self):
        # Guard: if this fails the fixture is meaningless.
        self.assertNotEqual(NFC_TITLE, NFD_TITLE)

    def test_nfd_existing_merges_with_nfc_fetched(self):
        merged = monotonic_merge_tracks({NFD_TITLE: 100}, {NFC_TITLE: 150})
        self.assertEqual(merged, {NFC_TITLE: 150})

    def test_monotonic_across_forms_lower_fetch_keeps_existing(self):
        merged = monotonic_merge_tracks({NFD_TITLE: 500}, {NFC_TITLE: 100})
        self.assertEqual(merged, {NFC_TITLE: 500})

    def test_pre_existing_duplicate_rows_collapse_to_max(self):
        # Data written before the fix can hold BOTH forms; merging must
        # collapse them even when the fetch is empty.
        merged = monotonic_merge_tracks({NFD_TITLE: 1355, NFC_TITLE: 1360}, {})
        self.assertEqual(merged, {NFC_TITLE: 1360})

    def test_new_nfd_track_is_stored_as_nfc(self):
        merged = monotonic_merge_tracks({}, {NFD_TITLE: 50})
        self.assertEqual(merged, {NFC_TITLE: 50})

    def test_unaccented_titles_unaffected(self):
        merged = monotonic_merge_tracks({"a": 100}, {"b": 50})
        self.assertEqual(merged, {"a": 100, "b": 50})

    def test_collapse_ignores_non_numeric_duplicate(self):
        merged = monotonic_merge_tracks({NFD_TITLE: None, NFC_TITLE: 70}, {})
        self.assertEqual(merged, {NFC_TITLE: 70})


class TestMonotonicMergeTracks(unittest.TestCase):
    def test_fetched_higher_than_existing_wins(self):
        merged = monotonic_merge_tracks({"a": 100}, {"a": 150})
        self.assertEqual(merged, {"a": 150})

    def test_fetched_lower_than_existing_does_not_decrease(self):
        merged = monotonic_merge_tracks({"a": 500}, {"a": 100})
        self.assertEqual(merged["a"], 500)

    def test_fetched_equal_keeps_value(self):
        merged = monotonic_merge_tracks({"a": 42}, {"a": 42})
        self.assertEqual(merged["a"], 42)

    def test_zero_fetched_preserves_existing(self):
        merged = monotonic_merge_tracks({"a": 100}, {"a": 0})
        self.assertEqual(merged["a"], 100)

    def test_negative_fetched_preserves_existing(self):
        merged = monotonic_merge_tracks({"a": 100}, {"a": -5})
        self.assertEqual(merged["a"], 100)

    def test_none_fetched_preserves_existing(self):
        merged = monotonic_merge_tracks({"a": 100}, {"a": None})
        self.assertEqual(merged["a"], 100)

    def test_non_numeric_fetched_preserves_existing(self):
        merged = monotonic_merge_tracks({"a": 100}, {"a": "bogus"})
        self.assertEqual(merged["a"], 100)

    def test_existing_track_missing_from_fetch_is_kept(self):
        merged = monotonic_merge_tracks({"a": 100, "b": 200}, {"a": 150})
        self.assertEqual(merged, {"a": 150, "b": 200})

    def test_new_track_in_fetch_is_added(self):
        merged = monotonic_merge_tracks({"a": 100}, {"b": 50})
        self.assertEqual(merged, {"a": 100, "b": 50})

    def test_empty_fetch_preserves_everything(self):
        existing = {"a": 100, "b": 200, "c": 300}
        merged = monotonic_merge_tracks(existing, {})
        self.assertEqual(merged, existing)

    def test_empty_existing_takes_fetched(self):
        merged = monotonic_merge_tracks({}, {"a": 50, "b": 75})
        self.assertEqual(merged, {"a": 50, "b": 75})

    def test_existing_zero_replaced_by_positive_fetch(self):
        # New release with placeholder 0 → first real count from API should win.
        merged = monotonic_merge_tracks({"a": 0}, {"a": 10})
        self.assertEqual(merged["a"], 10)

    def test_existing_none_treated_as_zero(self):
        merged = monotonic_merge_tracks({"a": None}, {"a": 10})
        self.assertEqual(merged["a"], 10)

    def test_existing_string_value_does_not_crash_merge(self):
        # plays.json is hand-edited for AM/SP manual totals — a stray string
        # must not raise TypeError in max(); the fetched number wins.
        merged = monotonic_merge_tracks({"a": "500"}, {"a": 100})
        self.assertEqual(merged["a"], 100)

    def test_existing_string_value_kept_when_not_fetched(self):
        # Untouched existing entries pass through verbatim, even if malformed.
        merged = monotonic_merge_tracks({"a": "500", "b": 10}, {"b": 20})
        self.assertEqual(merged, {"a": "500", "b": 20})

    def test_does_not_mutate_existing(self):
        existing = {"a": 100}
        monotonic_merge_tracks(existing, {"a": 200, "b": 50})
        self.assertEqual(existing, {"a": 100})

    def test_float_fetched_higher_wins(self):
        merged = monotonic_merge_tracks({"a": 100}, {"a": 150.5})
        self.assertEqual(merged["a"], 150.5)

    def test_realistic_partial_failure(self):
        # API returned data for some tracks, dropped others. The dropped ones
        # MUST keep their prior counts — this is the load-bearing scenario.
        existing = {"track1": 1000, "track2": 2000, "track3": 3000}
        fetched = {"track1": 1100, "track2": 0}  # track3 missing, track2 zero
        merged = monotonic_merge_tracks(existing, fetched)
        self.assertEqual(merged["track1"], 1100)
        self.assertEqual(merged["track2"], 2000)
        self.assertEqual(merged["track3"], 3000)


class TestMonotonicTotal(unittest.TestCase):
    def test_existing_higher_wins(self):
        self.assertEqual(monotonic_total(500, 100), 500)

    def test_computed_higher_wins(self):
        self.assertEqual(monotonic_total(100, 500), 500)

    def test_equal_returns_same(self):
        self.assertEqual(monotonic_total(100, 100), 100)

    def test_none_existing_treated_as_zero(self):
        self.assertEqual(monotonic_total(None, 100), 100)

    def test_none_computed_treated_as_zero(self):
        self.assertEqual(monotonic_total(100, None), 100)

    def test_both_none_returns_zero(self):
        self.assertEqual(monotonic_total(None, None), 0)

    def test_both_zero_returns_zero(self):
        self.assertEqual(monotonic_total(0, 0), 0)


if __name__ == "__main__":
    unittest.main()
