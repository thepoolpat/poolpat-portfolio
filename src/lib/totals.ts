// Per-platform play totals with ONE shared fallback rule, imported by both the
// homepage (index.astro) and the stats page so the headline figure can't diverge
// between them: prefer the stored platform total; if it is missing or 0, sum the
// per-track counts. grandTotal is always the sum of the three tiles, so it can
// never drift from its own breakdown.
const sumTracks = (tracks: unknown): number =>
  Object.values((tracks ?? {}) as Record<string, unknown>).reduce<number>(
    (a, b) => a + (Number(b) || 0),
    0,
  );

export function platformTotals(data: any) {
  const scTotal = data?.soundcloud?.total_plays || sumTracks(data?.soundcloud?.tracks);
  const spTotal = data?.spotify?.total_streams || sumTracks(data?.spotify?.tracks);
  const amTotal = data?.apple_music?.total_plays || sumTracks(data?.apple_music?.tracks);
  return { scTotal, spTotal, amTotal, grandTotal: scTotal + spTotal + amTotal };
}

// SoundCloud engagement totals with the same fallback rule as platformTotals:
// prefer the stored aggregate (written by the pipeline's sum_engagement); if a
// field is missing or 0, sum the per-track details instead.
const ENGAGEMENT_FIELDS = ["likes", "reposts", "comments", "downloads"] as const;

export function soundcloudEngagement(data: any) {
  const stored = (data?.soundcloud?.engagement ?? {}) as Record<string, unknown>;
  const details = (data?.soundcloud?.track_details ?? {}) as Record<string, unknown>;
  const sumField = (field: string): number =>
    Object.values(details).reduce<number>(
      (a, d) => a + (Number((d as Record<string, unknown>)?.[field]) || 0),
      0,
    );
  const out = {} as Record<(typeof ENGAGEMENT_FIELDS)[number], number>;
  for (const field of ENGAGEMENT_FIELDS) {
    out[field] = Number(stored[field]) || sumField(field);
  }
  return out;
}
