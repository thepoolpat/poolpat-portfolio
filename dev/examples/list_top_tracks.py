#!/usr/bin/env python3
"""Fetch top tracks across all three time ranges."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from spotify_auth import refresh_access_token
from spotify_client import SpotifyClient


def main():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")

    if not client_id or not refresh_token:
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_REFRESH_TOKEN env vars.")
        sys.exit(1)

    tokens = refresh_access_token(client_id, refresh_token)
    client = SpotifyClient(tokens["access_token"])

    for time_range in ["short_term", "medium_term", "long_term"]:
        label = {"short_term": "Last 4 Weeks", "medium_term": "Last 6 Months", "long_term": "All Time"}
        tracks = client.get_top_tracks(time_range, 10)
        print(f"\n{'=' * 50}")
        print(f"Top Tracks — {label[time_range]}")
        print(f"{'=' * 50}")
        for i, t in enumerate(tracks, 1):
            artists = ", ".join(a["name"] for a in t.get("artists", []))
            print(f"  {i:2}. {t['name']} — {artists} (pop: {t.get('popularity', '?')})")


if __name__ == "__main__":
    main()
