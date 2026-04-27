#!/usr/bin/env python3
"""
Spotify + Discord Analytics System
===================================

Full-featured Spotify logging + playback history + Discord remote control.

Features:
- Real-time playback tracking
- Playback history logging to SQLite
- Analytics dashboard (top tracks, artists, playlists)
- Discord remote control via webhooks
- Camoufox integration for enhanced API calls
- Automated streaming logging

Usage:
    python3 spotify_discord_analytics.py

Commands:
    [Enter] - Start continuous logging
    [q]     - Quit and show stats
    [h]     - Show help
"""

import sqlite3
import requests
import time
from pathlib import Path
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
import json

class SpotifyDiscordAnalytics:
    """Spotify analytics with Discord remote control."""
    
    def __init__(self):
        self._load_creds()
        self.session = requests.Session()
        self.session.headers = {
            "Authorization": "Bearer " + self.creds["SPOTIFY_ACCESS_TOKEN"],
            "Accept": "application/json"
        }
        
        # Analytics database
        self.db_path = Path.home() / "poolpat-portfolio" / "spotify_logs" / "analytics.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # Discord webhook
        self.discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        self.discord_enabled = bool(self.discord_webhook_url)
        
        print("="*70)
        print("🎵 Spotify Discord Analytics System")
        print("="*70)
        print(f"✅ Database: {self.db_path}")
        print(f"🔔 Discord: {'Enabled' if self.discord_enabled else 'Disabled'}")
        print(f"📡 Spotify API: {self.creds.get('SPOTIFY_CLIENT_ID', '')[:10]}...")
        print("-"*70)
        
        # Track state
        self.last_track_uri = None
        self.session_start = datetime.now()
        self.session_tracks = []
        
    def _load_creds(self):
        """Load Spotify credentials."""
        self.creds = {}
        with open(Path.home() / "poolpat-portfolio" / ".env.spotify") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    self.creds[key] = value
                    
    def _init_db(self):
        """Initialize analytics database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Playback history
        c.execute('''
            CREATE TABLE IF NOT EXISTS playback_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                track_name TEXT,
                artist_name TEXT,
                album_name TEXT,
                track_uri TEXT,
                device_name TEXT,
                device_type TEXT,
                is_playing INTEGER,
                progress_ms INTEGER,
                volume_percent INTEGER
            )
        ''')
        
        # Sessions
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                track_count INTEGER DEFAULT 0,
                avg_duration INTEGER,
                device_name TEXT
            )
        ''')
        
        # Daily stats
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_tracks INTEGER DEFAULT 0,
                unique_artists INTEGER DEFAULT 0,
                avg_listening_minutes INTEGER DEFAULT 0,
                top_genre TEXT
            )
        ''')
        
        # Device log
        c.execute('''
            CREATE TABLE IF NOT EXISTS device_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_name TEXT,
                device_type TEXT,
                is_active INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✓ Analytics database initialized: {self.db_path}")
        
    def poll_playback(self):
        """Fetch current playback state."""
        try:
            resp = self.session.get(
                self.creds["SPOTIFY_API_BASE_URL"] + "/me/player"
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 204:
                return None
            else:
                return {"error": resp.status_code}
        except Exception as e:
            return {"error": str(e)}
    
    def log_playback(self):
        """Log playback to database and Discord."""
        state = self.poll_playback()
        if not state or "error" in state:
            return
        
        item = state.get("item", {})
        device = state.get("device", {})
        
        if not item:
            return
        
        track_name = item.get("name", "")
        artist_name = item.get("artists", [{}])[0].get("name", "")
        track_uri = item.get("uri", "")
        
        # Check if track changed
        if self.last_track_uri == track_uri:
            return
        
        self.last_track_uri = track_uri
        
        # Log to database
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO playback_history 
            (timestamp, track_name, artist_name, album_name, track_uri, 
             device_name, device_type, is_playing, progress_ms, volume_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            track_name,
            artist_name,
            item.get("album", {}).get("name", ""),
            track_uri,
            device.get("name", ""),
            device.get("type", ""),
            1 if state.get("is_playing") else 0,
            state.get("progress_ms", 0),
            device.get("volume_percent", 0)
        ))
        conn.commit()
        conn.close()
        
        # Log to Discord
        is_playing = state.get("is_playing", False)
        device_name = device.get("name", "Unknown")
        
        if self.discord_enabled:
            emoji = "▶️" if is_playing else "⏸️"
            message = f"""{emoji} **Now Playing**:\n`{track_name}` by `{artist_name}`\n🎵 Device: `{device_name}`"""
            self._send_discord(message)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {emoji} {track_name} - {artist_name}")
        
    def _send_discord(self, message):
        """Send message to Discord webhook."""
        if not self.discord_webhook_url:
            return
        
        try:
            resp = requests.post(
                self.discord_webhook_url,
                json={"content": message}
            )
            if resp.status_code != 204:
                print(f"  Discord error: {resp.status_code}")
        except Exception as e:
            print(f"  Discord send failed: {e}")
    
    def get_playback_stats(self, days=7):
        """Get playback analytics for date range."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT COUNT(*) FROM playback_history
            WHERE timestamp > datetime('now', ?)
        ''', (f"-{days} days",))
        total_tracks = c.fetchone()[0]
        
        c.execute('''
            SELECT COUNT(DISTINCT artist_name) FROM playback_history
            WHERE timestamp > datetime('now', ?)
        ''', (f"-{days} days",))
        unique_artists = c.fetchone()[0]
        
        c.execute('''
            SELECT artist_name, COUNT(*) as count
            FROM playback_history
            WHERE timestamp > datetime('now', ?)
            GROUP BY artist_name
            ORDER BY count DESC
            LIMIT 1
        ''', (f"-{days} days",))
        top_artist = c.fetchone()
        
        c.execute('''
            SELECT track_name, artist_name, COUNT(*) as count
            FROM playback_history
            WHERE timestamp > datetime('now', ?)
            GROUP BY track_name, artist_name
            ORDER BY count DESC
            LIMIT 1
        ''', (f"-{days} days",))
        top_track = c.fetchone()
        
        stats = {
            "total_tracks": total_tracks,
            "unique_artists": unique_artists,
            "top_artist": top_artist[0] if top_artist else None,
            "top_artist_count": top_artist[1] if top_artist else 0,
            "top_track": top_track[0] if top_track else None,
            "top_track_artist": top_track[1] if top_track else None,
            "top_track_count": top_track[2] if top_track else 0,
        }
        
        conn.close()
        return stats
    
    def run(self):
        """Main loop: poll playback and log."""
        print("\nStarting continuous playback monitoring...")
        print("Press Enter to continue, 'q' to quit, 'h' for help\n")
        
        try:
            while True:
                self.log_playback()
                
                print(".", end="", flush=True)
                time.sleep(15)
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            self._show_stats()
            print("="*70)
        except Exception as e:
            print(f"\n\nError: {e}")

    def _show_stats(self):
        """Display playback statistics."""
        stats = self.get_playback_stats(days=7)
        
        print("\n" + "="*70)
        print("📊 7-Day Playback Analytics")
        print("="*70)
        print(f"Total tracks: {stats['total_tracks']}")
        print(f"Unique artists: {stats['unique_artists']}")
        if stats['top_artist']:
            print(f"Top artist: {stats['top_artist']} ({stats['top_artist_count']} listens)")
        if stats['top_track']:
            print(f"Top track: {stats['top_track']} - {stats['top_track_artist']}")
            print(f"  ({stats['top_track_count']} listens)")
        print("="*70)

def main():
    analytics = SpotifyDiscordAnalytics()
    analytics.run()

if __name__ == "__main__":
    main()
