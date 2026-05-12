#!/usr/bin/env python3
"""Simple OAuth flow - no auto-browser needed"""
from spotipy import SpotifyOAuth
from pathlib import Path
import webbrowser
import http.server
import socketserver
import urllib.parse
import threading
import time

cache_dir = Path.home() / ".cache" / "spotify_oauth"

# Global to store the callback
callback_code = [None]

class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if 'code' in params:
            callback_code[0] = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write('<html><body><h1>Authorization Successful!</h1><p>You can close this window.</p></body></html>'.encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'No authorization code received')
    
    def log_message(self, format, *args):
        pass   # Quiet server logs

print("="*60)
print("Spotify OAuth Authorization")
print("="*60)
print()
print("Step 1: A browser window should open automatically...")
print()

# Try to open browser
try:
    webbrowser.open("https://accounts.spotify.com/authorize?client_id=YOUR_SPOTIFY_CLIENT_ID&response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback&scope=user-read-playback-state%20user-modify-playback-state")
except:
    print("Browser did not open automatically. Try this URL manually:")
    print()
    print("https://accounts.spotify.com/authorize?client_id=YOUR_SPOTIFY_CLIENT_ID&response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback&scope=user-read-playback-state%20user-modify-playback-state")
    print()
    input("Press Enter after opening the URL...")

print()
print("Step 2: Authorize Spotify in the browser")
print("Step 3: Copy the callback URL from your browser (looks like http://127.0.0.1:8888/callback?code=...)")
print("Step 4: Paste the URL here...")
print()

# Start local server to catch callback
PORT = 8888
server = socketserver.TCPServer(("", PORT), OAuthHandler)
server_thread = threading.Thread(target=server.handle_request)
server_thread.start()

# Wait for callback (or timeout after 60 seconds)
server.server_close()

if callback_code[0]:
    print(f"\nCode received: {callback_code[0][:50]}...")
    print("Exchanging for tokens...")
    
    sp_oauth = SpotifyOAuth(
        client_id="YOUR_SPOTIFY_CLIENT_ID",
        client_secret="xxx",
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="user-read-playback-state,user-modify-playback-state",
        cache_path=str(cache_dir),
        open_browser=False
    )
    
    token = sp_oauth.get_access_token(access_code=callback_code[0])
    
    print(f"\nTokens acquired!")
    print(f"Access Token: {token['access_token'][:50]}...")
    print(f"Refresh Token: {token['refresh_token'][:50]}...")
    
    # Save to .env.spotify
    env_path = Path.home() / "poolpat-portfolio" / ".env.spotify"
    with open(env_path, "r") as f:
        lines = f.readlines()
    
    with open(env_path, "w") as f:
        for line in lines:
            if line.strip().startswith("SPOTIFY_ACCESS_TOKEN"):
                f.write(f"SPOTIFY_ACCESS_TOKEN={token['access_token']}\n")
                print("Updated SPOTIFY_ACCESS_TOKEN")
            elif line.strip().startswith("SPOTIFY_REFRESH_TOKEN"):
                f.write(f"SPOTIFY_REFRESH_TOKEN={token['refresh_token']}\n")
                print("Updated SPOTIFY_REFRESH_TOKEN")
            else:
                f.write(line)
    
    print(f"\nUpdated {env_path}")
    print("\nReady to run batch!")
else:
    print("No authorization code received")
    print("Try pasting the callback URL manually if the server did not catch it")
