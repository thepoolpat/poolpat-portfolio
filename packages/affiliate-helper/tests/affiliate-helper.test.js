import { describe, it, expect } from "vitest";
import {
  link,
  rewrite,
  parseCt,
  AffiliateError,
  TOKEN,
  HOST,
  APP,
  MAX_CT_LENGTH,
} from "../js/affiliate-helper.js";

describe("link()", () => {
  const valid = {
    storefront: "us",
    type: "album",
    slug: "midnight-tapes",
    id: "1234567890",
    campaign: "web-hero-launch",
  };

  it("composes a canonical URL with at, app, ct in fixed order", () => {
    const url = link(valid);
    expect(url).toBe(
      `https://${HOST}/us/album/midnight-tapes/1234567890?at=${TOKEN}&app=${APP}&ct=web-hero-launch`,
    );
  });

  it("lowercases the campaign before inserting", () => {
    const url = link({ ...valid, campaign: "WEB-HERO-LAUNCH" });
    expect(url).toContain("ct=web-hero-launch");
  });

  it("uses underscore slug placeholder when slug is empty string", () => {
    const url = link({ ...valid, slug: "" });
    expect(url).toContain("/album/_/1234567890");
  });

  it("rejects non-2-letter storefronts", () => {
    expect(() => link({ ...valid, storefront: "USA" })).toThrow(AffiliateError);
    expect(() => link({ ...valid, storefront: "US" })).toThrow(AffiliateError); // uppercase
    expect(() => link({ ...valid, storefront: "u1" })).toThrow(AffiliateError);
    expect(() => link({ ...valid, storefront: "" })).toThrow(AffiliateError);
  });

  it("rejects empty catalog id", () => {
    expect(() => link({ ...valid, id: "" })).toThrow(/Catalog ID/);
  });

  it("rejects ct longer than MAX_CT_LENGTH", () => {
    const long = "web-" + "x".repeat(MAX_CT_LENGTH);
    expect(() => link({ ...valid, campaign: long })).toThrow(/max/);
  });

  it("rejects ct with disallowed characters", () => {
    expect(() => link({ ...valid, campaign: "web hero launch" })).toThrow(
      /invalid characters/,
    );
    expect(() => link({ ...valid, campaign: "web_hero_launch" })).toThrow(
      /invalid characters/,
    );
    expect(() => link({ ...valid, campaign: "web/hero/launch" })).toThrow(
      AffiliateError,
    );
  });

  it("rejects ct with non-canonical surface", () => {
    expect(() => link({ ...valid, campaign: "twitter-hero-launch" })).toThrow(
      /not canonical/,
    );
  });

  it("requires ct to have at least 2 tokens", () => {
    expect(() => link({ ...valid, campaign: "web" })).toThrow(/at least 2 tokens/);
  });

  it("accepts every canonical surface", () => {
    for (const surface of ["web", "social", "ad", "email", "lab", "partner"]) {
      const url = link({ ...valid, campaign: `${surface}-hero` });
      expect(url).toContain(`ct=${surface}-hero`);
    }
  });
});

describe("rewrite()", () => {
  it("strips existing at/app/ct and re-injects ours", () => {
    const original =
      "https://music.apple.com/us/album/foo/123?at=oldtoken&app=other&ct=stale&l=en";
    const out = rewrite(original, { campaign: "web-rewrite" });
    expect(out).toContain(`at=${TOKEN}`);
    expect(out).toContain(`app=${APP}`);
    expect(out).toContain("ct=web-rewrite");
    expect(out).not.toContain("oldtoken");
    expect(out).not.toContain("stale");
    // Other params preserved
    expect(out).toContain("l=en");
  });

  it("rejects non-Apple-Music URLs", () => {
    expect(() =>
      rewrite("https://example.com/foo", { campaign: "web-x" }),
    ).toThrow(AffiliateError);
  });

  it("rejects malformed URLs", () => {
    expect(() => rewrite("not a url", { campaign: "web-x" })).toThrow();
  });

  it("validates campaign before parsing the URL", () => {
    expect(() =>
      rewrite("https://music.apple.com/us/album/foo/123", {
        campaign: "BAD CAMPAIGN",
      }),
    ).toThrow(/invalid characters/);
  });

  it("lowercases campaign on output", () => {
    const out = rewrite("https://music.apple.com/us/album/foo/123", {
      campaign: "WEB-Hero",
    });
    expect(out).toContain("ct=web-hero");
  });
});

describe("parseCt()", () => {
  it("returns null for single-token ct", () => {
    expect(parseCt("web")).toBe(null);
  });

  it("parses surface and placement only", () => {
    expect(parseCt("web-hero")).toEqual({
      surface: "web",
      placement: "hero",
      descriptor: null,
      date: null,
    });
  });

  it("parses descriptor when present", () => {
    expect(parseCt("web-hero-launch")).toEqual({
      surface: "web",
      placement: "hero",
      descriptor: "launch",
      date: null,
    });
  });

  it("recognizes trailing all-digit token as date", () => {
    expect(parseCt("web-hero-launch-20260101")).toEqual({
      surface: "web",
      placement: "hero",
      descriptor: "launch",
      date: "20260101",
    });
  });

  it("treats trailing date with no descriptor", () => {
    expect(parseCt("web-hero-20260101")).toEqual({
      surface: "web",
      placement: "hero",
      descriptor: null,
      date: "20260101",
    });
  });

  it("joins multi-segment descriptors with hyphens", () => {
    expect(parseCt("web-hero-multi-word-desc")).toEqual({
      surface: "web",
      placement: "hero",
      descriptor: "multi-word-desc",
      date: null,
    });
  });

  it("lowercases input", () => {
    expect(parseCt("WEB-HERO")).toEqual({
      surface: "web",
      placement: "hero",
      descriptor: null,
      date: null,
    });
  });

  it("does not treat alphanumeric trailing token as date", () => {
    // Mixed alpha+digit should remain part of descriptor
    expect(parseCt("web-hero-abc123")).toEqual({
      surface: "web",
      placement: "hero",
      descriptor: "abc123",
      date: null,
    });
  });
});

describe("byte-exact URL conformance", () => {
  // These guard against accidental encoding changes (e.g. switching to URLSearchParams)
  // that would diverge from the Swift / Python sibling builders.
  it("does not URL-encode hyphens in ct", () => {
    const url = link({
      storefront: "ie",
      type: "song",
      slug: "track-with-dashes",
      id: "9",
      campaign: "social-share-link",
    });
    expect(url).not.toContain("%2D");
    expect(url).toContain("ct=social-share-link");
  });

  it("query string order is at, app, ct", () => {
    const url = link({
      storefront: "us",
      type: "playlist",
      slug: "p",
      id: "1",
      campaign: "lab-test",
    });
    const query = url.split("?")[1];
    const keys = query.split("&").map((kv) => kv.split("=")[0]);
    expect(keys).toEqual(["at", "app", "ct"]);
  });
});
