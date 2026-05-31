# poolpat-portfolio — Development Guide

Developer setup, data-pipeline internals, and integration notes for `poolpat-portfolio`.
For the public-facing artist page, see the root [README.md](../README.md) and the
[live site](https://thepoolpat.github.io/poolpat-portfolio/).

## Pages

| Route | Description |
|-------|-------------|
| `/` | Home — hero carousel, live stats summary, platform links |
| `/stats/` | Play count trends (Chart.js), per-platform breakdowns, top tracks |
| `/discography/` | Release card grid with artwork, chart badges |
| `/releases/[slug]/` | Per-release liner notes, track listings, Apple Music CTAs |

## Stack

- **Framework:** [Astro](https://astro.build/) 6.x (static output, zero JS by default)
- **Data pipeline:** Python (`pipeline/fetch_plays.py`) — fetches SoundCloud, Spotify, Apple Music weekly via GitHub Actions
- **Spotify auth:** OAuth 2.0 Authorization Code Flow with PKCE (user-scoped data); hand-rolled `requests` client (`spotify_client.py`), not spotipy
- **Affiliate links:** `packages/affiliate-helper/js/` — validated Apple Music URLs with campaign tracking
- **Design system:** Dark/light theme (system fonts, Apple Music red accent)
- **Charts:** Chart.js 4 (loaded async via ES module import, non-blocking)

## Project Structure

```
├── .github/workflows/
│    ├── deploy.yml               # Build Astro → deploy to GitHub Pages
│    └── fetch-data.yml           # Weekly Python pipeline (cron 0 6 * * 0)
├── packages/affiliate-helper/   # Apple Music affiliate link builder (JS)
├── pipeline/
│    ├── fetch_plays.py           # Multi-platform play count scraper
│    ├── spotify_auth.py          # Spotify PKCE OAuth flow
│    ├── spotify_client.py        # Spotify API client (typed, with retry)
│    ├── spotify_errors.py        # Typed error hierarchy
│    ├── requirements.txt
│    └── tests/                   # 118 unit tests
├── dev/                         # Dev-only tooling (not in CI, except gen_world_geo.mjs)
│    ├── gen_world_geo.mjs       # Load-bearing geo generator for the listener map
│    ├── examples/               # Experimental Spotify demos (not in CI)
│    ├── setup_*.sh / setup_*.py # Experimental setup scripts (not in CI)
│    ├── config/                 # camoufox_spotify.json
│    └── spotify_logs/           # Local analytics DBs (gitignored) + spotify_export.csv
├── data/                        # Auto-committed by pipeline
│    ├── plays.json               # Latest play count snapshot
│    ├── history.csv              # Time-series (appended weekly)
│    └── rss_tracks.json          # SoundCloud catalog
├── public/artwork/              # Release cover images (1200px, web-optimized)
└── src/
     ├── data/releases.json       # Hand-maintained release catalog (7 releases)
     ├── layouts/Base.astro       # HTML shell, SEO, a11y
     ├── components/              # Astro components
     ├── pages/                   # Route pages
     └── styles/global.css        # Unified design tokens
```

## Camoufox + Discord Spotify logging (local/experimental, not in CI)

> **Note:** This is a local-only, experimental playback-logging path. It does
> **not** run in CI and is not part of the deployed site or the weekly pipeline.
> The runnable code lives under `dev/` (see `dev/examples/` and the `dev/setup_*`
> scripts); its SQLite analytics DBs and CSV exports are written to the
> gitignored `dev/spotify_logs/` directory. Configure it via
> `dev/config/camoufox_spotify.json` and a local, never-committed Spotify env
> file. Treat anything here as a personal experiment, not a supported feature.

## Setup

```bash
# Install dependencies
npm install
pip3 install -r pipeline/requirements.txt

# Development server
npm run dev

# Production build (public GitHub Pages)
DEPLOY_TARGET=public npm run build

# TypeScript check
npm run check
```

### Spotify Setup (one-time)

1. Register an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Add redirect URI: `http://127.0.0.1:8888/callback`
3. Run the auth flow:
    ```bash
    python3 pipeline/spotify_auth.py
    # Enter your Client ID when prompted
    # Authorize in browser → get refresh token
    ```
4. Add secrets to [GitHub Actions](../../../settings/secrets/actions):
    - `SPOTIFY_CLIENT_ID`
    - `SPOTIFY_CLIENT_SECRET`
    - `SPOTIFY_REFRESH_TOKEN`

### Running the Pipeline Locally

```bash
# Create .env (not committed)
cp pipeline/.env.example .env
# Fill in your credentials, then:

set -a && source .env && set +a
python3 pipeline/fetch_plays.py
```

> **Note:** Use `set -a` before `source .env` to export the variables. Plain `source .env` sets them but doesn't export to subprocesses.

## Data Pipeline

The Python fetcher runs weekly (`fetch-data.yml`, cron `0 6 * * 0` — Sundays
06:00 UTC) via GitHub Actions:

1. **Spotify (user-scoped):** PKCE refresh token → top tracks (short/medium/long term), recently played
2. **Spotify (public):** Client Credentials → catalog popularity scores (0-100)
3. **SoundCloud:** RSS feed + v2 API → play counts, catalog metadata
4. **Apple Music:** API or web scraping → track catalog (plays are manual entry)
5. Enforces a **monotonic invariant** — play counts never decrease between fetches
6. Commits updated `data/` files to `main` → triggers site rebuild

### Required Secrets

| Secret | Purpose |
|--------|---------|
| `SPOTIFY_CLIENT_ID` | Spotify API access |
| `SPOTIFY_CLIENT_SECRET` | Spotify API access |
| `SPOTIFY_REFRESH_TOKEN` | User-scoped Spotify data (PKCE) |
| `CAMOUXF_HOME` | Camoufox cache directory (local-first mode) |
| `APPLE_MUSIC_TOKEN` | Apple Music API access (optional — requires paid Developer Program) |

### Platform Notes

- **Spotify:** `total_streams` and `monthly_listeners` are preserved from manual entry (Spotify for Artists). The API provides popularity scores and top tracks.
- **Camoufox:** Local/experimental only — not part of this weekly pipeline. (Before the 2026-05-06 consolidation, an earlier local-first playback feed fed both the former `poolpat-plays` repo and this one; that path is now dev-only — see the note above.)
- **Apple Music:** Play counts are manual entry only. API token requires paid Apple Developer Program ($99/yr). Data preserved at current values when token unavailable.
- **SoundCloud:** Fully automated via v2 API + RSS feed.

## Affiliate Attribution

Every Apple Music link is built through the validated `link()` helper
(`packages/affiliate-helper/js/`). Campaign tokens are hashed at build time
(HMAC-SHA256, truncated) so the taxonomy stays out of public URLs. Set
`CAMPAIGN_HASH_SALT` in your environment to build; the public API is in
`affiliate-helper.js`.

## Origin

This repo unified two earlier projects on **2026-05-06**; both were consolidated
into this single canonical repository:

| Project (now consolidated) | What it contributed |
|---------|-------------------|
| poolpat-plays (archived 2026-05-06) | Data pipeline, GitHub Actions workflow, play count data |
| **Integrations** | A then-experimental Camoufox-Spotify local-first data feed with a monotonic streaming invariant |

## Credits

- **Camoufox anti-detect browser:** v0.4.11 / Firefox 135.0.1-beta.24 (local/experimental only)
- **Spotify API client:** hand-rolled `requests`-based client (`spotify_client.py`) with PKCE OAuth 2.0 — not spotipy
- **SQLite logging:** local/experimental only, under the gitignored `dev/spotify_logs/`
- **Local-first design:** an earlier experiment that captured play data locally before repo sync
