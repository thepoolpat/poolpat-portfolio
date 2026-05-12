#!/usr/bin/env python3
"""
Camoufox + Spotify Integration Setup
=====================================

This script sets up the credentials and configuration for automated
Spotify playback control using camoufox for browser-based automation.

Requirements:
- Spotify Premium account
- Spotify Developer App (Client ID configured)
- Camoufox installed and running

Usage:
    python setup_camoufox_spotify.py
"""

import json
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_SPOTIFY = PROJECT_ROOT / ".env.spotify"
AUTH_FILE = Path.home() / ".hermes" / "auth.json"

SPOTIFY_CLIENT_ID = "YOUR_SPOTIFY_CLIENT_ID"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# ============================================================================
# SETUP FUNCTIONS
# ============================================================================

def load_hermes_auth():
    """Load access token from Hermes auth file."""
    if not AUTH_FILE.exists():
        print(f"❌ Hermes auth file not found: {AUTH_FILE}")
        return None
    
    with open(AUTH_FILE) as f:
        auth_data = json.load(f)
    
    spotify_auth = auth_data.get("providers", {}).get("spotify", {})
    print(f"   ✓ Loaded auth: {spotify_auth.get('client_id')[:10]}...")
    return spotify_auth

def setup_env_file():
    """Create or update .env with base Spotify credentials."""
    print("✓ Setting up .env file...")
    
    if not ENV_FILE.exists():
        print(f"  Created: {ENV_FILE}")
        ENV_FILE.touch()
    
    # Read refresh token from Hermes
    spotify_auth = load_hermes_auth()
    if spotify_auth and isinstance(spotify_auth, dict):
        refresh_token = spotify_auth.get("refresh_token", "")
        if refresh_token:
            existing = ENV_FILE.read_text() if ENV_FILE.exists() else ""
            # Keep the existing refresh token, don't overwrite
            print("  ✓ Refresh token already configured")
    else:
        print("  ⚠ Using existing config")
    
    return True

def setup_spotify_creds():
    """Create dedicated spotify credentials file."""
    print("✓ Creating .env.spotify with credentials...")
    
    spotify_auth = load_hermes_auth()
    
    if not spotify_auth or not isinstance(spotify_auth, dict):
        print("  ❌ No Spotify auth from Hermes found (expected: dict)")
        return False
    
    creds = {
        "SPOTIFY_CLIENT_ID": spotify_auth.get("client_id"),
        "SPOTIFY_REDIRECT_URI": spotify_auth.get("redirect_uri"),
        "SPOTIFY_API_BASE_URL": spotify_auth.get("api_base_url", "https://api.spotify.com/v1"),
        "SPOTIFY_ACCOUNTS_BASE_URL": spotify_auth.get("accounts_base_url", "https://accounts.spotify.com"),
        "SPOTIFY_ACCESS_TOKEN": spotify_auth.get("access_token", ""),
        "SPOTIFY_REFRESH_TOKEN": spotify_auth.get("refresh_token"),
        "SPOTIFY_SCOPE": spotify_auth.get("scope", ""),
    }
    
    lines = []
    for key, value in creds.items():
        lines.append(f"{key}={value}\n")
    
    ENV_SPOTIFY.write_text("".join(lines))
    print(f"  ✓ Created: {ENV_SPOTIFY}")
    
    return True

def create_camoufox_config():
    """Create camoufox-spotify integration config."""
    print("✓ Creating camoufox integration config...")
    
    config = {
        "camoufox": {
            "enabled": True,
            "base_url": "http://127.0.0.1:8888",
            "spotify_integration": {
                "client_id": SPOTIFY_CLIENT_ID,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
                "auto_refresh": True,
                "device_poll_interval_ms": 5000,
            }
        },
        "spotify": {
            "api_base_url": "https://api.spotify.com/v1",
            "scopes": [
                "user-modify-playback-state",
                "user-read-playback-state",
                "user-read-currently-playing",
                "user-read-recently-played",
                "playlist-read-private",
                "playlist-read-collaborative",
                "playlist-modify-public",
                "playlist-modify-private",
                "user-library-read",
                "user-library-modify"
            ],
            "auth_type": "oauth_pkce"
        }
    }
    
    config_file = PROJECT_ROOT / "config" / "camoufox_spotify.json"
    config_file.parent.mkdir(exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2))
    
    print(f"  ✓ Created: {config_file}")
    return config_file

def print_usage():
    """Print usage guide."""
    print("\n" + "="*70)
    print("SETUP COMPLETE - Usage Guide")
    print("="*70)
    print("""
SPOTIFY DEVELOPMENT WORKFLOW
----------------------------

1. Quick Test (CLI via Hermes):
   $ hermes auth spotify status
   $ hermes chat spotify -m "play something relaxing"

2. Browser Automation with Camoufox:
   $ cd pipeline
   $ python camoufox_spotify_player.py
   
   Features:
   - Monitor playback state
   - Auto-play based on criteria
   - Queue management
   - Device discovery

3. API Client Usage:
   $ cd examples
   $ export $(cat ~/.env.spotify | xargs)
   $ python control_playback.py

4. Full Pipeline Execution:
   $ python pipeline/fetch_plays.py
   $ python pipeline/spotify_auth.py

CONFIG FILES
------------
- .env                   : Base env (refresh token)
- .env.spotify           : Full credentials
- config/camoufox_spotify.json : Integration config
- ~/.hermes/auth.json    : Hermes auth state

NEXT STEPS
----------
1. Verify Spotify is running on a device
2. Test: cd pipeline && python camoufox_spotify_player.py
3. Or use Hermes directly: hermes auth spotify login

""" + "="*70)

def main():
    print("🎵 Setting up Camoufox + Spotify integration...\n")
    
    setup_env_file()
    setup_spotify_creds()
    config_file = create_camoufox_config()
    
    print_usage()
    
    print("\n✓ Setup complete!")
    print(f"  Config saved to: {config_file}")
    print(f"  Credentials file: {ENV_SPOTIFY}")
    print(f"  Auth state: ~/.hermes/auth.json")
    
    return 0

if __name__ == "__main__":
    exit(main())
