import requests
import sys
from pathlib import Path

# Refresh token
refresh_resp = requests.post(
     "https://accounts.spotify.com/api/token",
    data={
         "grant_type": "refresh_token",
         "refresh_token": "AQDP7byRFd-O6rNco7TvKM-hM104KoMS6qWNpa2K1aL08fIDsXcPjcV_9iH5W4nAwvSASCUOdm3k1IBB3IqtS9cfx_0p8t8NlnqcosPhvApw64OHjMtr5nPhJoZ18-hx9Jw",
         "client_id": "88d1cb87aba74f809133542879d8885c"
     }
)

if refresh_resp.status_code == 200:
    token = refresh_resp.json()["access_token"]
    print(f"✅ New access token: {token[:50]}...")
    
    # Update .env.spotify
    env_path = Path.home() / "poolpat-portfolio" / ".env.spotify"
    with open(env_path, "r") as f:
        lines = f.readlines()
    
    with open(env_path, "w") as f:
        for line in lines:
            if line.strip().startswith("SPOTIFY_ACCESS_TOKEN"):
                f.write(f"SPOTIFY_ACCESS_TOKEN={token}\n")
            else:
                f.write(line)
    
    print("⬆️  Updated .env.spotify")
    sys.exit(0)
else:
    print(f"❌ Failed: {refresh_resp.status_code}")
    print(refresh_resp.text)
    sys.exit(1)
