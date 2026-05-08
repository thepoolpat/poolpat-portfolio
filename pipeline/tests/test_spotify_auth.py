"""Tests for spotify_auth module."""

import sys
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spotify_auth import (
    generate_pkce_pair,
    build_auth_url,
    refresh_access_token,
    exchange_code,
)


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

    @patch.dict(os.environ, {}, clear=True)
    @patch("spotify_auth.subprocess.run")
    @patch("spotify_auth.requests.post")
    def test_token_rotation_warning(self, mock_post, mock_run):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = refresh_access_token("client_id", "old_refresh")
        self.assertEqual(result["refresh_token"], "new_refresh")

        # Rotation must shell out to `gh secret set` — verify without leaking
        # the new token through assertion error messages.
        self.assertEqual(mock_run.call_count, 1)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[:4], ["gh", "secret", "set", "SPOTIFY_REFRESH_TOKEN"])

    @patch.dict(os.environ, {}, clear=True)
    @patch("spotify_auth.subprocess.run")
    @patch("spotify_auth.requests.post")
    def test_no_rotation_skips_gh_secret_set(self, mock_post, mock_run):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_access",
            "expires_in": 3600,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        refresh_access_token("client_id", "same_refresh")
        mock_run.assert_not_called()

    @patch("spotify_auth.subprocess.run")
    @patch("spotify_auth.requests.post")
    def test_rotation_writes_to_github_env(self, mock_post, mock_run):
        """Per CLAUDE.md: rotation must propagate via $GITHUB_ENV for the same job."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            gh_env_path = f.name
        try:
            with patch.dict(os.environ, {"GITHUB_ENV": gh_env_path}, clear=True):
                resp = MagicMock()
                resp.status_code = 200
                resp.raise_for_status = MagicMock()
                resp.json.return_value = {
                    "access_token": "new_access",
                    "refresh_token": "rotated_secret_value",
                    "expires_in": 3600,
                }
                mock_post.return_value = resp
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

                refresh_access_token("cid", "old_rt")

            with open(gh_env_path) as f:
                contents = f.read()
            self.assertIn("SPOTIFY_REFRESH_TOKEN=rotated_secret_value", contents)
        finally:
            os.unlink(gh_env_path)

    @patch.dict(os.environ, {}, clear=True)
    @patch("spotify_auth.subprocess.run")
    @patch("spotify_auth.requests.post")
    def test_rotation_emits_add_mask_directive(self, mock_post, mock_run):
        """The new refresh token must be masked in GH Actions logs BEFORE
        any other side effect that could surface it (env file, subprocess, etc.)."""
        import io
        from contextlib import redirect_stdout

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "access_token": "a",
            "refresh_token": "rotated_value_xyz",
            "expires_in": 3600,
        }
        mock_post.return_value = resp
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        captured = io.StringIO()
        with redirect_stdout(captured):
            refresh_access_token("cid", "old_rt")

        output = captured.getvalue()
        self.assertIn("::add-mask::rotated_value_xyz", output)

    @patch.dict(os.environ, {}, clear=True)
    @patch("spotify_auth.subprocess.run")
    @patch("spotify_auth.requests.post")
    def test_gh_secret_set_failure_does_not_raise(self, mock_post, mock_run):
        """When `gh secret set` fails (e.g. missing GH_PAT), the refresh must still
        return successfully — the access_token is still valid for this run."""
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "access_token": "a",
            "refresh_token": "rotated",
            "expires_in": 3600,
        }
        mock_post.return_value = resp
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")

        result = refresh_access_token("cid", "old_rt")
        self.assertEqual(result["access_token"], "a")

    @patch.dict(os.environ, {}, clear=True)
    @patch("spotify_auth.subprocess.run")
    @patch("spotify_auth.requests.post")
    def test_rotation_does_not_leak_token_in_subprocess_args_on_failure(
        self, mock_post, mock_run,
    ):
        """If subprocess fails, the error log must NOT include the token value
        (which lives in --body <token> arg). The implementation explicitly avoids
        result.stderr / capture_output leaks."""
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "access_token": "a",
            "refresh_token": "SUPER_SECRET_TOKEN_XYZ",
            "expires_in": 3600,
        }
        mock_post.return_value = resp
        mock_run.return_value = MagicMock(returncode=1, stdout="error", stderr="error")

        import io
        from contextlib import redirect_stderr, redirect_stdout
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            refresh_access_token("cid", "old_rt")

        # The token must not appear in stderr (which is where errors are logged)
        self.assertNotIn("SUPER_SECRET_TOKEN_XYZ", err.getvalue())

    @patch("spotify_auth.requests.post")
    def test_refresh_http_error_propagates(self, mock_post):
        """A 401 from the token endpoint must raise — caller can't recover silently."""
        resp = MagicMock()
        resp.status_code = 401
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
        mock_post.return_value = resp

        with self.assertRaises(requests.HTTPError):
            refresh_access_token("cid", "rt")


class TestExchangeCode(unittest.TestCase):
    @patch("spotify_auth.requests.post")
    def test_success_returns_tokens(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "expires_in": 3600,
        }
        mock_post.return_value = resp

        result = exchange_code("cid", "auth_code", "verifier", "http://localhost:8888/callback")
        self.assertEqual(result["refresh_token"], "rt")

        data = mock_post.call_args.kwargs["data"]
        self.assertEqual(data["grant_type"], "authorization_code")
        self.assertEqual(data["code"], "auth_code")
        self.assertEqual(data["code_verifier"], "verifier")
        self.assertEqual(data["redirect_uri"], "http://localhost:8888/callback")
        self.assertEqual(data["client_id"], "cid")

    @patch("spotify_auth.requests.post")
    def test_http_error_raises(self, mock_post):
        """Bad authorization codes (e.g. expired) return 400 — must raise."""
        resp = MagicMock()
        resp.status_code = 400
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
        mock_post.return_value = resp

        with self.assertRaises(requests.HTTPError):
            exchange_code("cid", "bad_code", "verifier", "http://localhost:8888/callback")


if __name__ == "__main__":
    unittest.main()
