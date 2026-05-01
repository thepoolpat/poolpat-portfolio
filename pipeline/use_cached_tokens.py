#!/usr/bin/env python3
"""Use cached Spotify tokens"""
import spotipy
from spotipy import SpotifyOAuth
from pathlib import Path
import requests
import time

cache_dir = Path.home() / ".cache" / "spotify_oauth"
sp_oauth = SpotifyOAuth(
    client_id="88d1cb87aba74f809133542879d8885c",
    client_secret="b4b12af5921b471e8ef1bda971816912",
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-read-playback-state,user-modify-playback-state",
    cache_path=str(cache_dir),
    open_browser=False
)

print("Spotify Cached Token Test")
print("="*60)

print("Waiting 3 seconds for token to settle...")
time.sleep(3)

try:
    # Check if cached token is valid
    from spotipy.oauth2 import SpotifyOAuth
    token_info = sp_oauth.get_cached_token()
    
    if token_info and "access_token" in token_info:
        print(f"✅ Found cached token")
        print(f"Expires in: {token_info.get('expires_in', 'N/A')}s")
        
        # Test API
        sp = spotipy.Spotify(auth=token_info["access_token"])
        me = sp.me()
        print(f"✅ Connected: {me['display_name']}")
        print(f"   Following: {me['followers']['total']}")
        
        # Test playback
        player = sp.current_playback()
        if player:
            print(f"Playing: {player['item']['name']} by {player['item']['artists'][0]['name']}")
        else:
            print("No active playback")
        
    else:
        print("❌ No cached token available")
        print("Starting OAuth flow...")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nCached token expired. Will need to re-authorize.")
