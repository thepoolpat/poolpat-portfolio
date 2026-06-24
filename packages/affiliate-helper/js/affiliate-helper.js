/**
 * Apple Music affiliate link builder for Poolpat (token: 1000l3chz).
 *
 * Build-time only (Node). Uses node:crypto for opaque campaign-token hashing
 * so the campaign taxonomy stays out of public URLs.
 *
 * ES module, no third-party deps.
 */

import { createHmac } from "node:crypto";

export const TOKEN = "1000l3chz";
export const HOST = "music.apple.com";
export const APP = "music";
export const MAX_CT_LENGTH = 40; // Apple's documented cap

export const ALLOWED_SURFACES = Object.freeze(
  new Set(["web", "social", "ad", "email", "lab", "partner"])
);

/** @typedef {"album"|"song"|"playlist"|"artist"|"station"|"music-video"} LinkType */

export class AffiliateError extends Error {
  constructor(message) {
    super(message);
    this.name = "AffiliateError";
  }
}

const STOREFRONT_RE = /^[a-z]{2}$/;
const CT_CHARS_RE = /^[a-z0-9-]+$/;

function validateStorefront(s) {
  if (!s) throw new AffiliateError("Storefront is empty.");
  if (!STOREFRONT_RE.test(s)) {
    throw new AffiliateError(
      `Storefront '${s}' must be 2 lowercase ASCII letters (ISO 3166-1 alpha-2).`
    );
  }
}

function validateCt(ct) {
  if (ct.length > MAX_CT_LENGTH) {
    throw new AffiliateError(`ct value is ${ct.length} chars (max ${MAX_CT_LENGTH}).`);
  }
  const lowered = ct.toLowerCase();
  if (!CT_CHARS_RE.test(lowered)) {
    throw new AffiliateError(`ct '${ct}' has invalid characters. Allowed: a-z, 0-9, hyphen.`);
  }
  const parts = lowered.split("-");
  if (parts.length < 2) {
    throw new AffiliateError("ct must have at least 2 tokens (surface-placement-...).");
  }
  if (!ALLOWED_SURFACES.has(parts[0])) {
    throw new AffiliateError(
      `ct surface '${parts[0]}' is not canonical. Allowed: ${[...ALLOWED_SURFACES].sort()}`
    );
  }
}

function resolveSalt(explicit) {
  if (explicit) return explicit;
  const env = process.env.CAMPAIGN_HASH_SALT;
  if (env) return env;
  if (process.env.DEPLOY_TARGET === "public") {
    throw new AffiliateError(
      "CAMPAIGN_HASH_SALT is required for public builds. Set the env var or pass {salt}."
    );
  }
  return "dev-only-salt";
}

/**
 * Hash a plaintext campaign string into an opaque token.
 * Preserves the surface prefix so the output still passes validateCt;
 * replaces everything after it with HMAC-SHA256 truncated to 10 hex chars.
 *
 * @param {string} plaintext e.g. "web-portfolio-discipline-hero"
 * @param {{salt?: string}} [opts]
 * @returns {string} e.g. "web-a1b2c3d4e5"
 */
export function hashCampaign(plaintext, { salt } = {}) {
  if (typeof plaintext !== "string" || !plaintext) {
    throw new AffiliateError("hashCampaign: plaintext is required.");
  }
  const lowered = plaintext.toLowerCase();
  if (!CT_CHARS_RE.test(lowered)) {
    throw new AffiliateError(
      `hashCampaign: plaintext '${plaintext}' has invalid characters. Allowed: a-z, 0-9, hyphen.`
    );
  }
  const idx = lowered.indexOf("-");
  if (idx < 0) {
    throw new AffiliateError("hashCampaign: plaintext needs a surface prefix (e.g. 'web-...').");
  }
  const surface = lowered.slice(0, idx);
  const rest = lowered.slice(idx + 1);
  if (!ALLOWED_SURFACES.has(surface)) {
    throw new AffiliateError(
      `hashCampaign: surface '${surface}' is not canonical. Allowed: ${[...ALLOWED_SURFACES].sort()}`
    );
  }
  if (!rest) {
    throw new AffiliateError("hashCampaign: plaintext needs content after the surface prefix.");
  }
  const resolvedSalt = resolveSalt(salt);
  const hash = createHmac("sha256", resolvedSalt).update(rest).digest("hex").slice(0, 10);
  return `${surface}-${hash}`;
}

/**
 * Build a validated Apple Music affiliate URL.
 * @param {object} args
 * @param {string} args.storefront ISO 3166-1 alpha-2, lowercase
 * @param {LinkType} args.type
 * @param {string} args.slug human-readable URL slug (or "_" if unknown)
 * @param {string} args.id Apple catalog ID
 * @param {string} args.campaign ct value (will be lowercased)
 * @returns {string} URL string
 */
export function link({ storefront, type, slug, id, campaign }) {
  validateStorefront(storefront);
  if (!id) throw new AffiliateError("Catalog ID is empty.");
  validateCt(campaign);
  const safeSlug = slug || "_";
  const ct = campaign.toLowerCase();
  // Manually compose query — keep at, app, ct in a fixed deterministic order.
  return `https://${HOST}/${storefront}/${type}/${safeSlug}/${id}?at=${TOKEN}&app=${APP}&ct=${ct}`;
}

/**
 * Rewrite an existing music.apple.com URL to embed the affiliate token + ct.
 * Preserves other query params; overwrites at, app, ct.
 */
export function rewrite(urlString, { campaign }) {
  validateCt(campaign);
  const u = new URL(urlString);
  if (u.hostname !== HOST) {
    throw new AffiliateError(`URL host '${u.host}' is not music.apple.com`);
  }
  ["at", "app", "ct"].forEach((k) => u.searchParams.delete(k));
  u.searchParams.append("at", TOKEN);
  u.searchParams.append("app", APP);
  u.searchParams.append("ct", campaign.toLowerCase());
  return u.toString();
}

/**
 * Parse a ct value into its taxonomy fields.
 * @returns {{surface:string,placement:string,descriptor:string|null,date:string|null}|null}
 */
export function parseCt(ct) {
  const parts = ct.toLowerCase().split("-");
  if (parts.length < 2) return null;
  const [surface, placement, ...rest] = parts;
  let date = null;
  let descParts = rest;
  if (rest.length > 0 && /^\d+$/.test(rest[rest.length - 1])) {
    date = rest[rest.length - 1];
    descParts = rest.slice(0, -1);
  }
  return {
    surface,
    placement,
    descriptor: descParts.length ? descParts.join("-") : null,
    date,
  };
}
