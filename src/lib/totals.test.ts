import { describe, it, expect } from "vitest";
import { platformTotals } from "./totals";

describe("platformTotals", () => {
  it("prefers the stored platform total when present", () => {
    expect(
      platformTotals({
        soundcloud: { total_plays: 100, tracks: { a: 1 } },
        spotify: { total_streams: 50, tracks: { a: 1 } },
        apple_music: { total_plays: 10, tracks: { a: 1 } },
      }),
    ).toEqual({ scTotal: 100, spTotal: 50, amTotal: 10, grandTotal: 160 });
  });

  // The regression guard for the bug this helper fixes: the homepage used `|| 0`
  // while stats used `|| sum(tracks)`, so a missing/0 stored total made them disagree.
  it("falls back to summing tracks when a stored total is missing or 0", () => {
    const t = platformTotals({
      soundcloud: { tracks: { a: 3, b: 4 } }, // no total_plays -> 7
      spotify: { total_streams: 0, tracks: { a: 5 } }, // 0 -> 5
      apple_music: { total_plays: 9, tracks: { a: 1 } },
    });
    expect(t).toEqual({ scTotal: 7, spTotal: 5, amTotal: 9, grandTotal: 21 });
  });

  it("is 0 across the board for empty data (no NaN)", () => {
    expect(platformTotals({})).toEqual({ scTotal: 0, spTotal: 0, amTotal: 0, grandTotal: 0 });
  });
});
