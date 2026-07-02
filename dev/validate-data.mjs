// Shape validator for the data/*.json files that feed the site.
//
// Run:  node dev/validate-data.mjs
//
// Exits 0 when every checked file matches its expected shape, non-zero on a
// REAL shape violation (so it can gate a workflow). It deliberately tolerates
// the known-valid quirks of this dataset:
//   - summary key names differ across files (sc.summary.plays vs
//     am.summary.total_plays) — we don't pin a specific summary key.
//   - plays.json track keys are intentionally mixed NFC/NFD; JSON parsing
//     collapses byte-identical-after-normalization duplicates, and that's fine.
//     We never treat "duplicate-looking" track names as an error.
//
// Uses zod when it resolves from node_modules; otherwise falls back to plain
// assertions so the script still runs in a bare checkout.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("..", import.meta.url)).replace(/\/$/, "");
const dataDir = `${repoRoot}/data`;

// ── optional zod ────────────────────────────────────────────────────────────
let z = null;
try {
  ({ z } = await import("zod"));
} catch {
  // zod not installed — plain-assertion path below is used instead.
}

// ── tiny assertion helpers (used as the zod fallback) ────────────────────────
const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const isStr = (v) => typeof v === "string";

function fail(file, msg) {
  throw new Error(`${file}: ${msg}`);
}

// Validate a list of {code, plays} location entries (sc_locations / am_locations).
function checkLocationCountries(file, json) {
  if (typeof json !== "object" || json === null) fail(file, "top-level is not an object");
  if (!Array.isArray(json.countries)) fail(file, "`countries` is not an array");
  if (json.countries.length === 0) fail(file, "`countries` is empty");

  // summary, if present, must be an object — but its keys legitimately differ
  // between files (plays vs total_plays), so we do NOT pin a key name.
  if ("summary" in json && (typeof json.summary !== "object" || json.summary === null)) {
    fail(file, "`summary` present but not an object");
  }

  json.countries.forEach((c, i) => {
    if (typeof c !== "object" || c === null) fail(file, `countries[${i}] is not an object`);
    if (!isStr(c.code) || c.code.length !== 2) {
      fail(file, `countries[${i}].code is not a 2-letter string (got ${JSON.stringify(c.code)})`);
    }
    if (!isNum(c.plays)) {
      fail(file, `countries[${i}].plays is not a number (got ${JSON.stringify(c.plays)})`);
    }
  });
  return json.countries.length;
}

// Validate world-geo.json choropleth shapes: viewBox string + countries[] with
// a `code` (2-letter string OR null) and a `d` SVG path string.
function checkWorldGeo(file, json) {
  if (typeof json !== "object" || json === null) fail(file, "top-level is not an object");
  if (!isStr(json.viewBox)) fail(file, "`viewBox` is not a string");
  if (!Array.isArray(json.countries)) fail(file, "`countries` is not an array");
  if (json.countries.length === 0) fail(file, "`countries` is empty");

  json.countries.forEach((c, i) => {
    if (typeof c !== "object" || c === null) fail(file, `countries[${i}] is not an object`);
    const codeOk = c.code === null || (isStr(c.code) && c.code.length === 2);
    if (!codeOk) {
      fail(file, `countries[${i}].code is not a 2-letter string or null (got ${JSON.stringify(c.code)})`);
    }
    if (!isStr(c.d) || c.d.length === 0) {
      fail(file, `countries[${i}].d is not a non-empty path string`);
    }
  });
  return json.countries.length;
}

// Validate plays.json: top-level totals numeric where present; each platform's
// per-track map has numeric values. Mixed NFC/NFD track keys are expected and
// fine — we never compare/normalize keys.
function checkPlays(file, json) {
  if (typeof json !== "object" || json === null) fail(file, "top-level is not an object");

  // Per-platform sections that may carry a numeric grand total. Only check the
  // ones actually present (Apple Music has no total_streams, etc.).
  const platforms = ["soundcloud", "spotify", "apple_music"];
  const totalKeys = ["total_plays", "total_streams", "total_plays_all_platforms"];

  for (const p of platforms) {
    const section = json[p];
    if (section === undefined) continue;
    if (typeof section !== "object" || section === null) fail(file, `\`${p}\` is not an object`);

    // any total_* present on the section must be numeric
    for (const k of totalKeys) {
      if (k in section && !isNum(section[k])) {
        fail(file, `${p}.${k} is not a number (got ${JSON.stringify(section[k])})`);
      }
    }

    // tracks map: every value numeric (keys are mixed NFC/NFD on purpose)
    if ("tracks" in section) {
      const tracks = section.tracks;
      if (typeof tracks !== "object" || tracks === null || Array.isArray(tracks)) {
        fail(file, `${p}.tracks is not an object map`);
      }
      for (const [name, count] of Object.entries(tracks)) {
        if (!isNum(count)) {
          fail(file, `${p}.tracks[${JSON.stringify(name)}] is not a number (got ${JSON.stringify(count)})`);
        }
      }
    }

    // engagement aggregate (SoundCloud): every value numeric when present
    if ("engagement" in section) {
      const eng = section.engagement;
      if (typeof eng !== "object" || eng === null || Array.isArray(eng)) {
        fail(file, `${p}.engagement is not an object`);
      }
      for (const [k, v] of Object.entries(eng)) {
        if (!isNum(v)) fail(file, `${p}.engagement.${k} is not a number (got ${JSON.stringify(v)})`);
      }
    }

    // track_details map (SoundCloud): entries are objects; the four engagement
    // fields must be numeric where present (metadata strings pass through)
    if ("track_details" in section) {
      const details = section.track_details;
      if (typeof details !== "object" || details === null || Array.isArray(details)) {
        fail(file, `${p}.track_details is not an object map`);
      }
      for (const [name, entry] of Object.entries(details)) {
        if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
          fail(file, `${p}.track_details[${JSON.stringify(name)}] is not an object`);
        }
        for (const k of ["likes", "reposts", "comments", "downloads"]) {
          if (k in entry && !isNum(entry[k])) {
            fail(file, `${p}.track_details[${JSON.stringify(name)}].${k} is not a number (got ${JSON.stringify(entry[k])})`);
          }
        }
      }
    }
  }
  return json;
}

// ── zod schemas (preferred path) ─────────────────────────────────────────────
function checkLocationCountriesZod(file, json) {
  const Country = z.object({
    code: z.string().length(2),
    plays: z.number().finite(),
  }).passthrough();
  const Schema = z.object({
    countries: z.array(Country).min(1),
    summary: z.object({}).passthrough().optional(),
  }).passthrough();
  const r = Schema.safeParse(json);
  if (!r.success) fail(file, r.error.issues.map((e) => `${e.path.join(".")}: ${e.message}`).join("; "));
  return json.countries.length;
}

function checkWorldGeoZod(file, json) {
  const Shape = z.object({
    code: z.union([z.string().length(2), z.null()]),
    d: z.string().min(1),
  }).passthrough();
  const Schema = z.object({
    viewBox: z.string(),
    countries: z.array(Shape).min(1),
  }).passthrough();
  const r = Schema.safeParse(json);
  if (!r.success) fail(file, r.error.issues.map((e) => `${e.path.join(".")}: ${e.message}`).join("; "));
  return json.countries.length;
}

function checkPlaysZod(file, json) {
  const num = z.number().finite();
  const TrackDetail = z.object({
    likes: num.optional(),
    reposts: num.optional(),
    comments: num.optional(),
    downloads: num.optional(),
  }).passthrough();
  const Platform = z.object({
    total_plays: num.optional(),
    total_streams: num.optional(),
    total_plays_all_platforms: num.optional(),
    tracks: z.record(z.string(), num).optional(),
    engagement: z.record(z.string(), num).optional(),
    track_details: z.record(z.string(), TrackDetail).optional(),
  }).passthrough();
  const Schema = z.object({
    soundcloud: Platform.optional(),
    spotify: Platform.optional(),
    apple_music: Platform.optional(),
  }).passthrough();
  const r = Schema.safeParse(json);
  if (!r.success) fail(file, r.error.issues.map((e) => `${e.path.join(".")}: ${e.message}`).join("; "));
  return json;
}

// ── runner ───────────────────────────────────────────────────────────────────
const checks = [
  {
    file: "sc_locations.json",
    run: (f, j) => (z ? checkLocationCountriesZod : checkLocationCountries)(f, j),
    summary: (n) => `${n} countries`,
  },
  {
    file: "am_locations.json",
    run: (f, j) => (z ? checkLocationCountriesZod : checkLocationCountries)(f, j),
    summary: (n) => `${n} countries`,
  },
  {
    file: "world-geo.json",
    run: (f, j) => (z ? checkWorldGeoZod : checkWorldGeo)(f, j),
    summary: (n) => `${n} geo shapes`,
  },
  {
    file: "plays.json",
    run: (f, j) => (z ? checkPlaysZod : checkPlays)(f, j),
    summary: () => "totals + per-track maps numeric",
  },
];

let failed = 0;
console.log(`validate-data: ${z ? "using zod" : "using plain assertions"} — ${dataDir}`);

for (const { file, run, summary } of checks) {
  const path = `${dataDir}/${file}`;
  try {
    const json = JSON.parse(readFileSync(path, "utf8"));
    const result = run(file, json);
    console.log(`  OK   ${file.padEnd(20)} ${summary(result)}`);
  } catch (err) {
    failed += 1;
    console.error(`  FAIL ${file.padEnd(20)} ${err.message}`);
  }
}

if (failed > 0) {
  console.error(`\nvalidate-data: ${failed} file(s) failed shape validation`);
  process.exit(1);
}
console.log("\nvalidate-data: all files OK");
