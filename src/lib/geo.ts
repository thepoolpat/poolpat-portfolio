// Combined listening geography: SoundCloud + Apple Music, summed per place.
//
// SoundCloud and Apple Music are the only platforms that expose a per-country
// breakdown (Spotify for Artists does not), so the homepage map and the /stats
// "Top Locations" lists are built from these two, merged here at build time.
// Raw per-platform data lives in data/sc_locations.json and data/am_locations.json
// (both manually compiled — the weekly fetch-data workflow does NOT refresh them).
//
// Merge rules:
//   - Countries join on ISO alpha-2 code; plays are summed; per-platform values
//     kept for tooltips. Display name prefers the SoundCloud spelling.
//   - Cities join on normalized name (lowercased, with a couple of aliases for
//     differing spellings); the country code comes from the SoundCloud entry
//     (every city that ranks high enough to display is a SoundCloud city).
//   - `approx` carries through: Ireland/Dublin's SoundCloud counts are shown
//     abbreviated by SoundCloud ("12.4K"), so their combined totals stay approx.

import scRaw from "@data/sc_locations.json";
import amRaw from "@data/am_locations.json";

export interface GeoCountry {
  code: string;
  name: string;
  plays: number;        // combined
  sc: number;
  am: number;
  approx?: boolean;
}
export interface GeoCity {
  name: string;
  country: string | null; // ISO alpha-2 (from SoundCloud); null for AM-only tail
  plays: number;          // combined
  sc: number;
  am: number;
  approx?: boolean;
}

// Raw per-platform datasets, as loaded from data/*.json. Kept loose (`any`)
// because mergeGeo is the single place that reads their fields.
export interface GeoSource {
  summary?: { plays?: number; total_plays?: number; [k: string]: unknown };
  countries: Array<{ name: string; code: string; plays: number; approx?: boolean }>;
  cities: Array<{ name: string; country?: string | null; plays: number; approx?: boolean }>;
}

export interface MergedGeo {
  countries: GeoCountry[];
  cities: GeoCity[];
  scTotalPlays: number;
  amTotalPlays: number;
  combinedTotalPlays: number;
  countryCount: number;
}

const CITY_ALIAS: Record<string, string> = {
  "new york city": "new york",
  "nürnberg": "nuremberg",
  "nurnberg": "nuremberg",
};
const cityKey = (n: string) => {
  const k = n.trim().toLowerCase();
  return CITY_ALIAS[k] ?? k;
};

// Pure: takes the two raw datasets and returns the merged geography. No I/O,
// no module-level data — so it is unit-testable with inline fixtures. The
// module-level exports below are just this applied to the real JSON.
export function mergeGeo(sc: GeoSource, am: GeoSource): MergedGeo {
  // ── Countries: join on alpha-2 code ───────────────────────────────────────
  const countryByCode = new Map<string, GeoCountry>();
  for (const c of sc.countries) {
    countryByCode.set(c.code, { code: c.code, name: c.name, plays: c.plays, sc: c.plays, am: 0, approx: !!c.approx });
  }
  for (const c of am.countries) {
    const e = countryByCode.get(c.code);
    if (e) { e.plays += c.plays; e.am = c.plays; }
    else countryByCode.set(c.code, { code: c.code, name: c.name, plays: c.plays, sc: 0, am: c.plays });
  }
  const countries = [...countryByCode.values()].sort((a, b) => b.plays - a.plays);

  // ── Cities: join on normalized name (a few spellings differ across platforms) ─
  const cityByKey = new Map<string, GeoCity>();
  for (const c of sc.cities) {
    cityByKey.set(cityKey(c.name), { name: c.name, country: c.country ?? null, plays: c.plays, sc: c.plays, am: 0, approx: !!c.approx });
  }
  for (const c of am.cities) {
    const k = cityKey(c.name);
    const e = cityByKey.get(k);
    if (e) { e.plays += c.plays; e.am = c.plays; }
    else cityByKey.set(k, { name: c.name, country: null, plays: c.plays, sc: 0, am: c.plays });
  }
  const cities = [...cityByKey.values()].sort((a, b) => b.plays - a.plays);

  // ── Totals ────────────────────────────────────────────────────────────────
  const scTotalPlays = sc.summary?.plays ?? 0;          // 28,544
  const amTotalPlays = am.summary?.total_plays ?? 0;    // 4,104
  // NOTE: combinedTotalPlays is the full all-time headline figure (SC plays +
  // AM total_plays). It INTENTIONALLY exceeds the sum of the mapped country
  // rows below: country rows are only the geo-attributable subset, and on the
  // Apple Music side a large share of plays (here ~1,159 of 4,104) carry no
  // place at all (see am.summary.geo_attributed_plays). Do NOT "fix" the gap by
  // swapping to am.summary.geo_attributed_plays — the headline number is meant
  // to be the true total plays, not the smaller geo-attributed subset. The map
  // showing fewer plays than the headline is correct and expected.
  const combinedTotalPlays = scTotalPlays + amTotalPlays;
  const countryCount = countries.length;               // distinct countries with any plays

  return { countries, cities, scTotalPlays, amTotalPlays, combinedTotalPlays, countryCount };
}

const merged = mergeGeo(scRaw as unknown as GeoSource, amRaw as unknown as GeoSource);

// Consumed by src/pages/index.astro and src/pages/stats.astro — keep stable.
export const countries: GeoCountry[] = merged.countries;
export const cities: GeoCity[] = merged.cities;
export const combinedTotalPlays: number = merged.combinedTotalPlays;
export const countryCount: number = merged.countryCount;           // distinct countries with any plays
