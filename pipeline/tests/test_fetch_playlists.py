"""Tests for fetch_playlists.py.

Covers the four public functions individually:
- get_spotify_token: client_credentials auth, missing creds, HTTP failure
- spotify_get: 429 retry, generic HTTP error
- get_artist_tracks: dedup across album/single groups, partial failure
- find_playlists_for_track: nullability of search response
- enrich_with_playlistcheck: silent fallback to {}
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import requests

import fetch_playlists


def _resp(status=200, json_body=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.ok = status < 400
    r.json.return_value = json_body if json_body is not None else {}
    r.headers = headers or {}
    if status >= 400:
        err = requests.HTTPError(response=r)
        r.raise_for_status.side_effect = err
    else:
        r.raise_for_status = MagicMock()
    return r


# ─── get_spotify_token ───────────────────────────────────────────────────────

class TestGetSpotifyToken(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_creds_raises(self):
        with self.assertRaises(RuntimeError):
            fetch_playlists.get_spotify_token()

    @patch.dict(os.environ, {"SPOTIFY_CLIENT_ID": "id"}, clear=True)
    def test_missing_secret_raises(self):
        with self.assertRaises(RuntimeError):
            fetch_playlists.get_spotify_token()

    @patch.dict(os.environ, {"SPOTIFY_CLIENT_ID": "id", "SPOTIFY_CLIENT_SECRET": "secret"}, clear=True)
    @patch("fetch_playlists.requests.post")
    def test_success_returns_access_token(self, mock_post):
        mock_post.return_value = _resp(200, {"access_token": "abc123"})
        token = fetch_playlists.get_spotify_token()
        self.assertEqual(token, "abc123")

        # Verify HTTP basic auth used
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["auth"], ("id", "secret"))
        self.assertEqual(kwargs["data"], {"grant_type": "client_credentials"})

    @patch.dict(os.environ, {"SPOTIFY_CLIENT_ID": "id", "SPOTIFY_CLIENT_SECRET": "secret"}, clear=True)
    @patch("fetch_playlists.requests.post")
    def test_http_failure_raises_without_leaking_secret(self, mock_post):
        mock_post.return_value = _resp(401)
        with self.assertRaises(RuntimeError) as ctx:
            fetch_playlists.get_spotify_token()
        # Critical: error message must NOT include the secret
        self.assertNotIn("secret", str(ctx.exception))


# ─── spotify_get ─────────────────────────────────────────────────────────────

class TestSpotifyGet(unittest.TestCase):
    @patch("fetch_playlists.requests.get")
    def test_success(self, mock_get):
        mock_get.return_value = _resp(200, {"foo": "bar"})
        result = fetch_playlists.spotify_get("/foo", "tok")
        self.assertEqual(result, {"foo": "bar"})

    @patch("fetch_playlists.time.sleep")
    @patch("fetch_playlists.requests.get")
    def test_429_retries_after_header(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            _resp(429, headers={"Retry-After": "2"}),
            _resp(200, {"ok": True}),
        ]
        result = fetch_playlists.spotify_get("/foo", "tok")
        self.assertEqual(result, {"ok": True})
        mock_sleep.assert_called_once_with(2)

    @patch("fetch_playlists.time.sleep")
    @patch("fetch_playlists.requests.get")
    def test_429_default_retry_after_when_header_missing(self, mock_get, mock_sleep):
        mock_get.side_effect = [_resp(429), _resp(200, {"ok": True})]
        fetch_playlists.spotify_get("/foo", "tok")
        mock_sleep.assert_called_once_with(5)

    @patch("fetch_playlists.requests.get")
    def test_500_raises(self, mock_get):
        mock_get.return_value = _resp(500)
        with self.assertRaises(requests.HTTPError):
            fetch_playlists.spotify_get("/foo", "tok")


# ─── get_artist_tracks ───────────────────────────────────────────────────────

class TestGetArtistTracks(unittest.TestCase):
    @patch("fetch_playlists.spotify_get")
    def test_dedupes_across_album_and_single(self, mock_get):
        # Albums response (group=album)
        albums_resp = {"items": [{"id": "alb1"}]}
        # Tracks on alb1
        alb1_tracks = {"items": [{"id": "trk1", "name": "Song One"}]}
        # Singles response (group=single) — same track appears here too
        singles_resp = {"items": [{"id": "alb2"}]}
        alb2_tracks = {"items": [
            {"id": "trk1", "name": "Song One (Single)"},  # dup id, ignored
            {"id": "trk2", "name": "Song Two"},
        ]}
        mock_get.side_effect = [albums_resp, alb1_tracks, singles_resp, alb2_tracks]

        tracks = fetch_playlists.get_artist_tracks("tok")
        ids = [t["id"] for t in tracks]
        self.assertEqual(ids, ["trk1", "trk2"])  # dedup'd

    @patch("fetch_playlists.spotify_get")
    def test_album_group_failure_continues_to_single(self, mock_get):
        """A 404/500 on the album group must not crash the whole fetch."""
        err_resp = MagicMock(); err_resp.status_code = 500
        err = requests.HTTPError(response=err_resp)

        single_albums = {"items": [{"id": "alb1"}]}
        single_tracks = {"items": [{"id": "trk1", "name": "Solo"}]}
        mock_get.side_effect = [err, single_albums, single_tracks]

        tracks = fetch_playlists.get_artist_tracks("tok")
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]["id"], "trk1")

    @patch("fetch_playlists.spotify_get")
    def test_track_with_no_id_skipped(self, mock_get):
        albums_resp = {"items": [{"id": "alb1"}]}
        alb_tracks = {"items": [
            {"id": None, "name": "Local file"},
            {"id": "trk1", "name": "Real"},
        ]}
        empty_singles = {"items": []}
        mock_get.side_effect = [albums_resp, alb_tracks, empty_singles]

        tracks = fetch_playlists.get_artist_tracks("tok")
        self.assertEqual([t["id"] for t in tracks], ["trk1"])


# ─── find_playlists_for_track ────────────────────────────────────────────────

class TestFindPlaylistsForTrack(unittest.TestCase):
    @patch("fetch_playlists.spotify_get")
    def test_success_returns_normalized_playlists(self, mock_get):
        mock_get.return_value = {"playlists": {"items": [{
            "id": "pl1",
            "name": "Chill Vibes",
            "external_urls": {"spotify": "https://open.spotify.com/playlist/pl1"},
            "owner": {"display_name": "Curator"},
        }]}}

        result = fetch_playlists.find_playlists_for_track("trk1", "Song One", "tok")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["playlist_id"], "pl1")
        self.assertEqual(result[0]["name"], "Chill Vibes")
        self.assertEqual(result[0]["track_id"], "trk1")
        self.assertEqual(result[0]["owner"], "Curator")

    @patch("fetch_playlists.spotify_get")
    def test_null_playlist_in_items_skipped(self, mock_get):
        """Spotify search occasionally returns null entries — must not crash."""
        mock_get.return_value = {"playlists": {"items": [None, {"id": "pl1", "name": "ok"}]}}
        result = fetch_playlists.find_playlists_for_track("trk1", "Song", "tok")
        self.assertEqual(len(result), 1)

    @patch("fetch_playlists.spotify_get")
    def test_null_items_returns_empty(self, mock_get):
        mock_get.return_value = {"playlists": {"items": None}}
        result = fetch_playlists.find_playlists_for_track("trk1", "Song", "tok")
        self.assertEqual(result, [])

    @patch("fetch_playlists.spotify_get")
    def test_missing_owner_does_not_crash(self, mock_get):
        mock_get.return_value = {"playlists": {"items": [{
            "id": "pl1", "name": "x", "external_urls": None, "owner": None,
        }]}}
        result = fetch_playlists.find_playlists_for_track("trk1", "Song", "tok")
        self.assertEqual(result[0]["owner"], None)
        self.assertEqual(result[0]["spotify_url"], None)

    @patch("fetch_playlists.spotify_get")
    def test_search_http_error_returns_empty(self, mock_get):
        err_resp = MagicMock(); err_resp.status_code = 400
        mock_get.side_effect = requests.HTTPError(response=err_resp)
        result = fetch_playlists.find_playlists_for_track("trk1", "Song", "tok")
        self.assertEqual(result, [])


# ─── enrich_with_playlistcheck ───────────────────────────────────────────────

class TestEnrichWithPlaylistcheck(unittest.TestCase):
    @patch("fetch_playlists.requests.get")
    def test_success_returns_data(self, mock_get):
        mock_get.return_value = _resp(200, {"followers": 500, "rank": 12})
        result = fetch_playlists.enrich_with_playlistcheck("pl1", "key")
        self.assertEqual(result, {"followers": 500, "rank": 12})

        kwargs = mock_get.call_args.kwargs
        self.assertEqual(kwargs["headers"]["x-rapidapi-key"], "key")
        self.assertEqual(kwargs["params"], {"playlist_id": "pl1"})

    @patch("fetch_playlists.requests.get")
    def test_http_error_returns_empty(self, mock_get):
        mock_get.return_value = _resp(429)
        result = fetch_playlists.enrich_with_playlistcheck("pl1", "key")
        self.assertEqual(result, {})

    @patch("fetch_playlists.requests.get")
    def test_network_error_swallowed(self, mock_get):
        """Any exception from the playlistcheck call must not break the pipeline."""
        mock_get.side_effect = Exception("network")
        result = fetch_playlists.enrich_with_playlistcheck("pl1", "key")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
