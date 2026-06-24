import { describe, it, expect } from "vitest";
import { mergeGeo, type GeoSource } from "./geo";

// Inline fixtures modeled on the real data/sc_locations.json and
// data/am_locations.json shapes — but tiny, so the merge behavior is checked
// against known numbers rather than the live (changing) datasets. We call the
// pure mergeGeo directly; nothing here reads the @data JSON.

// SoundCloud-shaped source: summary.plays, and `approx` on the Ireland/Dublin
// rows (SoundCloud reports those abbreviated, e.g. "12.4K").
const sc: GeoSource = {
  summary: { plays: 1000, likes: 10 },
  countries: [
    { name: "Ireland", code: "IE", plays: 600, approx: true },
    { name: "United Kingdom", code: "GB", plays: 200 },
    { name: "France", code: "FR", plays: 100 },
  ],
  cities: [
    { name: "Dublin", country: "IE", plays: 500, approx: true },
    { name: "Slough", country: "GB", plays: 150 },
  ],
};

// Apple Music-shaped source: summary.total_plays (different key!), AM city has
// no `country` field at all, and a country (Spain) that SC doesn't list.
const am: GeoSource = {
  summary: { total_plays: 250, geo_attributed_plays: 200 },
  countries: [
    { name: "Ireland", code: "IE", plays: 80 },
    { name: "United Kingdom", code: "GB", plays: 40 },
    { name: "Spain", code: "ES", plays: 30 },
  ],
  cities: [
    { name: "Dublin", plays: 70 },
    { name: "Barcelona", plays: 25 }, // AM-only city → country:null tail
  ],
};

describe("mergeGeo — countries", () => {
  it("joins SC + AM on alpha-2 code and sums plays", () => {
    const { countries } = mergeGeo(sc, am);
    const ie = countries.find((c) => c.code === "IE")!;
    expect(ie.plays).toBe(680); // 600 SC + 80 AM
    expect(ie.sc).toBe(600);
    expect(ie.am).toBe(80);
    const gb = countries.find((c) => c.code === "GB")!;
    expect(gb.plays).toBe(240); // 200 + 40
    expect(gb.sc).toBe(200);
    expect(gb.am).toBe(40);
  });

  it("keeps the SC display name when the two platforms spell it differently", () => {
    // SC says "United Kingdom", AM says "Britain" for the same GB code; the SC
    // spelling must survive the join (the AM update only touches plays/am).
    const scUk: GeoSource = {
      summary: { plays: 0 },
      countries: [{ name: "United Kingdom", code: "GB", plays: 200 }],
      cities: [],
    };
    const amUk: GeoSource = {
      summary: { total_plays: 0 },
      countries: [{ name: "Britain", code: "GB", plays: 40 }],
      cities: [],
    };
    const { countries } = mergeGeo(scUk, amUk);
    const gb = countries.find((c) => c.code === "GB")!;
    expect(gb.name).toBe("United Kingdom"); // SC spelling, not "Britain"
    expect(gb.plays).toBe(240);
  });

  it("carries an AM-only country with sc:0", () => {
    const { countries } = mergeGeo(sc, am);
    const es = countries.find((c) => c.code === "ES")!;
    expect(es).toBeDefined();
    expect(es.sc).toBe(0);
    expect(es.am).toBe(30);
    expect(es.plays).toBe(30);
  });

  it("sorts countries by combined plays descending", () => {
    const { countries } = mergeGeo(sc, am);
    const plays = countries.map((c) => c.plays);
    expect(plays).toEqual([...plays].sort((a, b) => b - a));
    expect(countries[0].code).toBe("IE"); // 680 is the largest
  });

  it("carries the approx flag from the SC country entry", () => {
    const { countries } = mergeGeo(sc, am);
    const ie = countries.find((c) => c.code === "IE")!;
    expect(ie.approx).toBe(true); // from SC Ireland row
    const gb = countries.find((c) => c.code === "GB")!;
    expect(gb.approx).toBe(false); // SC GB had no approx
  });
});

describe("mergeGeo — cities", () => {
  it("joins cities on normalized name and sums plays", () => {
    const { cities } = mergeGeo(sc, am);
    const dublin = cities.find((c) => c.name === "Dublin")!;
    expect(dublin.plays).toBe(570); // 500 SC + 70 AM
    expect(dublin.sc).toBe(500);
    expect(dublin.am).toBe(70);
    expect(dublin.country).toBe("IE"); // country comes from the SC entry
  });

  it("carries the approx flag from the SC city entry", () => {
    const { cities } = mergeGeo(sc, am);
    const dublin = cities.find((c) => c.name === "Dublin")!;
    expect(dublin.approx).toBe(true);
    const slough = cities.find((c) => c.name === "Slough")!;
    expect(slough.approx).toBe(false);
  });

  it("lands an AM-only city as country:null in the tail", () => {
    const { cities } = mergeGeo(sc, am);
    const barcelona = cities.find((c) => c.name === "Barcelona")!;
    expect(barcelona).toBeDefined();
    expect(barcelona.country).toBeNull(); // AM cities have no country field
    expect(barcelona.sc).toBe(0);
    expect(barcelona.am).toBe(25);
    expect(barcelona.plays).toBe(25);
  });

  it("normalizes city-name spelling differences via alias", () => {
    // "New York City" (SC) and "New York" (AM) alias to the same key.
    const scNy: GeoSource = {
      summary: { plays: 0 },
      countries: [],
      cities: [{ name: "New York City", country: "US", plays: 40 }],
    };
    const amNy: GeoSource = {
      summary: { total_plays: 0 },
      countries: [],
      cities: [{ name: "New York", plays: 10 }],
    };
    const { cities } = mergeGeo(scNy, amNy);
    expect(cities).toHaveLength(1);
    expect(cities[0].plays).toBe(50); // 40 + 10, merged not duplicated
    expect(cities[0].country).toBe("US"); // SC entry's country survives
  });
});

describe("mergeGeo — totals (two distinct summary key shapes)", () => {
  it("reads sc.summary.plays and am.summary.total_plays", () => {
    const { scTotalPlays, amTotalPlays, combinedTotalPlays } = mergeGeo(sc, am);
    expect(scTotalPlays).toBe(1000); // sc.summary.plays
    expect(amTotalPlays).toBe(250); // am.summary.total_plays (NOT .plays)
    expect(combinedTotalPlays).toBe(1250);
  });

  it("the headline total intentionally exceeds the summed country rows", () => {
    // Documents the gap that G2's comment warns against 'fixing'.
    const { combinedTotalPlays, amTotalPlays, countries } = mergeGeo(sc, am);
    const summedRows = countries.reduce((acc, c) => acc + c.plays, 0);
    expect(combinedTotalPlays).toBeGreaterThan(summedRows);
    // amTotalPlays must come from total_plays (250), NOT a silent fallback to
    // am.summary.geo_attributed_plays (200) — the regression G2's comment warns
    // a future reader against introducing.
    expect(amTotalPlays).toBe(250);
    expect(amTotalPlays).not.toBe(200);
  });

  it("defaults missing summary fields to 0", () => {
    const empty: GeoSource = { countries: [], cities: [] };
    const { scTotalPlays, amTotalPlays, combinedTotalPlays, countryCount } =
      mergeGeo(empty, empty);
    expect(scTotalPlays).toBe(0);
    expect(amTotalPlays).toBe(0);
    expect(combinedTotalPlays).toBe(0);
    expect(countryCount).toBe(0);
  });

  it("countryCount is the number of distinct merged countries", () => {
    const { countryCount } = mergeGeo(sc, am);
    // SC: IE, GB, FR. AM: IE, GB, ES. Distinct union = IE, GB, FR, ES = 4.
    expect(countryCount).toBe(4);
  });
});
