#!/usr/bin/env python3
"""
Enhanced Spotify Analytics System v2.0
=======================================

Integrates with poolpat/portfolio for enhanced features:
- Portfolio data tracking
- Spotify listening habits analysis
- Cross-platform integration
- Advanced analytics dashboard

Features:
- Portfolio project integration
- Enhanced playback logging
- Cross-device analytics
- Web API rate limit awareness
- Discord bot command logging
"""

import sqlite3
import requests
import time
from pathlib import Path
from datetime import datetime, timedelta
import json
import csv
from collections import defaultdict


class EnhancedSpotifyAnalytics:
    """Enhanced Spotify analytics with portfolio integration."""
    
    def __init__(self):
        self._load_creds()
        self.session = requests.Session()
        self.session.headers = {
            "Authorization": "Bearer " + self.creds["SPOTIFY_ACCESS_TOKEN"],
            "Accept": "application/json"
        }
        
        # Enhanced database
        self.db_path = Path.home() / "poolpat-portfolio" / "spotify_logs" / "analytics_v2.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db_v2()
        
        # Portfolio config
        self.portfolio_url = "https://github.com/thepoolpat/portfolio"
        self.portfolio_data = {}
        
        # Analytics tracking
        self.playback_counter = 0
        self.discord_commands = []
        
        print("="*70)
        print("🎵 Enhanced Spotify Analytics System v2.0")
        print("="*70)
        print(f"✅ Database: {self.db_path}")
        print(f"🔗 Portfolio: {self.portfolio_url}")
        print(f"📡 API: {self.creds.get('SPOTIFY_CLIENT_ID', '')[:10]}...")
        print("-"*70)
        
    def _load_creds(self):
        self.creds = {}
        creds_file = Path.home() / "poolpat-portfolio" / ".env.spotify"
        if creds_file.exists():
            with open(creds_file) as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        self.creds[key] = value
    
    def _init_db_v2(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Enhanced playback history with portfolio tags
        c.execute('''
            CREATE TABLE IF NOT EXISTS playback_history_v2 (
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
                volume_percent INTEGER,
                mood_tag TEXT,
                activity_context TEXT,
                portfolio_project TEXT,
                listening_session TEXT
            )
        ''')
        
        # Portfolio projects table
        c.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                status TEXT,
                last_updated TEXT,
                spotify_sync INTEGER,
                priority INTEGER
            )
        ''')
        
        # Discord commands log
        c.execute('''
            CREATE TABLE IF NOT EXISTS discord_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                command TEXT,
                player_response TEXT,
                status TEXT
            )
        ''')
        
        # Analytics dashboard
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_dashboard (
                date TEXT PRIMARY KEY,
                total_listens INTEGER DEFAULT 0,
                top_artist TEXT,
                top_artist_plays INTEGER,
                top_track TEXT,
                top_track_plays INTEGER,
                avg_volume INTEGER,
                active_devices TEXT,
                portfolio_sync INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✓ Enhanced database initialized: {self.db_path}")
        
    def fetch_portfolio(self):
        """Fetch portfolio repository data."""
        try:
            resp = requests.get(
                "https://api.github.com/repos/thepoolpat/portfolio",
                timeout=10
            )
            if resp.status_code == 200:
                self.portfolio_data = resp.json()
                print(f"✓ Portfolio: {self.portfolio_data['full_name']}")
                print(f"📊 Stars: {self.portfolio_data['stargazers_count']}")
                return True
            else:
                print(f"⚠ Portfolio not found: {resp.status_code}")
                return False
        except Exception as e:
            print(f"⚠ Fetch error: {e}")
            return False
    
    def log_playback_enhanced(self, portfolio_project=None):
        """Log playback with portfolio integration."""
        state = self.poll_playback()
        if not state or "error" in state:
            return
        
        item = state.get("item", {})
        device = state.get("device", {})
        
        if not item:
            return
        
        track_name = item.get("name", "")
        artist_name = item.get("artists", [{}])[0].get("name", "")
        
        # Enhanced context
        mood = self._detect_mood(artist_name)
        project = portfolio_project or self._match_project_to_artist(artist_name)
        
        # Log to enhanced DB
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO playback_history_v2 
            (timestamp, track_name, artist_name, album_name, track_uri, 
            device_name, device_type, is_playing, progress_ms, volume_percent,
            mood_tag, activity_context, portfolio_project, listening_session)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            track_name,
            artist_name,
            item.get("album", {}).get("name", ""),
            item.get("uri", ""),
            device.get("name", ""),
            device.get("type", ""),
            1 if state.get("is_playing") else 0,
            state.get("progress_ms", 0),
            device.get("volume_percent", 0),
            mood,
            "active",
            project,
            self._get_session_id()
        ))
        conn.commit()
        conn.close()
        
        self.playback_counter += 1
        print(f"    [{self.playback_counter}] {track_name} - {artist_name} | {mood}")
        
        return True
    
    def _detect_mood(self, artist_name):
        """Simple mood detection based on artist name."""
        mood_keywords = {
            "chill": ["lo-fi", "chill", "ambient", "relax", "sleep"],
            "energetic": ["rock", "dance", "edm", "pop", "upbeat"],
            "melancholy": ["sad", "slow", "ballad", "acoustic", "cover"],
            "focus": ["classical", "jazz", "instrumental", "study"]
        }
        
        artist_lower = artist_name.lower()
        for mood, keywords in mood_keywords.items():
            for keyword in keywords:
                if keyword in artist_lower:
                    return mood
        return "general"
    
    def _match_project_to_artist(self, artist_name):
        """Match playing track to portfolio project."""
        projects = self.portfolio_data.get("projects", [])
        artist_lower = artist_name.lower()
        
        for project in projects:
            project_name = project.get("name", "").lower()
            if artist_lower in project_name or project_name in artist_lower:
                return project.get("name")
        
        return "spontaneous"
    
    def _get_session_id(self):
        """Get or create current listening session."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT id FROM sessions 
            WHERE ended_at IS NULL 
            ORDER BY started_at DESC 
            LIMIT 1
        ''')
        
        session = c.fetchone()
        session_id = session[0] if session else f"session_{datetime.now().strftime('%Y%m%d_%H%M')}"
        conn.close()
        return session_id
    
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
    
    def log_discord_command(self, command, response=None, status="sent"):
        """Log Discord remote control command."""
        self.discord_commands.append({
            "command": command,
            "response": response,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO discord_commands 
            (timestamp, command, player_response, status)
            VALUES (?, ?, ?, ?)
        ''', (
            self.discord_commands[-1]["timestamp"],
            command,
            response or "",
            status
        ))
        conn.commit()
        conn.close()
    
    def sync_spotify_to_portfolio(self):
        """Create Spotify sync data for portfolio."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get recent listening stats
        c.execute('''
            SELECT artist_name, COUNT(*) as plays
            FROM playback_history_v2
            WHERE timestamp > datetime('now', '-7 days')
            GROUP BY artist_name
            ORDER BY plays DESC
            LIMIT 10
        ''')
        
        top_artists = c.fetchall()
        
        # Create sync entries
        sync_data = []
        for artist, plays in top_artists[:5]:
            sync_data.append({
                "artist": artist,
                "plays": plays,
                "period": "last_7_days",
                "sync_source": "spotify_discord_integration",
                "timestamp": datetime.now().isoformat()
            })
        
        conn.close()
        
        return sync_data
    
    def export_portfolio_data(self, filename="export.csv"):
        """Export analytics to portfolio CSV format."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get dashboard data
        c.execute('''
            SELECT date, total_listens, top_artist, top_artist_plays,
                   top_track, top_track_plays, avg_volume, active_devices
            FROM daily_dashboard
            ORDER BY date DESC
            LIMIT 30
        ''')
        
        dashboard = c.fetchall()
        
        # Export to CSV
        csv_path = Path.home() / "poolpat-portfolio" / "spotify_logs" / filename
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["date", "plays", "top_artist", "top_artist_plays"])
            writer.writeheader()
            for row in dashboard:
                writer.writerow({
                    "date": row[0],
                    "plays": row[1],
                    "top_artist": row[2],
                    "top_artist_plays": row[3]
                })
        
        conn.close()
        
        print(f"✓ Dashboard exported: {csv_path}")
        return csv_path
    
    def run_enhanced(self):
        """Run enhanced monitoring with portfolio integration."""
        print("\nStarting enhanced monitoring...\n")
        
        # Fetch portfolio if available
        if self.portfolio_data:
            self.fetch_portfolio()
        
        try:
            while True:
                self.log_playback_enhanced()
                print(".", end="", flush=True)
                time.sleep(30)  # 30s intervals for enhanced features
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("🎵 Enhanced Analytics Session Complete")
            print("="*70)
        except Exception as e:
            print(f"\n\nError: {e}")


def main():
    analytics = EnhancedSpotifyAnalytics()
    
    # Test Discord logging
    analytics.log_discord_command("!play Folks Now!", "queued", "success")
    analytics.log_discord_command("!status", "Web Player (Chrome)", "success")
    analytics.log_discord_command("!pause", "paused", "success")
    
    print(f"\n✅ {len(analytics.discord_commands)} Discord commands logged")
    print("Ready to run enhanced loop!")
    
    # Uncomment to run:
    # analytics.run_enhanced()


if __name__ == "__main__":
    main()
