#!/usr/bin/env python3
"""Quick token refresh for Spotify"""
import requests
import sys
from pathlib import Path

env_path = Path.home() / "poolpat-portfolio" / ".env.spotify"

# Load current credentials
creds = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            creds[key] = value

if "SPOTIFY_REFRESH_TOKEN" not in creds or "SPOTIFY_CLIENT_ID" not in creds:
    print("❌ Missing required credentials in .env.spotify")
    sys.exit(1)

print("🔄 Refreshing token...")
resp = requests.post(
    "https://accounts.spotify.com/api/token",
    data={
        "grant_type": "refresh_token",
        "refresh_token": creds["SPOTIFY_REFRESH_TOKEN"],
        "client_id": creds["SPOTIFY_CLIENT_ID"]
    }
)

if resp.status_code == 200:
    new_token = resp.json()["access_token"]
    print("✅ Token refreshed!")
    
    # Update .env.spotify
    with open(env_path, "r") as f:
        lines = f.readlines()
    
    with open(env_path, "w") as f:
        for line in lines:
            if line.strip().startswith("SPOTIFY_ACCESS_TOKEN"):
                f.write(f"SPOTIFY_ACCESS_TOKEN={new_token}\n")
            else:
                f.write(line)
    
    print("⬆️  Updated .env.spotify with new access token")
else:
    print(f"❌ Refresh failed: {resp.status_code}")
    print(resp.text)
    sys.exit(1)
