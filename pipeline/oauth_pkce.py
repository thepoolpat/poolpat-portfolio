#!/usr/bin/env python3
"""PKCE OAuth flow - client_secret required by spotipy"""
import spotipy
from spotipy import SpotifyOAuth
from pathlib import Path
import webbrowser

cache_dir = Path.home() / ".cache" / "spotify_oauth"

# Create OAuth object (PKCE flow)
sp_oauth = SpotifyOAuth(
    client_id="YOUR_SPOTIFY_CLIENT_ID",
    client_secret="anything",  # Required but not validated for PKCE
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-read-playback-state,user-modify-playback-state",
    cache_path=str(cache_dir),
    open_browser=True
)

print("🌐 Opening Spotify authorization in browser...")
auth_url = sp_oauth.get_authorize_url()
print(f"\nVisit this URL:")
print(f"  {auth_url}\n")

print("After authorizing, Spotify will redirect to a callback URL")
print("Paste the full callback URL here:\n")

callback_url = input()

# Parse code from URL
from urllib.parse import urlparse, parse_qs
parsed = urlparse(callback_url)
code = parse_qs(parsed.query).get('code', [None])[0]

if not code:
    print("❌ No code found in URL")
    exit(1)

print(f"\n✅ Code received, exchanging for tokens...")

# Get tokens
token = sp_oauth.get_access_token(from_response_code=code)

print(f"\n✅ Tokens acquired!")
print(f"Access Token: {token['access_token'][:50]}...")
print(f"Refresh Token: {token['refresh_token'][:50]}...")

# Save to .env.spotify
env_path = Path.home() / "poolpat-portfolio" / ".env.spotify"
with open(env_path, "r") as f:
    lines = f.readlines()

with open(env_path, "w") as f:
    for line in lines:
        if line.strip().startswith("SPOTIFY_ACCESS_TOKEN"):
            f.write(f"SPOTIFY_ACCESS_TOKEN={token['access_token']}\n")
        elif line.strip().startswith("SPOTIFY_REFRESH_TOKEN"):
            f.write(f"SPOTIFY_REFRESH_TOKEN={token['refresh_token']}\n")
        else:
            f.write(line)

print(f"\n⬆️  Updated {env_path}")
print("\nReady to run batch!")
