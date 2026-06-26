#!/usr/bin/env python3
"""Fetch play counts for Poolpat across SoundCloud, Spotify, and Apple Music.

Key invariant: streaming counts are MONOTONICALLY INCREASING.
A new fetch must never reduce any play count below the previously recorded value.
If a fetch returns lower numbers (API failure, missing data), preserve the existing data.
"""

import csv
import json
import os
import re
import sys
import unicodedata
import defusedxml.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

_PIPELINE_DIR = Path(__file__).resolve().parent
DATA_DIR = _PIPELINE_DIR.parent / "data"
PLAYS_JSON = DATA_DIR / "plays.json"
HISTORY_CSV = DATA_DIR / "history.csv"
FAIL_TRACKER = DATA_DIR / ".fetch_failures.json"
# Cache of the last-working SoundCloud client_id. The id is public (scraped from
# SoundCloud's JS bundles) so committing it is harmless; persisting it lets a
# fresh CI checkout skip the fragile bundle scrape and reuse a known-good id.
SC_STATE = DATA_DIR / ".sc_state.json"

SOUNDCLOUD_URL = "https://soundcloud.com/poolpat"
SOUNDCLOUD_USER_ID = 3265651
SOUNDCLOUD_RSS = f"https://feeds.soundcloud.com/users/soundcloud:users:{SOUNDCLOUD_USER_ID}/sounds.rss"
SPOTIFY_ARTIST_ID = "4rr3o9anpUXitNXo0W4uX7"
APPLE_MUSIC_ARTIST_ID = "1716939831"
APPLE_MUSIC_ARTIST_URL = f"https://music.apple.com/us/artist/poolpat/{APPLE_MUSIC_ARTIST_ID}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

ALERT_THRESHOLD = 3  # consecutive failures before creating a GitHub Issue
STALE_AFTER_DAYS = 21  # warn when served SoundCloud data hasn't refreshed in this long


# ─── Monotonic helpers ───────────────────────────────────────────────────────

def _canon_display(title: str) -> str:
    """Display-safe title normalization: NFC composition + straight apostrophes.
    Letter case is preserved (we never lowercase a displayed title)."""
    s = unicodedata.normalize("NFC", title)
    for q in ("’", "‘", "ʼ"):  # curly / modifier apostrophes -> ASCII '
        s = s.replace(q, "'")
    return s


def _canon_key(title: str) -> str:
    """Comparison key folding the three display-equivalent variations that have
    produced phantom duplicate track rows: NFC/NFD composition, curly vs straight
    apostrophes, and ASCII letter case (plus edge whitespace, matching the old
    RSS fuzzy match)."""
    return _canon_display(title).casefold().strip()


def _num(v) -> float:
    return v if isinstance(v, (int, float)) else 0


def monotonic_merge_tracks(existing: dict, fetched: dict) -> dict:
    """Merge track dicts keeping the MAX play count per track; counts never decrease.
    New tracks from fetched are added; existing tracks absent from fetched are kept.
    Titles are compared via _canon_key so NFC/NFD, curly/straight-apostrophe, and
    letter-case variants of one track collapse to a single row — the highest-count
    variant supplies the display title (normalized to NFC + straight apostrophes)."""
    merged: dict = {}  # canon_key -> [display_title, plays]
    for title, plays in existing.items():
        k = _canon_key(title)
        if k not in merged or _num(plays) > _num(merged[k][1]):
            merged[k] = [_canon_display(title), plays]
    for title, plays in fetched.items():
        if not isinstance(plays, (int, float)) or plays <= 0:
            continue  # skip zero/null fetched values — keep existing
        k = _canon_key(title)
        if k not in merged:
            merged[k] = [_canon_display(title), plays]
        elif plays >= _num(merged[k][1]):
            merged[k][1] = plays  # monotonic increase; keep the established display title
    return {t: p for t, p in merged.values()}


def monotonic_total(existing_total: int, computed_total: int, label: str = "") -> int:
    """Return the higher of existing vs computed total. Streams never decrease.

    A computed total LOWER than the stored one is usually an API hiccup (correctly
    ignored), but a genuine drop — a deleted track or a counter reset/purge — is
    absorbed silently too. Warn to stderr so a real decrease is visible in the run
    log instead of vanishing; the stored value still wins and must be reset by hand."""
    e, c = existing_total or 0, computed_total or 0
    if c < e:
        where = f" [{label}]" if label else ""
        print(f"  ⚠ monotonic guard{where}: computed {c:,} < stored {e:,}; keeping stored "
              f"(reset the stored value by hand if this is a real purge/reset).", file=sys.stderr)
    return max(e, c)


def get_last_history_row() -> dict:
    """Read the last row of history.csv to enforce monotonic totals."""
    if not HISTORY_CSV.exists():
        return {}
    try:
        with open(HISTORY_CSV) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            return rows[-1] if rows else {}
    except Exception:
        return {}


# ─── SoundCloud ──────────────────────────────────────────────────────────────

def fetch_soundcloud_rss() -> list[dict]:
    """Parse the SoundCloud RSS feed — reliable, always returns track catalog (no play counts)."""
    tracks = []
    try:
        resp = requests.get(SOUNDCLOUD_RSS, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
        for item in root.findall(".//item"):
            title = item.findtext("title", "Unknown")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            duration = item.findtext("itunes:duration", "", ns)
            enclosure = item.find("enclosure")
            stream_url = enclosure.get("url", "") if enclosure is not None else ""
            img = item.find("itunes:image", ns)
            artwork = img.get("href", "") if img is not None else ""
            tracks.append({
                "title": title, "link": link, "pub_date": pub_date,
                "duration": duration, "stream_url": stream_url, "artwork": artwork,
            })
        print(f"  RSS: {len(tracks)} tracks from feed")
    except Exception as e:
        print(f"  RSS Error: {e}", file=sys.stderr)
    return tracks


def _get_soundcloud_client_id() -> str | None:
    """Try to extract a client_id from SoundCloud's JS bundles."""
    try:
        resp = requests.get("https://soundcloud.com", headers=HEADERS, timeout=15)
        for match in re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', resp.text):
            js_resp = requests.get(match, headers=HEADERS, timeout=10)
            cid_match = re.search(r'client_id:"([a-zA-Z0-9]+)"', js_resp.text)
            if cid_match:
                return cid_match.group(1)
    except Exception:
        pass
    return None


def _load_sc_client_id_cache() -> str | None:
    """Return the last-working client_id from disk, or None if absent/unreadable.
    A corrupt cache must never kill the fetch — we just fall through to a scrape."""
    try:
        if SC_STATE.exists():
            with open(SC_STATE) as f:
                cid = json.load(f).get("client_id")
                return cid if isinstance(cid, str) and cid else None
    except (json.JSONDecodeError, OSError) as e:
        print(f"  client_id cache unreadable ({e}), will scrape", file=sys.stderr)
    return None


def _save_sc_client_id_cache(client_id) -> None:
    """Persist a known-good client_id. Silently no-ops on a non-str (e.g. a test
    mock) or a write error — the cache is an optimization, never load-bearing."""
    if not isinstance(client_id, str) or not client_id:
        return
    try:
        _atomic_write_json(SC_STATE, {"client_id": client_id})
    except OSError as e:
        print(f"  client_id cache write failed ({e})", file=sys.stderr)


def resolve_soundcloud_client_id() -> tuple[str | None, str]:
    """Resolve a client_id, preferring cheap/robust sources over the fragile scrape.

    Order: SOUNDCLOUD_CLIENT_ID env override → on-disk cache → live JS-bundle
    scrape. Returns (client_id, source) where source is 'env' | 'cache' | 'scrape'
    so the caller can re-scrape if a stale cached/env id stops working."""
    env_cid = os.environ.get("SOUNDCLOUD_CLIENT_ID", "").strip()
    if env_cid:
        return env_cid, "env"
    cached = _load_sc_client_id_cache()
    if cached:
        return cached, "cache"
    return _get_soundcloud_client_id(), "scrape"


def _is_stale(iso_timestamp, now: datetime) -> bool:
    """True if iso_timestamp is older than STALE_AFTER_DAYS. Unparseable or missing
    timestamps are treated as NOT stale (we don't warn on data we can't date)."""
    if not iso_timestamp or not isinstance(iso_timestamp, str):
        return False
    try:
        last = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last).days > STALE_AFTER_DAYS


def fetch_soundcloud_plays_v2(client_id: str | None = None) -> dict[str, int]:
    """Fetch play counts via SoundCloud's v2 API with pagination."""
    tracks = {}
    try:
        if not client_id:
            client_id = _get_soundcloud_client_id()

        offset = 0
        limit = 50
        while True:
            url = (
                f"https://api-v2.soundcloud.com/users/{SOUNDCLOUD_USER_ID}/tracks"
                f"?limit={limit}&offset={offset}"
            )
            if client_id:
                url += f"&client_id={client_id}"

            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                print(f"  v2 API: HTTP {resp.status_code} at offset {offset}")
                break

            data = resp.json()
            collection = data.get("collection", [])
            if not collection:
                break

            for item in collection:
                title = item.get("title", "Unknown")
                plays = item.get("playback_count", 0) or 0
                tracks[title] = plays

            next_href = data.get("next_href")
            if not next_href or len(collection) < limit:
                break
            offset += limit

        print(f"  v2 API: {len(tracks)} tracks with play counts")
    except Exception as e:
        print(f"  v2 API Error: {e}", file=sys.stderr)
    return tracks


def fetch_soundcloud_profile(client_id: str | None = None) -> dict:
    """Fetch profile info (track_count, followers_count)."""
    try:
        url = f"https://api-v2.soundcloud.com/users/{SOUNDCLOUD_USER_ID}"
        if client_id:
            url += f"?client_id={client_id}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def fetch_soundcloud_all(existing_sc: dict) -> tuple[dict, list[dict], bool]:
    """
    Fetch SoundCloud data. Returns (sc_data_dict, rss_tracks, got_plays).

    CRITICAL: Only update play counts if the API returned real numbers (total > 0).
    RSS feed is always used for the track catalog but NEVER
    for play counts (it doesn't have them).
    """
    print("\n--- SoundCloud ---")

    client_id, cid_source = resolve_soundcloud_client_id()
    print(f"  client_id source: {cid_source}")
    rss_tracks = fetch_soundcloud_rss()
    api_plays = fetch_soundcloud_plays_v2(client_id)
    profile = fetch_soundcloud_profile(client_id)

    # Did the API return any real play counts?
    api_total = sum(api_plays.values())
    got_plays = api_total > 0

    # A cached/env client_id can silently rotate out from under us. If it returned
    # nothing, re-scrape a fresh id once before falling back to preserve-existing.
    if not got_plays and cid_source != "scrape":
        print(f"  client_id from {cid_source} returned no plays — re-scraping a fresh id")
        client_id = _get_soundcloud_client_id()
        api_plays = fetch_soundcloud_plays_v2(client_id)
        profile = fetch_soundcloud_profile(client_id) or profile
        api_total = sum(api_plays.values())
        got_plays = api_total > 0

    existing_tracks = existing_sc.get("tracks", {})
    existing_total = existing_sc.get("total_plays", 0) or 0

    if got_plays:
        # Merge API data with existing, keeping the MAX per track (monotonic)
        merged = monotonic_merge_tracks(existing_tracks, api_plays)

        # Add any RSS-only titles not already present. Compare via _canon_key so an
        # NFD / curly-apostrophe / differently-cased feed title can't re-create a
        # duplicate row (the bug this dedup exists to kill).
        canon_seen = {_canon_key(k) for k in merged}
        for rt in rss_tracks:
            title = _canon_display(rt["title"])
            if _canon_key(title) not in canon_seen:
                merged[title] = 0  # new track, no plays yet
                canon_seen.add(_canon_key(title))

        new_total = sum(v for v in merged.values() if isinstance(v, (int, float)))
        final_total = monotonic_total(existing_total, new_total, "SoundCloud")

        print(f"  Merged: {len(merged)} tracks, {final_total:,} total plays (was {existing_total:,})")

        sc_data = {
            "url": SOUNDCLOUD_URL,
            "tracks": merged,
            "total_plays": final_total,
            "total_tracks": profile.get("track_count", len(merged)),
            "followers": profile.get("followers_count", existing_sc.get("followers", 0)),
            "fetch_status": "success",
            "last_successful_fetch": datetime.now(timezone.utc).isoformat(),
        }
        # Preserve manually-entered Insights metrics (not available via API).
        for key in ("total_listeners",
                    "total_streams_sc", "total_downloads", "source"):
            if key in existing_sc:
                sc_data[key] = existing_sc[key]

        # Remember the client_id that just worked so the next run can skip the scrape.
        _save_sc_client_id_cache(client_id)
    else:
        # API failed — preserve ALL existing data, only update catalog from RSS
        print(f"  WARN: API returned 0 plays, preserving existing data ({existing_total:,} plays)")

        sc_data = dict(existing_sc)
        sc_data["fetch_status"] = "api_failed_preserved"
        # Update profile info if we got it
        if profile:
            sc_data["total_tracks"] = profile.get("track_count", sc_data.get("total_tracks", 0))
            sc_data["followers"] = profile.get("followers_count", sc_data.get("followers", 0))

    # Surface silent degradation: if we're serving data whose last successful
    # fetch is stale, the weekly auto-fetch has quietly stopped landing real plays.
    if _is_stale(sc_data.get("last_successful_fetch"), datetime.now(timezone.utc)):
        print(f"  ⚠ SoundCloud data is stale (last successful fetch "
              f"{sc_data.get('last_successful_fetch')}, >{STALE_AFTER_DAYS}d ago)",
              file=sys.stderr)

    return sc_data, rss_tracks, got_plays


# ─── Spotify ─────────────────────────────────────────────────────────────────

def _get_spotify_token() -> str | None:
    """Get Spotify access token via client credentials or anonymous."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if client_id and client_secret:
        try:
            resp = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret), timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
        except Exception as e:
            print(f"  Client credentials error: {e}", file=sys.stderr)
    # Fallback: anonymous
    try:
        resp = requests.get(
            "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
            headers=HEADERS, timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("accessToken")
    except Exception:
        pass
    return None


def fetch_spotify_all(existing_sp: dict) -> tuple[dict, bool]:
    """
    Fetch Spotify data. Returns (sp_data_dict, got_data).

    If SPOTIFY_REFRESH_TOKEN is set, uses the user-scoped Authorization Code
    flow (PKCE) to fetch top tracks and recently played with real data.
    Otherwise falls back to Client Credentials (public popularity scores only).
    """
    print("\n--- Spotify ---")

    # ── Try user-scoped auth first (PKCE refresh token) ──
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")

    user_data_fetched = False
    top_tracks_short = []
    top_tracks_medium = []
    top_tracks_long = []
    recently_played = []

    if refresh_token and client_id:
        try:
            from spotify_auth import refresh_access_token
            from spotify_client import SpotifyClient

            tokens = refresh_access_token(client_id, refresh_token)
            client = SpotifyClient(tokens["access_token"], client_id, refresh_token)

            user = client.get_current_user()
            print(f"  Authenticated as: {user.get('display_name', 'unknown')} ({user.get('product', 'free')})")

            top_tracks_short = [
                {"name": t["name"], "popularity": t.get("popularity", 0)}
                for t in client.get_top_tracks("short_term", 50)
            ]
            top_tracks_medium = [
                {"name": t["name"], "popularity": t.get("popularity", 0)}
                for t in client.get_top_tracks("medium_term", 50)
            ]
            top_tracks_long = [
                {"name": t["name"], "popularity": t.get("popularity", 0)}
                for t in client.get_top_tracks("long_term", 50)
            ]
            recently_played = [
                {"name": t["track"]["name"], "played_at": t["played_at"]}
                for t in client.get_recently_played(50)
            ]

            print(f"  User data: {len(top_tracks_short)} short-term, {len(top_tracks_medium)} medium-term, {len(top_tracks_long)} long-term top tracks")
            print(f"  Recently played: {len(recently_played)} tracks")
            user_data_fetched = True

        except Exception as e:
            print(f"  User auth failed ({e}), falling back to public API", file=sys.stderr)

    # ── Public API: catalog + popularity scores ──
    token = _get_spotify_token()
    if not token and not user_data_fetched:
        print("  ERROR: No Spotify token", file=sys.stderr)
        sp_data = dict(existing_sp) if existing_sp else {}
        sp_data["fetch_status"] = "failed"
        return sp_data, False

    fetched_tracks = {}
    if token:
        api_headers = {"Authorization": f"Bearer {token}"}

        try:
            album_ids = set()
            for group in ["album", "single", "appears_on", "compilation"]:
                offset = 0
                while True:
                    resp = requests.get(
                        f"https://api.spotify.com/v1/artists/{SPOTIFY_ARTIST_ID}/albums",
                        headers=api_headers,
                        params={"include_groups": group, "market": "US", "limit": 50, "offset": offset},
                        timeout=30,
                    )
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    for album in data.get("items", []):
                        album_ids.add(album["id"])
                    if not data.get("next"):
                        break
                    offset += 50

            print(f"  Found {len(album_ids)} albums/singles")

            track_ids = set()
            album_list = list(album_ids)
            for i in range(0, len(album_list), 20):
                batch = album_list[i:i+20]
                resp = requests.get(
                    "https://api.spotify.com/v1/albums",
                    headers=api_headers,
                    params={"ids": ",".join(batch), "market": "US"}, timeout=30,
                )
                if resp.status_code == 200:
                    for album in resp.json().get("albums", []):
                        if not album:
                            continue
                        for track in album.get("tracks", {}).get("items", []):
                            if SPOTIFY_ARTIST_ID in [a["id"] for a in track.get("artists", [])]:
                                track_ids.add(track["id"])

            print(f"  Found {len(track_ids)} tracks by Poolpat")

            # NOTE: this public-token catalog path uses raw requests.get rather
            # than SpotifyClient. A full swap (typed retry/429 handling) is
            # deferred: the orchestration tests mock requests.get by exact call
            # sequence, the client uses a Session those mocks don't intercept,
            # and this weekly fetch already preserves existing data on failure.
            track_id_list = list(track_ids)
            for i in range(0, len(track_id_list), 50):
                batch = track_id_list[i:i + 50]
                resp = requests.get(
                    "https://api.spotify.com/v1/tracks",
                    headers=api_headers,
                    params={"ids": ",".join(batch), "market": "US"}, timeout=30,
                )
                if resp.status_code == 200:
                    for track in resp.json().get("tracks", []):
                        if track:
                            fetched_tracks[track["name"]] = track.get("popularity", 0)

        except Exception as e:
            print(f"  Spotify catalog error: {e}", file=sys.stderr)

    got_data = len(fetched_tracks) > 0 or user_data_fetched

    existing_total_streams = existing_sp.get("total_streams", 0) or 0
    existing_monthly = existing_sp.get("monthly_listeners")
    existing_streams_28d = existing_sp.get("streams_28d")
    existing_source = existing_sp.get("source", "")

    if got_data:
        existing_tracks = existing_sp.get("tracks", {})
        merged = monotonic_merge_tracks(existing_tracks, fetched_tracks) if fetched_tracks else dict(existing_tracks)

        sp_data = {
            "url": f"https://open.spotify.com/artist/{SPOTIFY_ARTIST_ID}",
            "artist_id": SPOTIFY_ARTIST_ID,
            "source": existing_source if existing_source else "Spotify API (popularity 0-100)",
            "tracks": merged,
            "total_streams": existing_total_streams,
            "total_tracks": max(int(existing_sp.get("total_tracks", 0) or 0), len(merged), 21),
            "monthly_listeners": existing_monthly,
            "streams_28d": existing_streams_28d,
            "fetch_status": "success",
            "last_successful_fetch": datetime.now(timezone.utc).isoformat(),
            "auth_method": "user_token" if user_data_fetched else "client_credentials",
            "note": "total_streams/monthly_listeners from Spotify for Artists (manual). Track values are popularity scores.",
        }

        if user_data_fetched:
            sp_data["top_tracks_short"] = [t["name"] for t in top_tracks_short]
            sp_data["top_tracks_medium"] = [t["name"] for t in top_tracks_medium]
            sp_data["top_tracks_long"] = [t["name"] for t in top_tracks_long]

    else:
        sp_data = dict(existing_sp) if existing_sp else {}
        sp_data["fetch_status"] = "failed"

    print(f"  Result: {len(fetched_tracks)} catalog tracks, total_streams={existing_total_streams:,} (preserved), user_data={'yes' if user_data_fetched else 'no'}")
    return sp_data, got_data


# ─── Apple Music ─────────────────────────────────────────────────────────────

def fetch_apple_music_all(existing_am: dict) -> tuple[dict, bool]:
    """
    Apple Music: public API has no play counts.
    All play data comes from manual entry (Apple Music for Artists).
    This function only updates catalog metadata, never touches play counts.
    """
    print("\n--- Apple Music ---")
    track_names = []
    apple_token = os.environ.get("APPLE_MUSIC_TOKEN", "").strip()

    try:
        if apple_token:
            resp = requests.get(
                f"https://api.music.apple.com/v1/catalog/us/artists/{APPLE_MUSIC_ARTIST_ID}/songs",
                headers={"Authorization": f"Bearer {apple_token}", "User-Agent": HEADERS["User-Agent"]},
                timeout=30,
            )
            if resp.status_code == 200:
                for song in resp.json().get("data", []):
                    track_names.append(song.get("attributes", {}).get("name", "Unknown"))
                print(f"  Apple Music API: {len(track_names)} catalog tracks")
            else:
                print(f"  Apple Music API: HTTP {resp.status_code} (token may be expired)", file=sys.stderr)
        else:
            print("  APPLE_MUSIC_TOKEN not set — skipping API, trying web scrape")

        if not track_names:
            resp = requests.get(APPLE_MUSIC_ARTIST_URL, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get("@type") == "MusicGroup":
                            for track in data.get("track", []):
                                track_names.append(track.get("name", "Unknown"))
                    except (json.JSONDecodeError, TypeError):
                        continue
                print(f"  Apple Music scrape: {len(track_names)} catalog tracks")
            else:
                print(f"  Apple Music scrape: HTTP {resp.status_code}", file=sys.stderr)

    except requests.exceptions.Timeout:
        print("  Apple Music: request timed out", file=sys.stderr)
    except requests.exceptions.ConnectionError:
        print("  Apple Music: connection failed (check network)", file=sys.stderr)
    except Exception as e:
        print(f"  Apple Music error: {e}", file=sys.stderr)

    # Always preserve existing manual data
    has_manual = bool(existing_am.get("tracks")) and any(
        isinstance(v, (int, float)) and v > 0
        for v in existing_am.get("tracks", {}).values()
    )

    if has_manual:
        am_data = dict(existing_am)
        am_data["fetch_status"] = "preserved"
        if track_names:
            am_data["catalog_track_count"] = len(track_names)
        return am_data, True
    else:
        am_data = {
            "url": APPLE_MUSIC_ARTIST_URL,
            "tracks": {name: None for name in track_names},
            "total_tracks": max(int(existing_am.get("total_tracks", 0) or 0), len(track_names), 21),
            "note": "Apple Music does not expose play counts. Update manually from Apple Music for Artists.",
            "fetch_status": "catalog_only" if track_names else "failed",
        }
        return am_data, len(track_names) > 0


# ─── Failure tracking & alerting ─────────────────────────────────────────────

def load_failure_tracker() -> dict:
    defaults = {"soundcloud": 0, "spotify": 0, "apple_music": 0}
    if FAIL_TRACKER.exists():
        try:
            with open(FAIL_TRACKER) as f:
                return {**defaults, **json.load(f)}
        except (json.JSONDecodeError, OSError) as e:
            # Tracker is expendable — a corrupt file must not kill the fetch.
            print(f"  WARN: failure tracker unreadable ({e}), resetting", file=sys.stderr)
    return defaults


def save_failure_tracker(tracker: dict) -> None:
    _atomic_write_json(FAIL_TRACKER, tracker)


def _existing_alert_issue(platform: str, token: str, repo: str) -> bool:
    """True if an open auto-created alert issue for this platform already exists."""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            params={"labels": "automated", "state": "open", "per_page": 100},
            timeout=30,
        )
        if resp.status_code == 200:
            return any(
                platform in issue.get("title", "") and "fetch failed" in issue.get("title", "")
                for issue in resp.json()
            )
        print(f"  ALERT: issue lookup HTTP {resp.status_code}, assuming none open", file=sys.stderr)
    except Exception as e:
        print(f"  ALERT: issue lookup error: {e}", file=sys.stderr)
    return False


def create_alert_issue(platform: str, consecutive: int) -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print(f"  ALERT: {platform} failed {consecutive}x (no GH token)")
        return
    if _existing_alert_issue(platform, token, repo):
        print(f"  ALERT: open issue for {platform} already exists, skipping")
        return
    try:
        resp = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={
                "title": f"🔴 {platform} fetch failed {consecutive}x consecutively",
                "body": (
                    f"The automated fetcher failed to retrieve data from **{platform}** "
                    f"for **{consecutive} consecutive runs**.\n\n"
                    f"Check the workflow logs and update the fetcher.\n\n"
                    f"_Auto-created by `fetch_plays.py`._"
                ),
                "labels": ["bug", "automated"],
            },
            timeout=30,
        )
        if resp.status_code == 201:
            print(f"  ALERT: Created GitHub Issue for {platform}")
        else:
            print(f"  ALERT: issue creation failed HTTP {resp.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"  ALERT error: {e}", file=sys.stderr)


# ─── Data I/O ────────────────────────────────────────────────────────────────

def _atomic_write_json(path: Path, data) -> None:
    """Serialize to a temp file, then os.replace() so a crash mid-write can
    never leave a truncated JSON file (which the commit step would push)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load_existing_data() -> dict:
    # NOTE: a corrupt plays.json must abort loudly — silently starting from {}
    # would zero the monotonic baseline.
    if PLAYS_JSON.exists():
        with open(PLAYS_JSON) as f:
            return json.load(f)
    return {}


def save_plays_json(data: dict) -> None:
    _atomic_write_json(PLAYS_JSON, data)
    print(f"\nSaved {PLAYS_JSON}")


def append_history_csv(data: dict) -> None:
    """Append a history row. MONOTONIC: never record a value lower than the previous row."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = HISTORY_CSV.exists()

    last = get_last_history_row()
    # Tolerant read-back: a hand-edited float like "4108.0" must not crash int()
    # on the NEXT run (it previously aborted append_history_csv and main).
    def _prev_int(*keys):
        for k in keys:
            if k in last:
                return int(float(last.get(k) or 0))
        return 0
    prev_sc = _prev_int("soundcloud_total_plays")
    prev_sp = _prev_int("spotify_total_streams", "spotify_total_popularity")
    prev_am = _prev_int("apple_music_total_plays")
    prev_sc_tc = _prev_int("soundcloud_track_count")
    prev_sp_tc = _prev_int("spotify_track_count")
    prev_am_tc = _prev_int("apple_music_track_count")

    sc = data.get("soundcloud", {})
    sp = data.get("spotify", {})
    am = data.get("apple_music", {})

    # Totals are written as ints so the column type stays stable across runs.
    sc_total = max(prev_sc, int(round(sc.get("total_plays", 0) or 0)))
    sp_total = max(prev_sp, int(round(sp.get("total_streams", 0) or 0)))
    am_total = max(prev_am, int(round(am.get("total_plays", 0) or 0)))
    # track_count columns are monotonic too: a failed fetch yields an empty tracks
    # dict; clamping to the prior value prevents a one-row dip to 0 in history.
    sc_tc = max(prev_sc_tc, len(sc.get("tracks", {})))
    sp_tc = max(prev_sp_tc, len(sp.get("tracks", {})))
    am_tc = max(prev_am_tc, len(am.get("tracks", {})))

    fieldnames = [
        "timestamp", "soundcloud_total_plays", "soundcloud_track_count",
        "spotify_total_streams", "spotify_track_count",
        "apple_music_total_plays", "apple_music_track_count",
    ]

    with open(HISTORY_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": data.get("last_updated", datetime.now(timezone.utc).isoformat()),
            "soundcloud_total_plays": sc_total,
            "soundcloud_track_count": sc_tc,
            "spotify_total_streams": sp_total,
            "spotify_track_count": sp_tc,
            "apple_music_total_plays": am_total,
            "apple_music_track_count": am_tc,
        })
    print(f"History: SC={sc_total:,} SP={sp_total:,} AM={am_total:,}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc).isoformat()
    print(f"Fetching play counts at {now}")

    existing = load_existing_data()
    failures = load_failure_tracker()

    # ── SoundCloud ──
    sc_data, _, sc_ok = fetch_soundcloud_all(existing.get("soundcloud", {}))
    if sc_ok:
        failures["soundcloud"] = 0
    else:
        failures["soundcloud"] = failures.get("soundcloud", 0) + 1
        if failures["soundcloud"] >= ALERT_THRESHOLD:
            create_alert_issue("SoundCloud", failures["soundcloud"])

    # ── Spotify ──
    sp_data, sp_ok = fetch_spotify_all(existing.get("spotify", {}))
    if sp_ok:
        failures["spotify"] = 0
    else:
        failures["spotify"] = failures.get("spotify", 0) + 1
        if failures["spotify"] >= ALERT_THRESHOLD:
            create_alert_issue("Spotify", failures["spotify"])

    # ── Apple Music ──
    am_data, am_ok = fetch_apple_music_all(existing.get("apple_music", {}))
    if am_ok:
        failures["apple_music"] = 0
    else:
        failures["apple_music"] = failures.get("apple_music", 0) + 1
        if failures["apple_music"] >= ALERT_THRESHOLD:
            create_alert_issue("Apple Music", failures["apple_music"])

    save_failure_tracker(failures)

    # ── Assemble & save ──
    data = {
        "artist": "Poolpat",
        "last_updated": now,
        "soundcloud": sc_data,
        "spotify": sp_data,
        "apple_music": am_data,
    }

    sc_t = sc_data.get("total_plays", 0) or 0
    sp_t = sp_data.get("total_streams", 0) or 0
    am_t = am_data.get("total_plays", 0) or 0

    save_plays_json(data)
    append_history_csv(data)

    print(f"\nGrand total: {sc_t + sp_t + am_t:,}")
    print(f"  SC: {sc_t:,} ({len(sc_data.get('tracks', {}))} tracks) [{sc_data.get('fetch_status')}]")
    print(f"  SP: {sp_t:,} ({len(sp_data.get('tracks', {}))} tracks) [{sp_data.get('fetch_status')}]")
    print(f"  AM: {am_t:,} ({len(am_data.get('tracks', {}))} tracks) [{am_data.get('fetch_status')}]")


if __name__ == "__main__":
    main()
