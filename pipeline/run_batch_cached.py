#!/usr/bin/env python3
"""
Spotify Auto-Token Batch Logger
Uses requests directly for reliable token authentication
"""
import sys
import sqlite3
import requests
import time
from pathlib import Path

# Config
N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "dev" / "spotify_logs" / "analytics.db"
ENV_PATH = Path.home() / "poolpat-portfolio" / ".env.spotify"

def load_spotify_creds():
    """Load Spotify credentials from .env file"""
    creds = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                creds[key] = value
    return creds

def main():
    print("\n" + "="*60)
    print(f"🚀 AUTO-REFRESH BATCH: {N} PLAYBACK POLLS")
    print("="*60)
    print(f"🗄️  DB: {DB_PATH}")
    print("="*60 + "\n")
    
    # Load credentials
    creds = load_spotify_creds()
    
    # Create authenticated session
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {creds['SPOTIFY_ACCESS_TOKEN']}"})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    tracks_seen = []
    for i in range(N):
        try:
            resp = session.get("https://api.spotify.com/v1/me/player")
            
            if resp.status_code == 200:
                player = resp.json()
                
                if player.get("item"):
                    track = player["item"]
                    track_name = track["name"]
                    artists = ", ".join([a["name"] for a in track["artists"]])
                    
                    # Insert to DB
                    c.execute("""INSERT INTO playback_history 
                                    (timestamp, track_name, artist_name, device_name, 
                                     is_playing, progress_ms, volume_percent)
                                VALUES (?, ?, ?, ?, ?, ?, ?""",
                              (str(time.time()), track_name, artists,
                               player.get("device", {}).get("name"), 
                               1 if player.get("is_playing") else 0,
                               player.get("progress_ms"),
                               player.get("device", {}).get("volume_percent")))
                    
                    tracks_seen.append(track_name)
                    
                    if (i + 1) % 10 == 0:
                        print(f"[{i+1}/{N}] ✅ Batch {i+1}: {', '.join(set(tracks_seen[-3:]))}")
                    elif (i + 1) % 5 == 0:
                        print(f"[{i+1}/{N}] ✅ {track_name}")
                    else:
                        print(f"[{i+1}/{N}] ⚪ {track_name}")
                else:
                    print(f"[{i+1}/{N}] ⚪ No track playing")
            else:
                print(f"[{i+1}/{N}] ❌ API Error: {resp.status_code}")
                
                # Try to refresh token
                if resp.status_code == 401:
                    print("       ↻Refreshing token...")
                    token_resp = session.post(
                        "https://accounts.spotify.com/api/token",
                        data={"grant_type": "refresh_token", "refresh_token": creds["SPOTIFY_REFRESH_TOKEN"]}
                    )
                    if token_resp.status_code == 200:
                        new_token = token_resp.json()["access_token"]
                        session.headers["Authorization"] = f"Bearer {new_token}"
                        creds["SPOTIFY_ACCESS_TOKEN"] = new_token
                        print("       ✅ Token refreshed")
                    else:
                        print("       ❌ Token refresh failed")
            
            conn.commit()
            
        except Exception as e:
            print(f"[{i+1}/{N}] ❌ Error: {e}")
        
        time.sleep(6)  # 6-second intervals
    
    conn.close()
    
    # Summary
    print("\n" + "="*60)
    print("✅ BATCH COMPLETE")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM playback_history")
    total = c.fetchone()[0]
    
    c.execute("SELECT track_name, COUNT(*) as plays FROM playback_history GROUP BY track_name ORDER BY plays DESC LIMIT 10")
    
    print("\n📊 TRACK COUNTS:")
    for track_name, count in c.fetchall():
        bar = "█" * min(count, 50)
        print(f"      {track_name:20s} [{bar:50s}] {count}")
    
    print(f"\n📈 TOTAL: {total} records")
    print(f"🎵 UNIQUE TRACKS IN BATCH: {len(set(tracks_seen))}")
    print(f"⏱️  SAMPLE: {N} polls × ~6s = ~{N*6}s")
    
    conn.close()
    print("="*60)

if __name__ == "__main__":
    main()
