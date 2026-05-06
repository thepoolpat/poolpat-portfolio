#!/usr/bin/env python3
"""Wrapper to run Spotify logger with correct Python path."""
import subprocess
import sys
from pathlib import Path

target = Path(__file__).resolve().parent / "spotify_discord_analytics.py"
result = subprocess.run([sys.executable, str(target)])
sys.exit(result.returncode)
