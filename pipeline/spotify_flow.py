#!/usr/bin/env python3
"""Spotify client credentials - direct OAuth"""
import requests
import time
from pathlib import Path

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
if not CLIENT_ID:
    raise RuntimeError("SPOTIFY_CLIENT_ID not set in environment")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-read-playback-state user-modify-playback-state"

cache_dir = Path.home() / ".cache" / "spotify_oauth"
cache_dir.mkdir(parents=True, exist_ok=True)

print("Spotify Client Credentials Flow")
print("="*60)
print(f"Client ID: {CLIENT_ID[:20]}")
print(f"Redirect URI: {REDIRECT_URI}")
print(f"Cache: {cache_dir}")
print()

# Step 1: Get auth URL through OAuth flow
print("Step 1: Opening OAuth URL...")
auth_url = f"https://accounts.spotify.com/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI.replace('http://', 'https://')}&scope={SCOPE.replace(' ', '%20')}"
print(f"\n✅ Open this URL:")
print(f"   {auth_url}")
print()
print("After authorizing:")
print("1. Click 'Agree'")
print("2. Browser will try to redirect to http://127.0.0.1:8888/callback (will fail)")
print("3. Copy the FULL URL from address bar")
print("4. Paste it here - it contains the authorization code")
print()

# Wait for user input
print("Waiting 90 seconds for authorization...")
time.sleep(90)

print()
print("Ready to proceed when you paste the callback URL!")
