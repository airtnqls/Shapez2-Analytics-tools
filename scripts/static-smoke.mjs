import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const port = 4179;
const child = spawn(process.execPath, ["scripts/serve-static.mjs", String(port)], { stdio: ["ignore", "pipe", "pipe"] });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
try {
  let ok = false;
  for (let i = 0; i < 30; i += 1) {
    await sleep(100);
    try { const response = await fetch(`http://127.0.0.1:${port}/`); if (response.ok) { ok = true; break; } } catch {}
  }
  if (!ok) throw new Error("static server did not start");
  const [home, worker, table, serviceWorker] = await Promise.all([
    fetch(`http://127.0.0.1:${port}/`),
    fetch(`http://127.0.0.1:${port}/solver.worker.js`),
    fetch(`http://127.0.0.1:${port}/data/claw_parent_table.json.gz`),
    fetch(`http://127.0.0.1:${port}/sw.js`),
  ]);
  if (![home, worker, table, serviceWorker].every((response) => response.ok)) throw new Error("static asset returned non-200");
  if (home.headers.get("cross-origin-opener-policy") !== "same-origin") throw new Error("COOP header missing");
  if (home.headers.get("cross-origin-embedder-policy") !== "require-corp") throw new Error("COEP header missing");
  if (worker.headers.get("cache-control") !== "no-cache, must-revalidate") throw new Error("worker must be revalidated");
  if (table.headers.get("cache-control") !== "no-cache, must-revalidate") throw new Error("data must be revalidated");
  if (serviceWorker.headers.get("cache-control") !== "no-cache, no-store, must-revalidate") throw new Error("service worker must never be HTTP cached");
  const served = Buffer.from(await table.arrayBuffer());
  const local = await readFile("out/data/claw_parent_table.json.gz");
  const hash = (value) => createHash("sha256").update(value).digest("hex");
  if (hash(served) !== hash(local)) throw new Error("served table hash mismatch");
  const html = await home.text();
  if (!html.includes("Shapez2 TMAM Studio")) throw new Error("static HTML title missing");
  console.log(JSON.stringify({ status: "PASS", htmlBytes: html.length, workerBytes: Number(worker.headers.get("content-length") ?? 0) || (await worker.arrayBuffer()).byteLength, tableSha256: hash(served) }, null, 2));
} finally {
  child.kill("SIGTERM");
}
