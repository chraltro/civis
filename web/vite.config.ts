import { defineConfig } from "vite";
import { resolve } from "node:path";

// Civis ships as a static site. The data file lives at /data/civis.json
// and is served from web/public/data/ in dev (symlinked or copied at build).
export default defineConfig({
  base: "./",
  root: ".",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2022",
    sourcemap: false,
    rollupOptions: {
      input: resolve(__dirname, "index.html"),
    },
  },
  server: {
    host: true,
    port: 5173,
  },
});
