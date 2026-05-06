# CLAUDE.md

Guidance for Claude Code when working in this repo. For human developer
setup notes (Spotify/Apple Music auth, Discord webhook, local pipeline runs)
see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## What this is

Astro 6 static site (artist portfolio) + Python data pipeline that fetches play
counts from SoundCloud, Spotify, and Apple Music. Data lives in `data/` and is
auto-committed by the weekly `fetch-data.yml` workflow.

## Layout

- `src/` — Astro pages, layouts, components, styles
- `pipeline/` — Python fetchers and Spotify API client
  - `fetch_plays.py` — multi-platform scraper, enforces monotonic invariant
  - `fetch_playlists.py` — client_credentials flow for public catalog data
  - `spotify_client.py` — typed API client with retry + auto-refresh
  - `spotify_auth.py` — PKCE OAuth flow + refresh-token rotation handling
  - `spotify_errors.py` — typed exception hierarchy
  - `tests/` — pytest suite (44 tests across 4 modules)
- `packages/affiliate-helper/js/` — Apple Music affiliate link builder (untested)
- `.github/workflows/` — `deploy.yml` (Pages), `fetch-data.yml` (weekly cron),
  `codeql.yml`, `tests.yml` (pytest on push/PR).

## Commands

```bash
npm run dev                                # Astro dev server
npm run build                              # Astro build (DEPLOY_TARGET=public for Pages)
npm run check                              # astro check (TypeScript)

cd pipeline && python -m pytest tests/ -v  # Run Python tests
pip install -r pipeline/requirements.txt   # Pipeline runtime deps
pip install pytest                         # Test dep (in [project.optional-dependencies].dev)
```

## Critical invariant

`fetch_plays.monotonic_merge_tracks` must never let a play count decrease.
If a fetch returns a lower number (API hiccup, missing data), the *existing*
value wins. Any change to the merge logic needs tests covering: missing keys,
zero values, partial responses, and new tracks in the fetched set.

## Test status

44 passing. Coverage now includes `fetch_plays.monotonic_merge_tracks` and
`monotonic_total` — the load-bearing invariant.

## Known test gaps

These modules still have no tests — prioritize when adding coverage:

- `fetch_plays.py` — only the monotonic helpers are covered; the SoundCloud /
  Spotify / Apple Music fetch orchestration paths are not.
- `fetch_playlists.py` (client_credentials flow)
- `spotify_client.SpotifyClient._refresh()` (401 → refresh → retry path)
- `spotify_discord_analytics.py`, `spotify_enhanced_analytics.py`
- `packages/affiliate-helper/js/affiliate-helper.js` (no JS test runner set up)

## Conventions

- Python: stdlib + `requests` + `beautifulsoup4` + `defusedxml`. No frameworks.
- Pipeline modules import each other by flat name (`from spotify_errors import ...`),
  so tests prepend `pipeline/` to `sys.path` rather than installing as a package.
- Secrets: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`,
  optional `APPLE_MUSIC_TOKEN`, `RAPIDAPI_KEY`. Never commit; never log.
- Refresh-token rotation: when Spotify returns a new `refresh_token`, the auth
  module masks it via `::add-mask::`, writes to `$GITHUB_ENV`, and `gh secret set`s
  it back. Anything mocking this path must mock all three side effects.
- Workflow concurrency: `fetch-data.yml` uses `concurrency: spotify-fetch` to
  serialize runs and avoid the refresh-token race that hit when plays/playlists
  ran in separate workflows.
