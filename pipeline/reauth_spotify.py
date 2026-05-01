#!/usr/bin/env python3
"""Non-interactive token refresh using PKCE"""
import sys
from pathlib import Path
import spotipy
from spotipy import SpotifyOAuth
import webbrowser

env_path = Path.home() / "poolpat-portfolio" / ".env.spotify"
cache_dir = Path.home() / ".cache" / "spotify_oauth"

# Load current credentials
creds = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            creds[key] = value

print("🔑 Loading credentials...")
print(f"   Client ID: {creds.get('SPOTIFY_CLIENT_ID', 'MISSING')[:20]}...")
print(f"   Redirect URI: {creds.get('SPOTIFY_REDIRECT_URI', 'MISSING')}")

if "SPOTIFY_CLIENT_ID" not in creds or "SPOTIFY_REDIRECT_URI" not in creds:
    print("\n❌ Missing required credentials. Need to run OAuth flow.")
    sys.exit(1)

print("\n🌐 Opening browser for re-authentication...")
print(f"   Visit the URL that opens in your browser!")
print()

sp_oauth = SpotifyOAuth(
    client_id=creds["SPOTIFY_CLIENT_ID"],
    client_secret=None,
    redirect_uri=creds["SPOTIFY_REDIRECT_URI"],
    scope="user-read-playback-state,user-modify-playback-state",
    cache_path=str(cache_dir),
    open_browser=True,
    requests_session=None
)

print("⏳ Waiting for authentication callback...")
print("(After you authorize, a callback URL will be shown)")
print()

# Get new access token (triggers browser OAuth flow)
try:
    new_creds = sp_oauth.get_authorization_code()
    print(f"✅ Authorization code received!")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
