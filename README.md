# poolpat-portfolio

Unified artist portfolio for **Poolpat** — live play stats, full discography, and liner notes across SoundCloud, Spotify, and Apple Music.

**Live site:** [thepoolpat.github.io/poolpat-portfolio](https://thepoolpat.github.io/poolpat-portfolio/)

## Pages

| Route | Description |
|-------|-------------|
| `/` | Home — hero carousel, live stats summary, platform links |
| `/stats/` | Play count trends (Chart.js), per-platform breakdowns, top tracks |
| `/discography/` | Release card grid with artwork, chart badges |
| `/releases/[slug]/` | Per-release liner notes, track listings, Apple Music CTAs |

## Stack

- **Framework:** [Astro](https://astro.build/) (static output, zero JS by default)
- **Data pipeline:** Python (`pipeline/fetch_plays.py`) — scrapes SoundCloud, Spotify, Apple Music daily via GitHub Actions
- **Affiliate links:** `packages/affiliate-helper/js/` — validated Apple Music URLs with campaign tracking
- **Design system:** Dark/light theme (system fonts, Apple Music red accent)
- **Charts:** Chart.js 4 (loaded async via ES module import, non-blocking)

## Project Structure

```
├── .github/workflows/
│   ├── deploy.yml              # Build Astro → deploy to GitHub Pages
│   └── fetch-plays.yml         # Daily Python pipeline (cron 07:15 UTC)
├── packages/affiliate-helper/  # Apple Music affiliate link builder (JS)
├── pipeline/
│   ├── fetch_plays.py          # Multi-platform play count scraper
│   └── requirements.txt
├── data/                       # Auto-committed by pipeline
│   ├── plays.json              # Latest play count snapshot
│   ├── history.csv             # Time-series (appended daily)
│   └── rss_tracks.json         # SoundCloud catalog
├── public/artwork/             # Release cover images (1200px, web-optimized)
└── src/
    ├── data/releases.json      # Hand-maintained release catalog (7 releases)
    ├── layouts/Base.astro      # HTML shell, SEO, a11y
    ├── components/             # Astro components
    ├── pages/                  # Route pages
    └── styles/global.css       # Unified design tokens
```

## Setup

```bash
# Install dependencies
npm install

# Development server
npm run dev

# Production build (public GitHub Pages)
DEPLOY_TARGET=public npm run build

# Production build (internal)
npm run build

# Preview production build
npm run preview

# TypeScript check
npm run check
```

## Data Pipeline

The Python fetcher runs daily at 07:15 UTC via GitHub Actions:

1. Scrapes SoundCloud (RSS + v2 API), Spotify (public API), Apple Music (API + scraping)
2. Enforces a **monotonic invariant** — play counts never decrease between fetches
3. Commits updated `data/` files to `main`
4. The push triggers `deploy.yml`, which rebuilds and redeploys the site

### Required Secrets

| Secret | Purpose |
|--------|---------|
| `SPOTIFY_CLIENT_ID` | Spotify API access |
| `SPOTIFY_CLIENT_SECRET` | Spotify API access |
| `APPLE_MUSIC_TOKEN` | Apple Music API access (optional) |

## Affiliate Attribution

Every Apple Music link is built through the validated `link()` helper (`packages/affiliate-helper/js/`):
- Token: `1000l3chz`
- Campaign format: `web-portfolio-{slug}-{placement}`
- Max 64 characters, validated at build time

## Origin

This repo unifies two earlier projects:

| Project | What it contributed |
|---------|-------------------|
| [poolpat-plays](https://github.com/thepoolpat/poolpat-plays) | Data pipeline, GitHub Actions workflow, play count data |
