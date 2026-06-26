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
  - `tests/` — pytest suite (156 Python tests across 6 modules)
- `packages/affiliate-helper/js/` — Apple Music affiliate link builder
  - `tests/` — Vitest suite (55 JS: 39 affiliate-helper + 13 geo + 3 totals)
- `.github/workflows/` — `deploy.yml` (Pages), `fetch-data.yml` (weekly cron),
  `codeql.yml`, `tests.yml` (pytest + vitest on push/PR).

## Commands

```bash
npm run dev                                # Astro dev server
npm run build                              # Astro build (DEPLOY_TARGET=public for Pages)
npm run check                              # astro check (TypeScript)
npm test                                   # Run JS tests (vitest)

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

156 Python + 55 JS passing. Coverage now includes:
- `fetch_plays` — monotonic helpers + SoundCloud / Spotify / Apple Music
  fetch orchestration, history.csv writer, GitHub alert path, RSS parsing,
  SoundCloud client_id resolution (env → cache → scrape, re-scrape on miss) and
  the served-data staleness warning
- `fetch_playlists` — client_credentials auth, retry, dedup, search nullability
- `spotify_client` — `_refresh()` rotation path, 401 recovery, retry exhaustion
- `spotify_auth` — PKCE, `exchange_code`, refresh-token rotation including
  `::add-mask::`, `$GITHUB_ENV` write, and `gh secret set` failure modes
- `affiliate-helper.js` — `link()`, `rewrite()`, `parseCt()`, byte-exact URL
  conformance with the Swift / Python sibling builders
- `src/lib/geo.ts` (`geo.test.ts`) — listener-map geo merge (SoundCloud +
  Apple Music location aggregation, flag/country list building)
- `src/lib/totals.ts` (`totals.test.ts`) — shared per-platform play totals with
  one fallback rule (homepage + stats can't diverge)

## Known test gaps

- `_run_local_auth` (interactive HTTP server callback) — local-dev only.

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
