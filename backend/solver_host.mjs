import { readFile } from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath, pathToFileURL } from "node:url";

const backendDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(backendDir, "..");
const publicRoot = path.join(projectRoot, "public");
let listener;

function emit(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

globalThis.self = {
  location: { href: "https://shapez.local/solver.worker.js" },
  postMessage: emit,
  addEventListener(type, callback) {
    if (type === "message") listener = callback;
  },
};

globalThis.fetch = async (input) => {
  const url = new URL(String(input));
  const relative = decodeURIComponent(url.pathname).replace(/^[/\\]+/, "");
  const file = path.resolve(publicRoot, relative);
  if (file !== publicRoot && !file.startsWith(`${publicRoot}${path.sep}`)) {
    return new Response("forbidden", { status: 403 });
  }
  try {
    return new Response(await readFile(file), { status: 200 });
  } catch {
    return new Response("not found", { status: 404 });
  }
};

try {
  const workerUrl = pathToFileURL(path.join(publicRoot, "solver.worker.js")).href;
  await import(`${workerUrl}?local=${Date.now()}`);
  if (!listener) throw new Error("solver worker did not register its message listener");
  emit({ type: "host-ready", backend: "shapez2-worker", projectRoot });
} catch (error) {
  emit({ type: "host-error", error: error instanceof Error ? error.message : String(error) });
  process.exitCode = 1;
}

const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
lines.on("line", (line) => {
  if (!line.trim() || !listener) return;
  try {
    const message = JSON.parse(line);
    if (message.type === "shutdown") {
      lines.close();
      return;
    }
    listener({ data: message });
  } catch (error) {
    emit({ type: "host-error", error: error instanceof Error ? error.message : String(error) });
  }
});
