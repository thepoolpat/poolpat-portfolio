#!/usr/bin/env python3
"""Authenticate with Spotify and fetch the current user's profile."""

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
        print("Run 'python pipeline/spotify_auth.py' to obtain a refresh token.")
        sys.exit(1)

    tokens = refresh_access_token(client_id, refresh_token)
    client = SpotifyClient(tokens["access_token"])

    user = client.get_current_user()
    print(f"Display Name: {user.get('display_name')}")
    print(f"Account Type: {user.get('product')}")
    print(f"Country:      {user.get('country')}")
    print(f"Followers:    {user.get('followers', {}).get('total', 0)}")
    print(f"Profile URL:  {user.get('external_urls', {}).get('spotify')}")


if __name__ == "__main__":
    main()
