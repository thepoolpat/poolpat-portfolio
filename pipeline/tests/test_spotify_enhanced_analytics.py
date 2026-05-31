"""Tests for the pure keyword helpers in spotify_enhanced_analytics.

`_detect_mood` and `_match_project_to_artist` are the only deterministic,
side-effect-free pieces of EnhancedSpotifyAnalytics — everything else touches
SQLite, the Spotify session, or the filesystem. EnhancedSpotifyAnalytics.__init__
does heavy I/O (loads creds, opens a DB, prints a banner), so we construct the
instance via __new__ to bypass it and set only the attributes the methods read.

  - _detect_mood(artist_name) reads NO instance state (keyword table is local).
  - _match_project_to_artist(artist_name) reads self.portfolio_data["projects"].
"""

import unittest

from spotify_enhanced_analytics import EnhancedSpotifyAnalytics


def _bare_instance(portfolio_data=None):
    """An EnhancedSpotifyAnalytics with __init__ skipped (no creds/DB/session)."""
    inst = EnhancedSpotifyAnalytics.__new__(EnhancedSpotifyAnalytics)
    inst.portfolio_data = portfolio_data if portfolio_data is not None else {}
    return inst


class TestDetectMood(unittest.TestCase):
    def setUp(self):
        self.a = _bare_instance()

    def test_chill_keyword(self):
        self.assertEqual(self.a._detect_mood("Lo-Fi Study Beats"), "chill")
        self.assertEqual(self.a._detect_mood("Ambient Dreams"), "chill")

    def test_energetic_keyword(self):
        self.assertEqual(self.a._detect_mood("Hard Rock Heroes"), "energetic")
        self.assertEqual(self.a._detect_mood("EDM Anthems"), "energetic")

    def test_melancholy_keyword(self):
        self.assertEqual(self.a._detect_mood("Acoustic Sessions"), "melancholy")
        self.assertEqual(self.a._detect_mood("A Sad Ballad"), "melancholy")

    def test_focus_keyword(self):
        self.assertEqual(self.a._detect_mood("Classical Piano"), "focus")
        self.assertEqual(self.a._detect_mood("Smooth Jazz Trio"), "focus")

    def test_case_insensitive(self):
        # Matching is done on the lowercased name.
        self.assertEqual(self.a._detect_mood("CHILL WAVE"), "chill")

    def test_no_keyword_falls_back_to_general(self):
        self.assertEqual(self.a._detect_mood("The Mystery Artist"), "general")
        self.assertEqual(self.a._detect_mood(""), "general")


class TestMatchProjectToArtist(unittest.TestCase):
    def test_matches_when_project_name_is_substring_of_artist(self):
        a = _bare_instance({"projects": [{"name": "Poolpat"}]})
        self.assertEqual(a._match_project_to_artist("Poolpat Live"), "Poolpat")

    def test_matches_when_artist_is_substring_of_project_name(self):
        a = _bare_instance({"projects": [{"name": "Poolpat Portfolio Site"}]})
        # artist_lower ("poolpat") is contained in the project name.
        self.assertEqual(a._match_project_to_artist("Poolpat"), "Poolpat Portfolio Site")

    def test_no_match_returns_spontaneous(self):
        a = _bare_instance({"projects": [{"name": "Poolpat"}]})
        self.assertEqual(a._match_project_to_artist("Some Other Band"), "spontaneous")

    def test_no_projects_returns_spontaneous(self):
        a = _bare_instance({})
        self.assertEqual(a._match_project_to_artist("Anything"), "spontaneous")

    def test_first_matching_project_wins(self):
        a = _bare_instance({"projects": [{"name": "poolpat"}, {"name": "poolpat-two"}]})
        self.assertEqual(a._match_project_to_artist("poolpat"), "poolpat")


if __name__ == "__main__":
    unittest.main()
