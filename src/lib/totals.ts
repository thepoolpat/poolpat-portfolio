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
