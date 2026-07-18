"""Fetch all-platform play totals from SoundCloud Insights and update
data/insights.json + data/plays.json.

SoundCloud has no API for the "All Platforms" numbers — they only exist on the
logged-in SoundCloud for Artists Insights page. That page is server-rendered
(Next.js flight data), so a plain GET with a logged-in session's Cookie header
is enough; no browser needed.

Auth: the SC_COOKIE env var holds the raw Cookie header of a logged-in
soundcloud.com session (copy it from DevTools → Network → any soundcloud.com
request → Request Headers → cookie). It expires after some weeks; when this
script starts failing, paste a fresh one into the repo secret:

    gh secret set SC_COOKIE

Never logged, never passed via argv.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

INSIGHTS_URL = (
    "https://soundcloud.com/n/you/insights/distributed"
    "?timewindow=ALL_TIME&resolution=YEAR&embedded"
)
# Canonical UI URL, recorded as the source in insights.json.
SOURCE_URL = (
    "https://soundcloud.com/you/insights/distributed"
    "?timewindow=ALL_TIME&resolution=YEAR"
)

# Matches {"dsp":"SPOTIFY","plays":20354} inside the flight data, where quotes
# arrive backslash-escaped (\" or \\\") depending on nesting depth.
DSP_RE = re.compile(
    r'dsp\\*":\\*"(SOUNDCLOUD|SPOTIFY|APPLE|GLOBAL)\\*",\\*"plays\\*":(\d+)'
)


def parse_totals(html):
    """Extract {'SOUNDCLOUD','SPOTIFY','APPLE','GLOBAL'} play totals.

    The dehydrated state can contain several dsp/plays groups (other
    timewindows, other queries), so take the first window of 4 consecutive
    matches that has all four platforms AND whose three DSPs sum exactly to
    GLOBAL. Returns None if no window validates — expired cookie (login page)
    and layout changes both land here.
    """
    matches = [(dsp, int(n)) for dsp, n in DSP_RE.findall(html)]
    for i in range(len(matches) - 3):
        window = dict(matches[i : i + 4])
        if len(window) == 4 and (
            window["SOUNDCLOUD"] + window["SPOTIFY"] + window["APPLE"]
            == window["GLOBAL"]
        ):
            return window
    return None


def _write_json(path, data, trailing_newline):
    """tmp + os.replace so a crash can never leave truncated JSON — same
    pattern as fetch_plays._atomic_write_json."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            if trailing_newline:
                f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def update_files(totals, data_dir, now_iso):
    """Write insights.json and monotonically bump plays.json.

    Returns a one-line change summary, or None if nothing changed.
    Raises ValueError if the scraped total is lower than the stored one —
    GLOBAL always equals the sum of its own group, so a wrong-timewindow
    group would pass parse_totals' sum check; a total that went *down* is
    the loud signal that parsing (or SoundCloud) needs a human look.
    """
    insights_path = data_dir / "insights.json"
    try:
        old = json.loads(insights_path.read_text())
    except (OSError, ValueError):
        old = {}

    scraped = {
        "total_plays": totals["GLOBAL"],
        "soundcloud_plays": totals["SOUNDCLOUD"],
        "spotify_plays": totals["SPOTIFY"],
        "apple_music_plays": totals["APPLE"],
    }
    stored_total = old.get("total_plays")
    if isinstance(stored_total, int) and scraped["total_plays"] < stored_total:
        raise ValueError(
            f"scraped total {scraped['total_plays']} < stored {stored_total} — "
            "wrong-timewindow parse or a SoundCloud purge; not writing anything"
        )

    # Read + validate plays.json BEFORE writing anything, so a bad file can't
    # leave the insights/plays pair inconsistent on disk.
    plays_path = data_dir / "plays.json"
    plays = json.loads(plays_path.read_text())
    old_spotify = plays["spotify"]["total_streams"]
    old_am = plays["apple_music"]["total_plays"]
    # Monotonic invariant: a play count never decreases. SoundCloud's own
    # total is owned by the weekly fetch-data workflow — never touched here.
    new_spotify = max(old_spotify, scraped["spotify_plays"])
    new_am = max(old_am, scraped["apple_music_plays"])

    insights_changed = any(old.get(k) != v for k, v in scraped.items())
    plays_changed = (new_spotify, new_am) != (old_spotify, old_am)
    if not insights_changed and not plays_changed:
        return None

    if insights_changed:
        insights = {
            "fetched_at": now_iso,
            "source": SOURCE_URL,
            "method": "CI fetch (SC_COOKIE session, server-rendered SoundCloud "
            "Insights, All Platforms / All Time)",
            **scraped,
        }
        _write_json(insights_path, insights, trailing_newline=True)

    if plays_changed:
        plays["spotify"]["total_streams"] = new_spotify
        plays["apple_music"]["total_plays"] = new_am
        # No trailing newline — matches fetch_plays._atomic_write_json,
        # whose next weekly run rewrites this file.
        _write_json(plays_path, plays, trailing_newline=False)

    return (
        f"insights: total {old.get('total_plays', '?')}->{scraped['total_plays']}, "
        f"spotify {old_spotify}->{new_spotify}, "
        f"am {old_am}->{new_am}"
    )


def main():
    cookie = os.environ.get("SC_COOKIE")
    if not cookie:
        sys.exit("::error::SC_COOKIE is not set")

    resp = requests.get(
        INSIGHTS_URL,
        headers={
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=30,
    )
    if resp.status_code in (401, 403):
        # 403 is usually DataDome bot-blocking, 401 an expired session.
        sys.exit(
            f"::error::HTTP {resp.status_code} from Insights — session expired "
            "or bot-blocked; refresh the SC_COOKIE secret"
        )
    resp.raise_for_status()

    totals = parse_totals(resp.text)
    if totals is None:
        sys.exit(
            "::error::no valid platform totals in response — expired SC_COOKIE "
            "(login page served) or the Insights page layout changed"
        )

    try:
        summary = update_files(
            totals,
            Path(__file__).resolve().parent.parent / "data",
            datetime.now(timezone.utc).isoformat(),
        )
    except ValueError as e:
        sys.exit(f"::error::{e}")
    print(summary or "no change — stored values already current")


if __name__ == "__main__":
    main()
