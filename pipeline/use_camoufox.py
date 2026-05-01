#!/usr/bin/env python3
"""camoufox SoundCloud integration"""
import requests
import time

api_url = "http://localhost:50844"

print("camoufox SoundCloud Integration")
print("="*60)

# Start web session
print("Starting web session...")
resp = requests.post(f"{api_url}/new")
print(f"New session: {resp.status_code}")
if resp.status_code == 200:
    session_info = resp.json()
    print(f"Session created: {session_info}")
    
    # Check for session ID
    session_id = session_info.get("id", session_info.get("sessionId"))
    print(f"Session ID: {session_id}")
    
    if session_id:
        print(f"\nNavigating to SoundCloud...")
        resp = requests.get(f"{api_url}/session/{session_id}/navigate?url=https://soundcloud.com")
        print(f"Navigate: {resp.status_code}")
        print(f"Response: {resp.text[:300]}")
        
        print(f"\nWaiting for page to load...")
        time.sleep(5)
        
        print(f"Evaluating SoundCloud app...")
        resp = requests.get(f"{api_url}/session/{session_id}/evaluate?script=window.Spotify?.User?.player?.state")
        print(f"Evaluate: {resp.status_code}")
        print(f"Response: {resp.text[:500]}")
