import { defineConfig } from "vite";
import { resolve, dirname } from "node:path";
import { existsSync, mkdirSync, copyFileSync, statSync } from "node:fs";
import type { Plugin } from "vite";

// Copy data/processed/civis.{json,csv} from the repo root into the served
// asset tree at /data/civis.{json,csv}. The pipeline writes those files;
// when they're absent (e.g. fresh checkout before the first refresh), the
// plugin no-ops so the build still succeeds and the dashboard shows its
// empty state at runtime.
function dataAssets(): Plugin {
  const sources = [
    { src: "../data/processed/civis.json", dst: "data/civis.json" },
    { src: "../data/processed/civis.csv",  dst: "data/civis.csv"  },
  ];
  let outDir = "dist";
  let publicDir = "public";

  function copyIfPresent(target: string): void {
    for (const { src, dst } of sources) {
      const abs = resolve(__dirname, src);
      if (!existsSync(abs)) continue;
      const out = resolve(__dirname, target, dst);
      mkdirSync(dirname(out), { recursive: true });
      copyFileSync(abs, out);
    }
  }

  return {
    name: "civis-data-assets",
    configResolved(config) {
      outDir = config.build.outDir;
      publicDir = config.publicDir;
    },
    buildStart() {
      // Dev: stage into public/ so Vite's static middleware serves it.
      mkdirSync(resolve(__dirname, publicDir, "data"), { recursive: true });
      copyIfPresent(publicDir);
    },
    closeBundle() {
      // Build: ensure it's in dist/ even if Vite didn't copy from public/.
      copyIfPresent(outDir);
    },
    configureServer(server) {
      // Re-copy on data-file changes so dev sees fresh data without restart.
      const watched = sources.map((s) => resolve(__dirname, s.src));
      for (const w of watched) {
        if (existsSync(w)) {
          server.watcher.add(w);
          // touch the watcher to register
          try { statSync(w); } catch { /* noop */ }
        }
      }
      server.watcher.on("change", (file) => {
        if (watched.includes(file)) copyIfPresent(publicDir);
      });
    },
  };
}

export default defineConfig({
  base: "./",
  root: ".",
  plugins: [dataAssets()],
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
