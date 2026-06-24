"""Tests for spotify_client module."""

import unittest
from unittest.mock import patch, MagicMock

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

    @patch("spotify_client.time.sleep")
    @patch("spotify_client.requests.Session")
    def test_retry_exhaustion_raises(self, mock_session_cls, mock_sleep):
        """After MAX_RETRIES consecutive 429s the client must give up and raise."""
        from spotify_errors import SpotifyRateLimitError

        session = MagicMock()
        mock_session_cls.return_value = session

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {"error": {"message": "Rate limited"}}
        rate_limited.reason = "Too Many Requests"
        rate_limited.headers = {"Retry-After": "1"}

        # MAX_RETRIES = 3, so the client tries 4 times total before raising
        session.request.return_value = rate_limited

        client = SpotifyClient("test_token")
        with self.assertRaises(SpotifyRateLimitError):
            client.get_current_user()
        # 3 sleeps happen on attempts 0..2; attempt 3 raises without sleeping
        self.assertEqual(mock_sleep.call_count, 3)

    @patch("spotify_client.time.sleep")
    @patch("spotify_client.requests.Session")
    def test_retry_after_capped_at_30s(self, mock_session_cls, mock_sleep):
        """A hostile/buggy Retry-After must not block the worker forever."""
        session = MagicMock()
        mock_session_cls.return_value = session

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {"error": {"message": "Rate limited"}}
        rate_limited.reason = "Too Many Requests"
        rate_limited.headers = {"Retry-After": "9999"}

        success = _mock_json_response(200, {"display_name": "Poolpat"})
        session.request.side_effect = [rate_limited, success]

        client = SpotifyClient("test_token")
        client.get_current_user()
        mock_sleep.assert_called_once_with(30)

    @patch("spotify_client.requests.Session")
    def test_204_no_content_returns_none(self, mock_session_cls):
        """Endpoints like /me/player return 204 when nothing is playing."""
        session = MagicMock()
        mock_session_cls.return_value = session

        no_content = MagicMock()
        no_content.status_code = 204
        session.request.return_value = no_content

        client = SpotifyClient("test_token")
        self.assertIsNone(client.get_playback_state())


class TestSpotifyClientRefresh(unittest.TestCase):
    @patch("spotify_client.requests.Session")
    def test_401_without_refresh_credentials_raises(self, mock_session_cls):
        """Without a refresh_token there is no way to recover from 401."""
        from spotify_errors import SpotifyAuthError

        session = MagicMock()
        mock_session_cls.return_value = session

        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.json.return_value = {"error": {"message": "Unauthorized"}}
        unauthorized.reason = "Unauthorized"
        unauthorized.headers = {}
        session.request.return_value = unauthorized

        client = SpotifyClient("expired_token")  # no client_id, no refresh_token
        with self.assertRaises(SpotifyAuthError):
            client.get_current_user()

    @patch("spotify_client.requests.Session")
    def test_401_triggers_refresh_then_succeeds(self, mock_session_cls):
        """Happy path: 401 → refresh_access_token → retry → success."""
        session = MagicMock()
        mock_session_cls.return_value = session

        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.json.return_value = {"error": {"message": "Unauthorized"}}
        unauthorized.reason = "Unauthorized"
        unauthorized.headers = {}

        success = _mock_json_response(200, {"display_name": "Poolpat"})
        session.request.side_effect = [unauthorized, success]

        # Mock spotify_auth.refresh_access_token before _refresh imports it
        import sys as _sys
        from unittest.mock import MagicMock as _MM
        fake_auth = _MM()
        fake_auth.refresh_access_token = _MM(return_value={"access_token": "new_token"})
        _sys.modules["spotify_auth"] = fake_auth

        try:
            client = SpotifyClient("expired", client_id="cid", refresh_token="rt")
            result = client.get_current_user()
            self.assertEqual(result["display_name"], "Poolpat")
            fake_auth.refresh_access_token.assert_called_once_with("cid", "rt")
            # New token applied to session header
            self.assertEqual(client._token, "new_token")
            self.assertEqual(
                session.headers.__setitem__.call_args[0],
                ("Authorization", "Bearer new_token"),
            )
        finally:
            del _sys.modules["spotify_auth"]

    @patch("spotify_client.requests.Session")
    def test_refresh_rotates_refresh_token_when_returned(self, mock_session_cls):
        """If Spotify rotates the refresh_token, the client must store the new one."""
        session = MagicMock()
        mock_session_cls.return_value = session

        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.json.return_value = {"error": {"message": "Unauthorized"}}
        unauthorized.reason = "Unauthorized"
        unauthorized.headers = {}

        success = _mock_json_response(200, {"display_name": "Poolpat"})
        session.request.side_effect = [unauthorized, success]

        import sys as _sys
        from unittest.mock import MagicMock as _MM
        fake_auth = _MM()
        fake_auth.refresh_access_token = _MM(return_value={
            "access_token": "new_token",
            "refresh_token": "rotated_rt",
        })
        _sys.modules["spotify_auth"] = fake_auth

        try:
            client = SpotifyClient("expired", client_id="cid", refresh_token="old_rt")
            client.get_current_user()
            self.assertEqual(client._refresh_token, "rotated_rt")
        finally:
            del _sys.modules["spotify_auth"]

    @patch("spotify_client.requests.Session")
    def test_repeated_401_after_refresh_raises(self, mock_session_cls):
        """If the refresh somehow yields another 401, surface the error (don't loop)."""
        from spotify_errors import SpotifyAuthError

        session = MagicMock()
        mock_session_cls.return_value = session

        unauthorized = MagicMock()
        unauthorized.status_code = 401
        unauthorized.json.return_value = {"error": {"message": "Unauthorized"}}
        unauthorized.reason = "Unauthorized"
        unauthorized.headers = {}
        session.request.return_value = unauthorized  # always 401

        import sys as _sys
        from unittest.mock import MagicMock as _MM
        fake_auth = _MM()
        fake_auth.refresh_access_token = _MM(return_value={"access_token": "still_bad"})
        _sys.modules["spotify_auth"] = fake_auth

        try:
            client = SpotifyClient("expired", client_id="cid", refresh_token="rt")
            with self.assertRaises(SpotifyAuthError):
                client.get_current_user()
            # Refresh attempted exactly once — no infinite loop
            self.assertEqual(fake_auth.refresh_access_token.call_count, 1)
        finally:
            del _sys.modules["spotify_auth"]


class TestSpotifyClientServerError(unittest.TestCase):
    """Spotify occasionally 500s under load. The client must treat a 5xx as a
    transient fault: retry with bounded backoff and succeed if a later attempt
    returns 200; only raise once retries are exhausted — and on exhaustion it
    must raise SpotifyServerError, never silently return the error body."""

    @staticmethod
    def _server_error():
        err = MagicMock()
        err.status_code = 500
        err.json.return_value = {"error": {"status": 500, "message": "Server error"}}
        err.reason = "Internal Server Error"
        err.headers = {}
        return err

    @patch("spotify_client.time.sleep")
    @patch("spotify_client.requests.Session")
    def test_retry_on_500_then_succeeds(self, mock_session_cls, mock_sleep):
        """500 → backoff → retry → 200 returns the success body."""
        session = MagicMock()
        mock_session_cls.return_value = session

        success = _mock_json_response(200, {"display_name": "Poolpat"})
        session.request.side_effect = [self._server_error(), success]

        client = SpotifyClient("test_token")
        result = client.get_current_user()

        # The retry's 200 body is what comes back — not the 500 error body.
        self.assertEqual(result["display_name"], "Poolpat")
        self.assertNotIn("error", result)
        # A second attempt actually happened.
        self.assertEqual(session.request.call_count, 2)
        # Backoff occurred between attempts (bounded; we don't pin the value).
        self.assertTrue(mock_sleep.called)

    @patch("spotify_client.time.sleep")
    @patch("spotify_client.requests.Session")
    def test_500_retry_exhaustion_raises(self, mock_session_cls, mock_sleep):
        """All attempts 500 → raise SpotifyServerError; do NOT return the body."""
        from spotify_errors import SpotifyServerError

        session = MagicMock()
        mock_session_cls.return_value = session
        session.request.return_value = self._server_error()

        client = SpotifyClient("test_token")
        with self.assertRaises(SpotifyServerError) as ctx:
            client.get_current_user()

        # The error carries the 500 status, not a 2xx body leaked back to the caller.
        self.assertEqual(ctx.exception.status_code, 500)
        # It genuinely retried before giving up (more than the single first try).
        self.assertGreater(session.request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
