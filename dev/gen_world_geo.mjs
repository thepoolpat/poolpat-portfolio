// One-time generator for data/world-geo.json — the static choropleth geometry
// used by the homepage listener map. NOT part of the build or runtime; the
// site only consumes the pre-generated JSON (no d3 dependency ships).
//
// Provenance: Natural Earth 1:110m (public domain) via the `world-atlas`
// package, projected with d3-geo (Equal Earth) to a fixed 1000x500 viewBox.
// Each feature is tagged with its ISO 3166-1 alpha-2 code so the page can join
// on `code` (never on name). Antarctica is dropped. Coordinates are rounded to
// 1 decimal to keep the inlined SVG small (gzips well on Pages).
//
// Regenerate (deps live only in the temp dir, never in the project):
//   mkdir -p /tmp/poolpat-geo && cd /tmp/poolpat-geo && npm init -y
//   npm i d3-geo@3 topojson-client@3 world-atlas@2 i18n-iso-countries@7
//   cp /path/to/repo/dev/gen_world_geo.mjs ./gen.mjs   # run from here so bare
//                                                       # ESM imports resolve
//   POOLPAT_REPO=/path/to/repo node ./gen.mjs > /path/to/repo/data/world-geo.json
// (the script prints the JSON to stdout and a verification report to stderr)

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { feature } from "topojson-client";
import { geoEqualEarth, geoPath } from "d3-geo";
import countries from "i18n-iso-countries";

const require = createRequire(import.meta.url);
const topo = require("world-atlas/countries-110m.json");

// Path to the SoundCloud locations dataset (for the verification join). When
// run from a temp dir (so bare ESM imports resolve against temp node_modules),
// POOLPAT_REPO points back at the repo; otherwise fall back to the repo layout.
const repoRoot = process.env.POOLPAT_REPO || fileURLToPath(new URL("..", import.meta.url));
const scLocations = JSON.parse(readFileSync(`${repoRoot}/data/sc_locations.json`, "utf8"));

// ── numeric ISO id -> alpha-2, with fallbacks for Natural Earth quirks ──────
const numericToA2 = countries.getNumericCodes(); // { "372": "IE", ... }
const nameOverrides = {
  "Russia": "RU", "Russian Federation": "RU",
  "United States of America": "US", "United States": "US",
  "United Kingdom": "GB", "Czechia": "CZ", "Czech Republic": "CZ",
  "South Korea": "KR", "Republic of Korea": "KR", "Korea": "KR",
  "North Korea": "KP", "Türkiye": "TR", "Turkey": "TR",
  "Norway": "NO", "France": "FR", "Bosnia and Herz.": "BA",
  "Dominican Rep.": "DO", "Dem. Rep. Congo": "CD", "Congo": "CG",
  "Central African Rep.": "CF", "S. Sudan": "SS", "Eq. Guinea": "GQ",
  "eSwatini": "SZ", "Solomon Is.": "SB", "Vietnam": "VN", "Viet Nam": "VN",
  "Lao PDR": "LA", "Moldova": "MD", "Macedonia": "MK", "Kosovo": "XK",
};
function resolveCode(geoId, name) {
  const a2 = numericToA2[String(geoId).padStart(3, "0")];
  if (a2) return a2;
  if (nameOverrides[name]) return nameOverrides[name];
  const byName = countries.getAlpha2Code(name, "en");
  return byName || null;
}

// ── project to a fixed viewBox, drop Antarctica ─────────────────────────────
const W = 1000, H = 500;
const fc = feature(topo, topo.objects.countries);
fc.features = fc.features.filter(
  (f) => String(f.id) !== "010" && f.properties.name !== "Antarctica"
);

const projection = geoEqualEarth().fitExtent([[8, 8], [W - 8, H - 8]], fc);
const pathGen = geoPath(projection);
const round = (d) => d.replace(/-?\d+\.\d+/g, (m) => (+m).toFixed(1));

const out = [];
for (const f of fc.features) {
  const d = pathGen(f);
  if (!d) continue;
  out.push({
    code: resolveCode(f.id, f.properties.name),
    name: f.properties.name,
    d: round(d),
  });
}

// ── verification: every dataset country MUST resolve to a geometry ──────────
const geoCodes = new Set(out.map((c) => c.code).filter(Boolean));
const missing = scLocations.countries.filter((c) => !geoCodes.has(c.code));
const uncoded = out.filter((c) => !c.code).map((c) => c.name);

process.stderr.write(`features rendered: ${out.length}\n`);
process.stderr.write(`features with an ISO code: ${out.filter((c) => c.code).length}\n`);
process.stderr.write(`uncoded (rendered grey, no join): ${uncoded.length}${uncoded.length ? " — " + uncoded.join(", ") : ""}\n`);
process.stderr.write(`dataset countries: ${scLocations.countries.length}\n`);
if (missing.length) {
  process.stderr.write(`!! MISSING GEOMETRY for ${missing.length} dataset countries: ${missing.map((m) => `${m.name}(${m.code})`).join(", ")}\n`);
  process.exit(1);
}
process.stderr.write(`OK — all ${scLocations.countries.length} dataset countries matched a shape.\n`);

process.stdout.write(JSON.stringify({ viewBox: `0 0 ${W} ${H}`, countries: out }));
