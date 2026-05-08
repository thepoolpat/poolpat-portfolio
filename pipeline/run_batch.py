#!/usr/bin/env python3
"""
Automated Batch Playback Logger
Run N times → auto-exit after N polls
"""
import sys
import sqlite3
import requests
import time
import json
from pathlib import Path

# Load Spotify token from .env.spotify
env_path = Path.home() / "poolpat-portfolio" / ".env.spotify"
if not env_path.exists():
    raise FileNotFoundError(f"Environment file not found: {env_path}")

spotify = {}
spotify_headers = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            spotify[key] = value
            if key == "SPOTIFY_ACCESS_TOKEN":
                spotify_headers["Authorization"] = f"Bearer {value}"

# Config
N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "dev" / "spotify_logs" / "analytics.db"

# Session
session = requests.Session()
session.headers.update(spotify_headers)

# Database
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("\n" + "="*60)
print(f"🚀 BATCH LOGGING: {N} PLAYBACK POLLS")
print("="*60)

tracks_seen = []
for i in range(N):
    resp = session.get("https://api.spotify.com/v1/me/player")
    
    if resp.status_code == 200:
        player = resp.json()
        track = player.get("item", {})
        
        if track:
            track_name = track.get("name", "Unknown")
            artists = ", ".join([a["name"] for a in track.get("artists", [])])
            
            c.execute("""INSERT INTO playback_history 
                            (timestamp, track_name, artist_name, device_name, 
                             is_playing, progress_ms, volume_percent)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (str(time.time()), track_name, artists,
                        player.get("device", {}).get("name"), 
                        1 if player.get("is_playing") else 0,
                        player.get("progress_ms"),
                        player.get("device", {}).get("volume_percent")))
            
            tracks_seen.append(track_name)
            
            if (i + 1) % 10 == 0:
                print(f"[{i+1}/{N}] ✅ Batch {i+1}: {','.join(set(tracks_seen))}")
            else:
                print(f"[{i+1}/{N}] ✅ {track_name}")
        else:
            print(f"[{i+1}/{N}] ⚪ No track playing")
    else:
        print(f"[{i+1}/{N}] ❌ API Error: {resp.status_code}")
    
    time.sleep(6)  # 6-second intervals

conn.commit()

# Summary
print("\n" + "="*60)
print("✅ BATCH COMPLETE")
print("="*60)

c.execute("SELECT track_name, COUNT(*) as plays FROM playback_history GROUP BY track_name ORDER BY plays DESC")
print("\n📊 TRACK COUNTS:")
for track_name, count in c.fetchall():
    bar = "█" * min(count, 50)
    print(f"     {track_name:20s} [{bar:50s}] {count:2d} plays")

total = c.execute("SELECT COUNT(*) FROM playback_history").fetchone()[0]
print(f"\n📈 TOTAL DATABASE: {total} records")
print(f"🎵 UNIQUE TRACKS: {len(set(tracks_seen))}")
print(f"⏱️  SAMPLE: {N} polls × ~6s = ~{N*6}s")
print("="*60)

conn.close()
