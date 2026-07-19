import { build } from "esbuild";

await build({
  entryPoints: ["workers/solver.worker.ts"],
  outfile: "public/solver.worker.js",
  bundle: true,
  minify: true,
  sourcemap: false,
  platform: "browser",
  format: "iife",
  target: ["es2022"],
  define: { "process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV ?? "development") },
});
