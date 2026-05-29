import { defineCollection } from "astro:content";
import { z } from "astro:schema";
import { file } from "astro/loaders";

// Releases are authored as a single JSON array in src/data/releases.json and
// loaded via the file() loader. `order` is explicit (not derived from array or
// id order) so the curated hero/discography sequence is deterministic.
const releases = defineCollection({
  loader: file("src/data/releases.json"),
  schema: z.object({
    order: z.number(),
    slug: z.string(),
    title: z.string(),
    type: z.string(),
    typeLabel: z.string(),
    id: z.string(),
    storefront: z.string(),
    releaseDate: z.string(),
    artwork: z.string(),
    tagline: z.string(),
    meta: z.array(z.string()).optional(),
    credits: z.string().optional(),
    charts: z.array(z.string()).optional(),
    isCollab: z.boolean().optional(),
    sections: z
      .array(z.object({ id: z.string(), title: z.string(), body: z.string() }))
      .optional(),
    tracks: z.array(
      z.object({
        id: z.string(),
        title: z.string(),
        duration: z.string(),
        slug: z.string(),
      }),
    ),
  }),
});

export const collections = { releases };
