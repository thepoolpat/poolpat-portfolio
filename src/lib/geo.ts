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

const sc = scRaw as any;
const am = amRaw as any;

// ── Countries: join on alpha-2 code ─────────────────────────────────────────
const countryByCode = new Map<string, GeoCountry>();
for (const c of sc.countries) {
  countryByCode.set(c.code, { code: c.code, name: c.name, plays: c.plays, sc: c.plays, am: 0, approx: !!c.approx });
}
for (const c of am.countries) {
  const e = countryByCode.get(c.code);
  if (e) { e.plays += c.plays; e.am = c.plays; }
  else countryByCode.set(c.code, { code: c.code, name: c.name, plays: c.plays, sc: 0, am: c.plays });
}
export const countries: GeoCountry[] = [...countryByCode.values()].sort((a, b) => b.plays - a.plays);

// ── Cities: join on normalized name (a few spellings differ across platforms) ─
const CITY_ALIAS: Record<string, string> = {
  "new york city": "new york",
  "nürnberg": "nuremberg",
  "nurnberg": "nuremberg",
};
const cityKey = (n: string) => {
  const k = n.trim().toLowerCase();
  return CITY_ALIAS[k] ?? k;
};
const cityByKey = new Map<string, GeoCity>();
for (const c of sc.cities) {
  cityByKey.set(cityKey(c.name), { name: c.name, country: c.country, plays: c.plays, sc: c.plays, am: 0, approx: !!c.approx });
}
for (const c of am.cities) {
  const k = cityKey(c.name);
  const e = cityByKey.get(k);
  if (e) { e.plays += c.plays; e.am = c.plays; }
  else cityByKey.set(k, { name: c.name, country: null, plays: c.plays, sc: 0, am: c.plays });
}
export const cities: GeoCity[] = [...cityByKey.values()].sort((a, b) => b.plays - a.plays);

// ── Totals ──────────────────────────────────────────────────────────────────
export const scTotalPlays: number = sc.summary?.plays ?? 0;          // 28,544
export const amTotalPlays: number = am.summary?.total_plays ?? 0;    // 4,104
export const combinedTotalPlays: number = scTotalPlays + amTotalPlays;
export const countryCount: number = countries.length;               // distinct countries with any plays
