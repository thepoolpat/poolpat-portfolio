"""Tests for spotify_errors module."""

import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spotify_errors import (
    SpotifyAuthError,
    SpotifyError,
    SpotifyNotFoundError,
    SpotifyRateLimitError,
    SpotifyServerError,
    raise_for_status,
)


class TestRaiseForStatus(unittest.TestCase):
    def _mock_response(self, status_code, json_body=None, headers=None, reason="Error"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.reason = reason
        resp.headers = headers or {}
        if json_body is not None:
            resp.json.return_value = json_body
        else:
            resp.json.side_effect = ValueError("No JSON")
        return resp

    def test_2xx_no_error(self):
        resp = self._mock_response(200)
        raise_for_status(resp)

    def test_401_raises_auth_error(self):
        resp = self._mock_response(401, {"error": {"message": "Token expired"}})
        with self.assertRaises(SpotifyAuthError) as ctx:
            raise_for_status(resp)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Token expired", ctx.exception.message)

    def test_429_raises_rate_limit_with_retry_after(self):
        resp = self._mock_response(429, {"error": {"message": "Too many requests"}}, headers={"Retry-After": "5"})
        with self.assertRaises(SpotifyRateLimitError) as ctx:
            raise_for_status(resp)
        self.assertEqual(ctx.exception.retry_after, 5)

    def test_429_default_retry_after(self):
        resp = self._mock_response(429, {"error": {"message": "Rate limited"}})
        with self.assertRaises(SpotifyRateLimitError) as ctx:
            raise_for_status(resp)
        self.assertEqual(ctx.exception.retry_after, 1)

    def test_404_raises_not_found(self):
        resp = self._mock_response(404, {"error": {"message": "Not found"}})
        with self.assertRaises(SpotifyNotFoundError):
            raise_for_status(resp)

    def test_500_raises_server_error(self):
        resp = self._mock_response(500, {"error": {"message": "Internal error"}})
        with self.assertRaises(SpotifyServerError) as ctx:
            raise_for_status(resp)
        self.assertEqual(ctx.exception.status_code, 500)

    def test_503_raises_server_error(self):
        resp = self._mock_response(503)
        with self.assertRaises(SpotifyServerError):
            raise_for_status(resp)

    def test_403_raises_generic_error(self):
        resp = self._mock_response(403, {"error": {"message": "Forbidden"}})
        with self.assertRaises(SpotifyError) as ctx:
            raise_for_status(resp)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_no_json_body(self):
        resp = self._mock_response(400, reason="Bad Request")
        with self.assertRaises(SpotifyError) as ctx:
            raise_for_status(resp)
        self.assertIn("Bad Request", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
