import { spawn } from "node:child_process";
import readline from "node:readline";

const child = spawn(process.execPath, ["backend/solver_host.mjs"], {
  cwd: process.cwd(),
  stdio: ["pipe", "pipe", "inherit"],
});
const lines = readline.createInterface({ input: child.stdout, crlfDelay: Infinity });
const timeout = setTimeout(() => {
  child.kill();
  throw new Error("desktop solver host timed out");
}, 120_000);

let ready = false;
let completed = false;
for await (const line of lines) {
  const message = JSON.parse(line);
  if (message.type === "host-ready") {
    ready = true;
    child.stdin.write(`${JSON.stringify({
      type: "analyze",
      jobId: "desktop-smoke",
      mode: "proof",
      code: "S---:cSS-",
      cap: 3,
    })}\n`);
  }
  if (message.jobId === "desktop-smoke" && message.type === "result") {
    if (message.result.verdict !== "IMPOSSIBLE" || message.result.route !== "pp-closure-exhausted") {
      throw new Error(`unexpected desktop result: ${message.result.verdict}/${message.result.route}`);
    }
    if (!message.result.processRecipe || message.result.processRecipe.finalShapeNodeId !== message.result.proof?.rootId) {
      throw new Error("desktop result omitted the shared process recipe");
    }
    completed = true;
    child.stdin.write('{"type":"shutdown"}\n');
    child.stdin.end();
  }
}
clearTimeout(timeout);
if (!ready || !completed) throw new Error("desktop solver host ended before completing the smoke test");
console.log(JSON.stringify({ status: "PASS", backend: "desktop-jsonl-worker", recipe: "shared-worker-contract" }));
