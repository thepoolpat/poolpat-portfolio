#!/usr/bin/env python3
"""Get tokens without code verifier (spotipy handles this)"""
import spotipy
from spotipy import SpotifyOAuth
from pathlib import Path
import json
import requests

code = 'AQD6c6_ZCV37si2929weVw9KWo-AiqoJnrbwo5HSoeH4GXXoR2oCGqux1Xg9YduSdGYEUz-8YM81NhSMRptiEHKT59P50-vPke9kClbfqLxpog5wryFr8PP9LuMMqqWxJ8RccVF7YdI5uibURAtvRDb0E0Tt0Bj9HPZ_opmECkOSsS4uWEUgAsJQSaP2EZK5oAK3_orAg5MJWoK_d0DkUSKO_drQZXcCjDjAh5G19inM_r8NFSe1cL9O8N059xNtYRGxtT5LLIGkosjnKwZ3V8tmRiczSrh0Xf3gbbCdd1SJfgB2MBLC5BrHH6SWwn7SSMV2C6MpHqmUuvFhVcaH32RjRRkjrE-IyxnPOyYW971MHSZkDkq7erQe-RvXitiMpS04vob7o6ybSMOv0a3grpNSEh5u0sw0wHoPZFKcFtHx_cxsOPuMqrnYQd5Dr4-1BK2x8sQthZY5OK1xGxnBJ_8IzacpWHT1OazANEm9QSmuihyirbQfe1i976Nivg5OoPnh3DykWXW9l_JWMKSHkM6ZkHGxeYGT9ZvClNTimMFxOcaiNGvnRn3oNNDy4Lon'

cache_dir = Path.home() / '.cache' / 'spotify_oauth'
cache_dir.mkdir(parents=True, exist_ok=True)

sp_oauth = SpotifyOAuth(
    client_id='YOUR_SPOTIFY_CLIENT_ID',
    redirect_uri='http://127.0.0.1:8888/callback',
    scope='user-read-playback-state,user-modify-playback-state',
    cache_path=str(cache_dir),
    show_dialog=True
)

try:
    token_info = sp_oauth.validate_token()
    print('Token already valid:', token_info.get('access_token', 'N/A')[:50])
except Exception as e:
    print(f'Need new token: {e}')
    
    token_resp = requests.post(
        'https://accounts.spotify.com/api/token',
        data={
            'code': code,
            'redirect_uri': 'http://127.0.0.1:8888/callback',
            'grant_type': 'authorization_code',
            'client_id': 'YOUR_SPOTIFY_CLIENT_ID',
        },
        headers={'Authorization': ''}
    )
    
    print(f'Got response: {token_resp.status_code}')
    if token_resp.status_code == 200:
        token_data = token_resp.json()
        
        with open(cache_dir / 'spotify.oauth', 'w') as f:
            json.dump(token_data, f)
        
        env_path = Path.home() / 'poolpat-portfolio' / '.env.spotify'
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        with open(env_path, 'w') as f:
            for line in lines:
                if line.strip().startswith('SPOTIFY_ACCESS_TOKEN'):
                    f.write(f"SPOTIFY_ACCESS_TOKEN={token_data['access_token']}\n")
                elif line.strip().startswith('SPOTIFY_REFRESH_TOKEN'):
                    f.write(f"SPOTIFY_REFRESH_TOKEN={token_data['refresh_token']}\n")
                else:
                    f.write(line)
        
        print('Tokens saved!')
        print(f"Access: {token_data['access_token'][:50]}...")
    else:
        print(f'Failed: {token_resp.text}')
