import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { fileURLToPath } from "url";

const isPublic = process.env.DEPLOY_TARGET === "public";

const site = isPublic
  ? "https://thepoolpat.github.io"
  : "https://REDACTED/thepoolpat/poolpat-portfolio";

const base = isPublic
  ? "/poolpat-portfolio/"
  : "/thepoolpat/poolpat-portfolio/";

export default defineConfig({
  site,
  base,
  output: "static",
  integrations: [sitemap()],
  build: { inlineStylesheets: "auto" },
  vite: {
    resolve: {
      alias: {
        "@affiliate": fileURLToPath(
          new URL("./packages/affiliate-helper/js/affiliate-helper.js", import.meta.url)
        ),
      },
    },
  },
});
