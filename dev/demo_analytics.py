#!/usr/bin/env python3
"""Quick demo of analytics pipeline"""
import sys
sys.path.insert(0, 'pipeline')

from spotify_discord_analytics import SpotifyDiscordAnalytics

# Create analytics instance
stats = SpotifyDiscordAnalytics()

# Show current stats
s = stats.get_playback_stats(days=7)
print("\n" + "="*60)
print("🎵 SPOTIFY ANALYTICS DEMO")
print("="*60)
print(f"Total tracks (7d): {s['total_tracks']}")
print(f"Unique artists (7d): {s['unique_artists']}")
print(f"Top artist: {s['top_artist']} ({s['top_artist_count']} plays)")
print(f"Top track: {s['top_track']} - {s['top_track_artist']}")
print("="*60)
