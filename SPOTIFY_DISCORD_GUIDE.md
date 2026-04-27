# 🎵 Spotify + Discord Analytics System Guide

## Quick Start

### 1. Enable Discord Logging
```bash
cd ~/poolpat-portfolio
./setup_discord.sh
# Enter your Discord webhook URL when prompted
```

### 2. Start the Analytics System
```bash
cd ~/poolpat-portfolio/pipeline
python3 spotify_discord_analytics.py

# Press Enter to start logging
# 'q' to quit and see stats
# 'h' for help
```

### 3. Control via Hermes CLI
```bash
# Check Spotify auth
hermes auth spotify status

# Play a track
hermes chat spotify -m "play Folks Now!"

# Queue tracks
hermes chat spotify -m "queue Radiohead songs"

# Get stats
hermes chat spotify -m "show my top tracks this week"
```

## Features

### 📊 Playback Tracking
- Real-time playback state monitoring
- Track/artist/album logging
- Device detection and tracking
- Progress timestamp tracking
- Volume level logging

### 💾 Analytics Database
Location: `~/poolpat-portfolio/spotify_logs/analytics.db`

**Tables:**
- `playback_history` - All playback events
- `sessions` - Listening sessions
- `daily_stats` - Daily summaries
- `device_log` - Device usage history

**Queries:**
```sql
-- Today's top track
SELECT track_name, artist_name, COUNT(*) 
FROM playback_history 
WHERE date(timestamp) = date('now')
GROUP BY track_name 
ORDER BY COUNT(*) DESC 
LIMIT 1;

-- Top artists this week
SELECT artist_name, COUNT(*) as plays
FROM playback_history 
WHERE timestamp > datetime('now', '-7 days')
GROUP BY artist_name
ORDER BY plays DESC 
LIMIT 10;
```

### 🎮 Discord Remote Control

Webhook URL pattern:
```
https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
```

**Commands to send:**
```
POST to webhook URL with JSON:
{
    "content": "!play [track/artist]",
    "embeds": [...]
}
```

**Available Commands:**
- `!play <track>` - Play a track
- `!pause` - Pause playback
- `!next` - Skip to next
- `!prev` - Go to previous
- `!queue <track>` - Add to queue
- `!status` - Show current playback
- `!stats` - Show weekly stats
- `!devices` - List available devices

### 🎼 Spotify API Integration

**Via Hermes CLI:**
```bash
# Playback control
hermes spotify_playback play context_uri=spotify:playlist:xxx
hermes spotify_playback pause
hermes spotify_playback next
hermes spotify_playback volume 75

# Search
hermes spotify_search "radiohead" type=track limit=5

# Playlists
hermes spotify_playlists list
hermes spotify_playlists add_items 37i9dQZF1DXxxxx "spotify:track:xxx"

# Library
hermes spotify_library save "spotify:track:xxx" kind=tracks
hermes spotify_library list kind=tracks limit=50
```

**Via Python Script:**
```python
# Load credentials
with open(".env.spotify") as f:
    creds = {k.split("=")[0]: k.split("=")[1] for k in f.read().splitlines() if "=" in k}

# Get current playback
import requests
resp = requests.get(creds["SPOTIFY_API_BASE_URL"] + "/me/player",
    headers={"Authorization": f"Bearer {creds['SPOTIFY_ACCESS_TOKEN']}"})
state = resp.json() if resp.status_code == 200 else None

# Log to analytics
analytics.log_playback()
```

## Configuration Files

### `.env.spotify`
```
SPOTIFY_CLIENT_ID=88d1cb87aba74f809133542879d8885c
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_API_BASE_URL=https://api.spotify.com/v1
SPOTIFY_ACCESS_TOKEN=[auto-refreshed]
SPOTIFY_REFRESH_TOKEN=[stored securely]
```

### `.env.discord` (created by setup_discord.sh)
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### `config/camoufox_spotify.json`
```json
{
  "camoufox": {
    "enabled": true,
    "base_url": "http://127.0.0.1:8888",
    "spotify_integration": {
      "client_id": "88d1cb87aba74f809133542879d8885c",
      "redirect_uri": "http://127.0.0.1:8888/callback",
      "auto_refresh": true,
      "device_poll_interval_ms": 5000
    }
  }
}
```

## Usage Examples

### Example 1: Continuous Logging
```bash
cd ~/poolpat-portfolio/pipeline
python3 spotify_discord_analytics.py
# Runs continuously, logging every track change
# Press 'q' to stop and see stats
```

### Example 2: One-time Stats
```bash
cd ~/poolpat-portfolio
python3 -c "
from pipeline.spotify_discord_analytics import SpotifyDiscordAnalytics
a = SpotifyDiscordAnalytics()
stats = a.get_playback_stats(days=7)
print(f'Top: {stats[\"top_track\"]} by {stats[\"top_track_artist\"]}')
"
```

### Example 3: Discord Bot Commands
Send to webhook:
```
!play "Folks Now!"
!pause
!queue "Radiohead"
!status
!stats -- This week I played 147 tracks
```

### Example 4: Export Analytics
```bash
# Export to CSV
sqlite3 ~/poolpat-portfolio/spotify_logs/analytics.db \
    ".mode csv" ".select * from playback_history;" > playlist_export.csv

# Generate top 100
sqlite3 ~/poolpat-portfolio/spotify_logs/analytics.db \
    "SELECT track_name, artist_name, COUNT(*) as plays \
     FROM playback_history \
     GROUP BY track_name \
     ORDER BY plays DESC \
     LIMIT 100;" > top100.txt
```

## Pitfalls & Solutions

| Issue | Solution |
|-------|----------|
| `403 No active device` | Start playing music in Spotify first |
| `429 Rate limit` | Wait before retrying |
| Discord sends fail | Check webhook URL is correct |
| Playback not logging | Verify auth token has scopes |
| Web API timeout | Check Spotify client is running |

## Next Steps

1. **Configure Discord webhook** via `./setup_discord.sh`
2. **Run analytics** via `python3 spotify_discord_analytics.py`
3. **Test remote control** via Discord commands
4. **Export data** for analysis/visualization

Ready to start the loop? 🚀
