import { describe, it, expect } from "vitest";
import { platformTotals, soundcloudEngagement } from "./totals";

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

describe("soundcloudEngagement", () => {
  it("prefers the stored aggregate when present", () => {
    expect(
      soundcloudEngagement({
        soundcloud: {
          engagement: { likes: 100, reposts: 20, comments: 5, downloads: 30 },
          track_details: { a: { likes: 1 } }, // must NOT override the aggregate
        },
      }),
    ).toEqual({ likes: 100, reposts: 20, comments: 5, downloads: 30 });
  });

  it("falls back to summing track_details per missing/0 field", () => {
    expect(
      soundcloudEngagement({
        soundcloud: {
          engagement: { likes: 100 }, // reposts/comments/downloads absent
          track_details: {
            a: { likes: 1, reposts: 2, comments: 3 },
            b: { reposts: 4, downloads: 5, permalink_url: "https://x" },
          },
        },
      }),
    ).toEqual({ likes: 100, reposts: 6, comments: 3, downloads: 5 });
  });

  it("is 0 across the board for empty data (no NaN)", () => {
    expect(soundcloudEngagement({})).toEqual({ likes: 0, reposts: 0, comments: 0, downloads: 0 });
  });
});
