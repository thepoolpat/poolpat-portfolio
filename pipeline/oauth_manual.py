#!/usr/bin/env python3
"""Manual OAuth with correct redirect URI"""
from spotipy import SpotifyOAuth
from pathlib import Path
import webbrowser

cache_dir = Path.home() / ".cache" / "spotify_oauth"

print("Manual Spotify OAuth")
print("="*60)
print()
print("Step 1: Open this URL in your browser:")
print()
auth_url = "https://accounts.spotify.com/authorize?client_id=88d1cb87aba74f809133542879d8885c&response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback&scope=user-read-playback-state%20user-modify-playback-state"
print(auth_url)
print()
print("Step 2: Click 'Agree' to authorize")
print("Step 3: Copy the FULL callback URL after redirect (will fail to load)")
print("Step 4: Paste the full callback URL here (it contains the code)")
print()

callback_url = input("Paste callback URL: ")

if 'code=' in callback_url:
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(callback_url)
    code = parse_qs(parsed.query)['code'][0]
    
    print(f"Code received: {code[:50]}...")
    print("Exchanging for tokens...")
    
    sp_oauth = SpotifyOAuth(
        client_id="88d1cb87aba74f809133542879d8885c",
        client_secret="xxx",
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="user-read-playback-state,user-modify-playback-state",
        cache_path=str(cache_dir),
        open_browser=False
     )
    
    token = sp_oauth.get_access_token(access_code=code)
    
    print(f"\nTokens acquired!")
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
    
    print(f"\nUpdated {env_path}")
    print("Ready to run batch!")
else:
    print("No authorization code found in URL")
