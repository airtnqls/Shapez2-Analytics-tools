import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

let listener;
const pending = new Map();

globalThis.self = {
  location: { href: "https://shapez.test/solver.worker.js" },
  postMessage(message) {
    if (message.type === "progress") return;
    const waiter = pending.get(message.jobId);
    if (!waiter) return;
    pending.delete(message.jobId);
    waiter.resolve(message);
  },
  addEventListener(type, callback) {
    if (type === "message") listener = callback;
  },
};

globalThis.fetch = async (input) => {
  const url = new URL(String(input));
  const file = path.join(process.cwd(), "public", url.pathname.replace(/^\//, ""));
  try { return new Response(await readFile(file), { status: 200 }); }
  catch { return new Response("not found", { status: 404 }); }
};

await import(`${pathToFileURL(path.resolve("public/solver.worker.js")).href}?audit=${Date.now()}`);
if (!listener) throw new Error("worker message listener was not registered");

function request(data, timeoutMs = 20_000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pending.delete(data.jobId);
      reject(new Error(`${data.jobId} timeout`));
    }, timeoutMs);
    pending.set(data.jobId, {
      resolve(message) {
        clearTimeout(timeout);
        resolve(message);
      },
    });
    listener({ data });
  });
}

const source = JSON.parse(await readFile(path.resolve("public/zip-tests.json"), "utf8"));
const tests = Object.entries(source).flatMap(([category, items]) => items.map((test) => ({ category, ...test })));
const mismatches = [];
let passed = 0;

for (const [index, test] of tests.entries()) {
  const operation = test.operation === "rotate" ? "rotate_cw" : test.operation;
  const cap = Math.max(5, test.input_a.split(":").length, (test.input_b || "").split(":").length);
  try {
    if (operation === "classifier") {
      const message = await request({ type: "analyze", jobId: `legacy-${index}`, mode: "type", code: test.input_a, cap }, 120_000);
      if (message.type !== "result") throw new Error(message.error || `unexpected ${message.type}`);
      const result = message.result;
      const expected = test.expected_a ?? "";
      const candidates = [result.shapeType, result.verdict, result.reason];
      if (candidates.some((value) => value === expected || value.includes(expected))) passed += 1;
      else mismatches.push({ index, category: test.category, name: test.name, operation, expectedA: expected, actualA: result.shapeType, verdict: result.verdict, route: result.route });
      continue;
    }

    const message = await request({
      type: "operate",
      jobId: `legacy-${index}`,
      operation,
      inputA: test.input_a,
      inputB: test.input_b || "",
      inputBPresent: operation === "stack" || operation === "swap",
      cap,
      paintColor: test.params?.color || "u",
      crystalColor: test.params?.color || "u",
    });
    if (message.type !== "operation-result") throw new Error(message.error || `unexpected ${message.type}`);
    const actualA = message.result.outputs[0] ?? message.result.message;
    const actualB = message.result.outputs[1] ?? "";
    if (actualA === (test.expected_a ?? "") && actualB === (test.expected_b ?? "")) passed += 1;
    else mismatches.push({ index, category: test.category, name: test.name, operation, expectedA: test.expected_a ?? "", actualA, expectedB: test.expected_b ?? "", actualB });
  } catch (error) {
    mismatches.push({ index, category: test.category, name: test.name, operation, error: String(error) });
  }
}

console.log(JSON.stringify({ total: tests.length, passed, failed: mismatches.length, mismatches }, null, 2));
process.exitCode = mismatches.length ? 1 : 0;
