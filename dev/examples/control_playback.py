#!/usr/bin/env python3
"""Demonstrate playback control (requires Spotify Premium + active device)."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from spotify_auth import refresh_access_token
from spotify_client import SpotifyClient


def main():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")

    if not client_id or not refresh_token:
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_REFRESH_TOKEN env vars.")
        sys.exit(1)

    tokens = refresh_access_token(client_id, refresh_token)
    client = SpotifyClient(tokens["access_token"])

    state = client.get_playback_state()
    if not state:
        print("No active playback device found.")
        print("Open Spotify on a device and start playing something first.")
        sys.exit(0)

    device = state.get("device", {})
    item = state.get("item", {})
    print(f"Device:  {device.get('name')} ({device.get('type')})")
    print(f"Playing: {item.get('name', 'nothing')}")
    print(f"Volume:  {device.get('volume_percent')}%")
    print(f"State:   {'Playing' if state.get('is_playing') else 'Paused'}")

    print("\nCommands: play, pause, next, prev, vol <0-100>, quit")
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "quit":
            break
        elif cmd == "play":
            client.play()
            print("Playing")
        elif cmd == "pause":
            client.pause()
            print("Paused")
        elif cmd == "next":
            client.skip_next()
            time.sleep(0.5)
            s = client.get_playback_state()
            if s and s.get("item"):
                print(f"Now playing: {s['item']['name']}")
        elif cmd == "prev":
            client.skip_previous()
            time.sleep(0.5)
            s = client.get_playback_state()
            if s and s.get("item"):
                print(f"Now playing: {s['item']['name']}")
        elif cmd.startswith("vol "):
            try:
                vol = int(cmd.split()[1])
                client.set_volume(vol)
                print(f"Volume set to {vol}%")
            except (ValueError, IndexError):
                print("Usage: vol <0-100>")
        else:
            print("Unknown command")


if __name__ == "__main__":
    main()
