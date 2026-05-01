#!/usr/bin/env python3
"""Check SoundCloud via camoufox browser"""
import requests
import time

camoufox_url = "http://localhost:50844"

print("Camoufox SoundCloud Check")
print("="*60)
print(f"URL: {camoufox_url}")
print()

# Check if server is running
resp = requests.get(f"{camoufox_url}/status")
print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    print("Server is running. Let's try the WebSocket endpoint!")
    print(f"WebSocket: ws://localhost:50844/...")
    
     # Try to access camoufox via HTTP
    print("\nAttempting to check SoundCloud playback...")
    
    # Try camoufox HTTP endpoints
    endpoints = [
        "/status",
        "/health",
        "/ping",
        "/info",
    ]
    
    for endpoint in endpoints:
        try:
            resp = requests.get(f"{camoufox_url}{endpoint}")
            print(f"{endpoint}: {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"{endpoint}: Error - {e}")
else:
    print("Server not running")
