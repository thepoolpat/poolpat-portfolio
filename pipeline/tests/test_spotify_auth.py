"""Tests for spotify_auth module."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spotify_auth import generate_pkce_pair, build_auth_url, refresh_access_token


class TestPKCE(unittest.TestCase):
    def test_generate_pkce_pair_lengths(self):
        verifier, challenge = generate_pkce_pair()
        self.assertGreater(len(verifier), 40)
        self.assertGreater(len(challenge), 40)

    def test_generate_pkce_pair_uniqueness(self):
        pair1 = generate_pkce_pair()
        pair2 = generate_pkce_pair()
        self.assertNotEqual(pair1[0], pair2[0])

    def test_verifier_is_url_safe(self):
        verifier, _ = generate_pkce_pair()
        for char in verifier:
            self.assertIn(char, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


class TestBuildAuthURL(unittest.TestCase):
    def test_contains_required_params(self):
        url = build_auth_url("test_id", "http://localhost:8888/callback", "user-read-private", "challenge123")
        self.assertIn("client_id=test_id", url)
        self.assertIn("response_type=code", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("code_challenge=challenge123", url)
        self.assertIn("user-read-private", url)


class TestRefreshAccessToken(unittest.TestCase):
    @patch("spotify_auth.requests.post")
    def test_successful_refresh(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_access",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = refresh_access_token("client_id", "refresh_tok")
        self.assertEqual(result["access_token"], "new_access")

        call_data = mock_post.call_args[1]["data"]
        self.assertEqual(call_data["grant_type"], "refresh_token")
        self.assertEqual(call_data["client_id"], "client_id")
        self.assertEqual(call_data["refresh_token"], "refresh_tok")

    @patch("spotify_auth.requests.post")
    def test_token_rotation_warning(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = refresh_access_token("client_id", "old_refresh")
        self.assertEqual(result["refresh_token"], "new_refresh")


if __name__ == "__main__":
    unittest.main()
