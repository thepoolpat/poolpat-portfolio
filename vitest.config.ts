import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Minimal config: the only thing vitest can't resolve on its own is the
// "@data" path alias that src/lib/geo.ts uses for its module-level JSON
// imports. Mirror the alias from astro.config.mjs / tsconfig.json so that
// importing geo.ts (to reach the pure mergeGeo) loads cleanly. The default
// `include` glob still picks up every *.test.* file (affiliate-helper + this).
export default defineConfig({
  resolve: {
    alias: {
      "@data": fileURLToPath(new URL("./data", import.meta.url)),
    },
  },
});
