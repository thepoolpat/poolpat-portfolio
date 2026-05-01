#!/usr/bin/env python3
"""Spotify OAuth with PKCE flow - Complete implementation"""
import os
import spotipy
from spotipy import SpotifyOAuth
import webbrowser

# Client credentials (PKCE - no secret needed!)
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
if not CLIENT_ID:
    raise RuntimeError("SPOTIFY_CLIENT_ID not set in environment")

REDIRECT_URI = "http://127.0.0.1:8888/callback"

sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    scope="user-read-playback-state,user-modify-playback-state",
    open_browser=True
)

print("Opening Spotify OAuth...")
print("=" * 60)

auth_url = sp_oauth.get_authorize_url()
print(f"\n✅ Visit this URL to authorize:")
print(f"    {auth_url}")
print("\n1. Click 'Agree' to authorize")
print("2. After redirect, copy the full callback URL from browser")
print("3. Paste it here when ready")
print()

import time
time.sleep(90)

callback_url = input("Paste callback URL here: ").strip()
if not callback_url:
    raise ValueError("No callback URL provided")

print("\nChecking token...")

try:
    token_info = sp_oauth.get_access_token_from_code(callback_url)
    print(f"✅ Token acquired!")
    print(f"Access token: {token_info['access_token'][:50]}...")
except Exception as e:
    print(f"❌ Token failed: {e}")
    raise
