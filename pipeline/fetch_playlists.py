"""
fetch_playlists.py — live playlist fetcher (client_credentials flow)

This is the active playlist fetcher invoked by the `Fetch playlist data`
step in .github/workflows/fetch-data.yml. It authenticates to Spotify via
the **client_credentials** OAuth grant: every run mints its own short-lived
access_token from CLIENT_ID + CLIENT_SECRET, with no refresh_token, no
rotation, no save-back, and no $GITHUB_ENV juggling.

Scope
-----
Client credentials only grants access to PUBLIC catalog endpoints
(/artists, /albums, /tracks, /search, /playlists/<public_id>). It CANNOT
read user-scoped data (private playlists, saved tracks, top tracks,
recently played). That is fine for playlist discovery: we search for
tracks by name and hit Playlistcheck (RapidAPI) — both public.

Required env
------------
  SPOTIFY_CLIENT_ID
  SPOTIFY_CLIENT_SECRET
  RAPIDAPI_KEY
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
ARTIST_ID = "4rr3o9anpUXitNXo0W4uX7"  # Poolpat
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "playlists.json"
PLAYLISTCHECK_URL = "https://playlistcheck.p.rapidapi.com/playlist"


# ---------------------------------------------------------------------------
# Spotify auth — client_credentials (NO refresh_token, NO rotation)
# ---------------------------------------------------------------------------
def get_spotify_token() -> str:
    """Mint a fresh app-scoped access_token via client_credentials.

    Returns just the access_token string. No refresh_token is involved
    on this code path — every run gets a brand new short-lived token
    (~1h) and discards it. No state to persist anywhere.
    """
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise RuntimeError(
            "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must both be set "
            "for the client_credentials flow"
        )

    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=15,
    )

    if not resp.ok:
        # NEVER include resp.text or auth in the error message — keep clean
        raise RuntimeError(
            f"Spotify client_credentials auth failed ({resp.status_code})"
        )

    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Spotify helpers
# ---------------------------------------------------------------------------
MAX_RATE_LIMIT_RETRIES = 5
MAX_RETRY_AFTER_S = 30  # Spotify can send Retry-After in the thousands; cap it


def spotify_get(path: str, token: str, params: dict | None = None) -> dict:
    for _ in range(MAX_RATE_LIMIT_RETRIES):
        resp = requests.get(
            f"{SPOTIFY_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=15,
        )
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp.json()
        try:
            retry_after = int(resp.headers.get("Retry-After", 5))
        except ValueError:  # RFC allows an HTTP-date here
            retry_after = 5
        retry_after = min(max(retry_after, 1), MAX_RETRY_AFTER_S)
        print(f"  Spotify rate limit — sleeping {retry_after}s")
        time.sleep(retry_after)
    resp.raise_for_status()
    return resp.json()


def get_artist_tracks(token: str) -> list[dict]:
    """Returns deduplicated list of {id, name} for all tracks by Poolpat.

    Uses album,single groups (no scope required for public artist data).
    """
    tracks: list[dict] = []
    seen: set[str] = set()
    for group in ("album", "single"):
        try:
            resp = spotify_get(
                f"/artists/{ARTIST_ID}/albums",
                token,
                {"include_groups": group, "limit": 50, "market": "IE"},
            )
            for album in resp.get("items", []):
                tracks_resp = spotify_get(
                    f"/albums/{album['id']}/tracks",
                    token,
                    {"limit": 50, "market": "IE"},
                )
                for t in tracks_resp.get("items", []):
                    tid = t.get("id")
                    if tid and tid not in seen:
                        seen.add(tid)
                        tracks.append({"id": tid, "name": t.get("name", "")})
        except requests.HTTPError as e:
            print(f"  ⚠ {group}: {e.response.status_code}", file=sys.stderr)
            continue
    return tracks


def find_playlists_for_track(track_id: str, track_name: str, token: str) -> list[dict]:
    """Search Spotify for public playlists containing the track."""
    try:
        resp = spotify_get(
            "/search",
            token,
            {"q": track_name, "type": "playlist", "limit": 20, "market": "IE"},
        )
    except requests.HTTPError as e:
        print(f"  ⚠ search '{track_name[:40]}': {e.response.status_code}", file=sys.stderr)
        return []
    found = []
    for pl in resp.get("playlists", {}).get("items", []) or []:
        if not pl:
            continue
        found.append(
            {
                "playlist_id": pl.get("id"),
                "name": pl.get("name"),
                "spotify_url": (pl.get("external_urls") or {}).get("spotify"),
                "owner": (pl.get("owner") or {}).get("display_name"),
                "track_id": track_id,
                "track_name": track_name,
            }
        )
    return found


# ---------------------------------------------------------------------------
# Playlistcheck (RapidAPI) — public catalogue, public stats
# ---------------------------------------------------------------------------
def enrich_with_playlistcheck(playlist_id: str, rapidapi_key: str) -> dict:
    try:
        resp = requests.get(
            PLAYLISTCHECK_URL,
            headers={
                "x-rapidapi-host": "playlistcheck.p.rapidapi.com",
                "x-rapidapi-key": rapidapi_key,
            },
            params={"playlist_id": playlist_id},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"  Playlistcheck error: {e}", file=sys.stderr)
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Poolpat Playlist Tracker (client_credentials) ===\n")

    rapidapi_key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not rapidapi_key:
        print("⚠ RAPIDAPI_KEY not set — playlist enrichment will be skipped")

    print("[1/4] Authenticating with Spotify (client_credentials)...")
    token = get_spotify_token()
    print("  ✅ access_token obtained")

    print("[2/4] Fetching artist track catalogue...")
    artist_tracks = get_artist_tracks(token)
    print(f"  ✅ {len(artist_tracks)} unique tracks")

    print("[3/4] Searching Spotify for playlists containing each track...")
    all_placements: dict[str, dict] = {}
    for t in artist_tracks:
        for p in find_playlists_for_track(t["id"], t["name"], token):
            pid = p["playlist_id"]
            if not pid:
                continue
            if pid not in all_placements:
                all_placements[pid] = {**p, "tracks_matched": [t["name"]]}
            else:
                all_placements[pid]["tracks_matched"].append(t["name"])

    playlists = list(all_placements.values())
    print(f"  ✅ {len(playlists)} unique playlists matched")

    if rapidapi_key and playlists:
        print(f"[4/4] Enriching {len(playlists)} playlists with Playlistcheck...")
        enriched: list[dict] = []
        for i, p in enumerate(playlists, 1):
            data = enrich_with_playlistcheck(p["playlist_id"], rapidapi_key)
            enriched.append({**p, **data})
            if i % 10 == 0:
                print(f"  {i}/{len(playlists)}")
        playlists = enriched
    else:
        print("[4/4] Skipping enrichment (no RAPIDAPI_KEY or no playlists)")

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "artist_id": ARTIST_ID,
        "auth_method": "client_credentials",
        "playlists": playlists,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically so a crash mid-write can't leave truncated JSON
    # for the workflow's commit step to push.
    tmp = OUTPUT_PATH.with_name(OUTPUT_PATH.name + ".tmp")
    tmp.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    os.replace(tmp, OUTPUT_PATH)
    print(f"\n✅ {len(playlists)} playlists → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
