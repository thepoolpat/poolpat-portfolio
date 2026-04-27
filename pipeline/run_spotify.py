#!/opt/homebrew/bin/python3
"""Wrapper to run Spotify logger with correct Python path"""
import subprocess
import sys

result = subprocess.run([
    "/opt/homebrew/bin/python3",
    "/Users/mortymcfly/poolpat-portfolio/pipeline/spotify_discord_analytics.py"
])

sys.exit(result.returncode)
