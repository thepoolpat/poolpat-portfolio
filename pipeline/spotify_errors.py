"""Typed error hierarchy for Spotify Web API responses."""

from __future__ import annotations


class SpotifyError(Exception):
    def __init__(self, status_code: int, message: str, response: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.response = response
        super().__init__(f"[{status_code}] {message}")


class SpotifyAuthError(SpotifyError):
    pass


class SpotifyRateLimitError(SpotifyError):
    def __init__(self, retry_after: int, message: str = "Rate limited", response: dict | None = None):
        self.retry_after = retry_after
        super().__init__(429, message, response)


class SpotifyNotFoundError(SpotifyError):
    pass


class SpotifyServerError(SpotifyError):
    pass


def raise_for_status(response) -> None:
    """Map an HTTP response to a typed Spotify error. No-op on 2xx."""
    if response.status_code < 400:
        return

    try:
        body = response.json()
        msg = body.get("error", {}).get("message", response.reason)
    except Exception:
        msg = response.reason or f"HTTP {response.status_code}"

    if response.status_code == 401:
        raise SpotifyAuthError(401, msg)
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 1))
        raise SpotifyRateLimitError(retry_after, msg)
    if response.status_code == 404:
        raise SpotifyNotFoundError(404, msg)
    if response.status_code >= 500:
        raise SpotifyServerError(response.status_code, msg)

    raise SpotifyError(response.status_code, msg)
