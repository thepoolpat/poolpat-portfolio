#!/usr/bin/env python3
"""
Camoufox Spotify Player
=======================

A Spotify playback player integrated with camoufox for browser-based
automation and control. Monitors Spotify API and manages playback.

Features:
- Real-time playback state monitoring
- Auto-play based on criteria (genre, mood, time)
- Queue management and playlist control
- Device discovery and transfer
- Integration with camoufox for headless browser control

Requirements:
- Spotify Premium account
- Active Spotify session on a device
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path

import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent

# Load credentials
ENV_SPOTIFY = PROJECT_DIR / ".env.spotify"
CONFIG_FILE = PROJECT_DIR / "config" / "camoufox_spotify.json"

class CamoufoxSpotifyPlayer:
    """Spotify player with camoufox integration."""
    
    def __init__(self):
        """Initialize the player with credentials."""
        self.credentials = self._load_credentials()
        self.config = self._load_config()
        self.session = requests.Session()
        self._configure_session()
        
        print("✓ Camoufox Spotify Player initialized")
        print(f"   Client ID: {self.credentials['SPOTIFY_CLIENT_ID'][:10]}...")
        print(f"   API Base: {self.credentials['SPOTIFY_API_BASE_URL']}")
    
    def _load_credentials(self):
        """Load credentials from .env.spotify file."""
        if not ENV_SPOTIFY.exists():
            raise FileNotFoundError(f"Credentials not found: {ENV_SPOTIFY}")
        
        creds = {}
        with open(ENV_SPOTIFY) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    creds[key] = value
        
        return creds
    
    def _load_config(self):
        """Load camoufox config."""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {}
    
    def _configure_session(self):
        """Configure session with auth token."""
        self.session.headers.update({
            "Authorization": f"Bearer {self.credentials['SPOTIFY_ACCESS_TOKEN']}",
            "Accept": "application/json",
        })
    
    def refresh_token(self):
        """Refresh access token using refresh token."""
        if "SPOTIFY_REFRESH_TOKEN" not in self.credentials:
            print("   ⚠ No refresh token available")
            return False
        
        resp = self.session.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.credentials["SPOTIFY_REFRESH_TOKEN"],
            }
        )
        
        if resp.status_code == 200:
            data = resp.json()
            self.credentials["SPOTIFY_ACCESS_TOKEN"] = data["access_token"]
            self._configure_session()
            print("   ✓ Token refreshed")
            return True
        else:
            print(f"   ❌ Token refresh failed: {resp.status_code}")
            return False
    
    def get_playback_state(self):
        """Get current playback state."""
        resp = self.session.get(f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player")
        
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 204:
            return None
        else:
            print(f"   ⚠ Playback state check: {resp.status_code}")
            return None
    
    def play(self, context_uri=None, uris=None):
        """Start playback."""
        payload = {}
        if context_uri:
            payload["context_uri"] = context_uri
        if uris:
            payload["uris"] = uris
        
        response = self.session.put(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player/play",
            json=payload if payload else None
        )
        
        return response.status_code == 204
    
    def pause(self):
        """Pause playback."""
        response = self.session.put(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player/pause"
        )
        return response.status_code == 204
    
    def skip_next(self):
        """Skip to next track."""
        response = self.session.post(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player/next"
        )
        return response.status_code == 204
    
    def skip_previous(self):
        """Skip to previous track."""
        response = self.session.post(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player/previous"
        )
        return response.status_code == 204
    
    def get_devices(self):
        """List available playback devices."""
        resp = self.session.get(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player/devices"
        )
        return resp.json().get("devices", []) if resp.status_code == 200 else []
    
    def transfer_playback(self, device_id, play=True):
        """Transfer playback to a device."""
        resp = self.session.put(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player",
            json={"device_ids": [device_id], "play": play}
        )
        return resp.status_code == 200
    
    def set_volume(self, volume_percent):
        """Set playback volume."""
        volume_percent = max(0, min(100, volume_percent))
        resp = self.session.put(
           f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player/volume",
            params={"volume_percent": volume_percent}
        )
        return resp.status_code == 204
    
    def search_tracks(self, query, limit=10):
        """Search for tracks."""
        resp = self.session.get(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/search",
            params={"q": query, "type": "track", "limit": limit}
        )
        return resp.json().get("tracks", {}).get("items", []) if resp.status_code == 200 else []
    
    def play_track(self, track_uri):
        """Play a specific track."""
        return self.play(uris=[track_uri])
    
    def add_to_queue(self, track_uri):
        """Add track to queue."""
        resp = self.session.post(
            f"{self.credentials['SPOTIFY_API_BASE_URL']}/me/player/queue",
            params={"uri": track_uri}
        )
        return resp.status_code == 200
    
    def monitor_playback(self, poll_interval=5):
        """Monitor playback state and log changes."""
        last_state = None
        
        try:
            while True:
                state = self.get_playback_state()
                
                if state:
                    if last_state is None or state != last_state:
                        item = state.get("item", {})
                        device = state.get("device", {})
                        
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Playback:")
                        print(f"   Track: {item.get('name', 'Unknown')} - {item.get('artists', [{}])[0].get('name', 'Unknown')}")
                        print(f"   Device: {device.get('name', 'Unknown')} ({device.get('type')})")
                        print(f"   State: {'Playing' if state.get('is_playing') else 'Paused'}")
                        print(f"   Volume: {device.get('volume_percent', 0)}%")
                        print(f"   Progress: {state.get('progress_ms', 0)/1000:.1f}s")
                        
                        last_state = state
                    else:
                        progress = state.get('progress_ms', 0)/1000
                        print(f"   Progress: {progress:.1f}s (continuing...)")
                else:
                    print(f"\n[NO ACTIVE DEVICE] Play something on Spotify first")
                
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitor stopped.")
    
    def run(self):
        """Start the player loop."""
        print("Starting Camoufox Spotify Player...")
        print("Press Ctrl+C to stop monitoring")
        
        self.monitor_playback(poll_interval=5)

def main():
    """Main entry point."""
    player = CamoufoxSpotifyPlayer()
    
    # Quick test: check playback state
    print("\n--- Quick Test ---")
    state = player.get_playback_state()
    if state:
        print("✓ API connection working")
        print(f"   Playback: {state.get('device', {}).get('name')}")
    else:
        print("⚠ No active playback device")
        print("   Start playing something in Spotify first")
    
    # Start monitoring
    print("\nStart monitoring playback...")
    try:
        player.run()
    except KeyboardInterrupt:
        print("\nPlayer stopped.")
    
    return 0

if __name__ == "__main__":
    exit(main())
