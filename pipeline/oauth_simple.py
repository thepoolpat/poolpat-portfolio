#!/usr/bin/env python3
"""Simple OAuth re-auth for Spotify"""
from spotipy import SpotifyOAuth
from pathlib import Path
import webbrowser

env_path = Path.home() / "poolpat-portfolio" / ".env.spotify"
cache_dir = Path.home() / ".cache" / "spotify_oauth"

print("🔑 Loading credentials...")

# Generate a simple client secret for the flow
client_secret = "88d1cb87aba74f809133542879d8885c"  # Using client_id as secret (PKCE)

# Create OAuth object
sp_oauth = SpotifyOAuth(
    client_id="88d1cb87aba74f809133542879d8885c",
    client_secret=client_secret,
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-read-playback-state,user-modify-playback-state",
    cache_path=str(cache_dir),
    open_browser=True
)

print("\n🌐 Opening browser for Spotify authorization...")
print("   Please authorize when prompted!")
print()

# Get authorization code
auth_url = sp_oauth.get_authorize_url()
print(f"1. Visit this URL:")
print(f"   {auth_url}\n")

print("2. After authorizing, you'll be redirected to a callback URL")
print("3. Copy the full callback URL and paste it back here")
print()

# We'll wait for user to provide the callback URL
callback_url = input("Paste callback URL: ")

# Parse the code from the URL
from urllib.parse import parse_qs, urlparse
parsed = urlparse(callback_url)
params = parse_qs(parsed.query)
code = params.get('code', [None])[0]

if not code:
    print("❌ No authorization code found in URL")
    exit(1)

print(f"\n✅ Code received: {code[:20]}...")

# Exchange code for tokens
token = sp_oauth.get_access_token(from_response_code=code)

print(f"\n✅ Token obtained!")
print(f"   Expires in: {token['expires_in']} seconds")
print(f"   Token: {token['access_token'][:50]}...")

# Save to .env.spotify
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

print("\n⬆️  Updated .env.spotify")
print("\nReady to run batch! ✅")
