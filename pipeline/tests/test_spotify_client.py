"""Tests for spotify_client module."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spotify_client import SpotifyClient


def _mock_json_response(status_code, body):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.reason = "OK" if status_code < 400 else "Error"
    resp.headers = {}
    return resp


class TestSpotifyClientUser(unittest.TestCase):
    @patch("spotify_client.requests.Session")
    def test_get_current_user(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        session.request.return_value = _mock_json_response(200, {
            "display_name": "Poolpat",
            "product": "premium",
        })

        client = SpotifyClient("test_token")
        user = client.get_current_user()
        self.assertEqual(user["display_name"], "Poolpat")

    @patch("spotify_client.requests.Session")
    def test_get_top_tracks(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        session.request.return_value = _mock_json_response(200, {
            "items": [{"name": "Track A"}, {"name": "Track B"}],
            "next": None,
        })

        client = SpotifyClient("test_token")
        tracks = client.get_top_tracks("short_term", 10)
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0]["name"], "Track A")


class TestSpotifyClientPagination(unittest.TestCase):
    @patch("spotify_client.requests.Session")
    def test_pagination_follows_next(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        page1 = _mock_json_response(200, {
            "items": [{"name": f"Track {i}"} for i in range(50)],
            "next": "https://api.spotify.com/v1/me/playlists?offset=50",
        })
        page2 = _mock_json_response(200, {
            "items": [{"name": f"Track {i}"} for i in range(50, 75)],
            "next": None,
        })
        session.request.side_effect = [page1, page2]

        client = SpotifyClient("test_token")
        playlists = client.get_playlists(limit=100)
        self.assertEqual(len(playlists), 75)


class TestSpotifyClientBatching(unittest.TestCase):
    @patch("spotify_client.requests.Session")
    def test_get_tracks_batches_by_50(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        ids = [f"id_{i}" for i in range(120)]

        def side_effect(method, url, **kwargs):
            batch_ids = kwargs.get("params", {}).get("ids", "").split(",")
            return _mock_json_response(200, {
                "tracks": [{"id": tid, "name": f"Track {tid}"} for tid in batch_ids]
            })

        session.request.side_effect = side_effect

        client = SpotifyClient("test_token")
        tracks = client.get_tracks(ids)
        self.assertEqual(len(tracks), 120)
        self.assertEqual(session.request.call_count, 3)  # 50 + 50 + 20


class TestSpotifyClientRetry(unittest.TestCase):
    @patch("spotify_client.time.sleep")
    @patch("spotify_client.requests.Session")
    def test_retry_on_429(self, mock_session_cls, mock_sleep):
        session = MagicMock()
        mock_session_cls.return_value = session

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {"error": {"message": "Rate limited"}}
        rate_limited.reason = "Too Many Requests"
        rate_limited.headers = {"Retry-After": "1"}

        success = _mock_json_response(200, {"display_name": "Poolpat"})

        session.request.side_effect = [rate_limited, success]

        client = SpotifyClient("test_token")
        result = client.get_current_user()
        self.assertEqual(result["display_name"], "Poolpat")
        mock_sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
