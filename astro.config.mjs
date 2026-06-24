import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { fileURLToPath } from "url";

const isPublic = process.env.DEPLOY_TARGET === "public";

const site = isPublic
  ? "https://thepoolpat.github.io"
  : "http://localhost:4321";

const base = isPublic
  ? "/poolpat-portfolio/"
  : "/";

export default defineConfig({
  site,
  base,
  output: "static",
  integrations: [sitemap()],
  build: { inlineStylesheets: "always" },
  vite: {
    resolve: {
      alias: {
        "@affiliate": fileURLToPath(
          new URL("./packages/affiliate-helper/js/affiliate-helper.js", import.meta.url)
        ),
        "@data": fileURLToPath(new URL("./data", import.meta.url)),
      },
    },
  },
});
