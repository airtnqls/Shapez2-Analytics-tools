import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

let listener;
const progressByJob = new Map();
const pending = new Map();

globalThis.self = {
  location: { href: "https://shapez.test/solver.worker.js" },
  postMessage(message) {
    if (message.type === "progress") {
      const list = progressByJob.get(message.jobId) ?? [];
      list.push(message.phase);
      progressByJob.set(message.jobId, list);
      return;
    }
    const waiter = pending.get(message.jobId);
    if (waiter) { pending.delete(message.jobId); waiter.resolve(message); }
  },
  addEventListener(type, callback) { if (type === "message") listener = callback; },
};

globalThis.fetch = async (input) => {
  const url = new URL(String(input));
  const file = path.join(process.cwd(), "public", url.pathname.replace(/^\//, ""));
  try { return new Response(await readFile(file), { status: 200 }); }
  catch { return new Response("not found", { status: 404 }); }
};

await import(`${pathToFileURL(path.resolve("public/solver.worker.js")).href}?smoke=${Date.now()}`);
if (!listener) throw new Error("worker message listener was not registered");

function analyze(jobId, mode, code, cap) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { pending.delete(jobId); reject(new Error(`${jobId} timeout`)); }, 120000);
    pending.set(jobId, { resolve: (message) => { clearTimeout(timeout); resolve(message); } });
    listener({ data: { type: "analyze", jobId, mode, code, cap } });
  });
}

function operate(jobId, operation, inputA, inputB = "", cap = 5) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { pending.delete(jobId); reject(new Error(`${jobId} timeout`)); }, 10000);
    pending.set(jobId, { resolve: (message) => { clearTimeout(timeout); resolve(message); } });
    listener({ data: { type: "operate", jobId, operation, inputA, inputB, inputBPresent: operation === "stack" || operation === "swap", cap, paintColor: "u", crystalColor: "u" } });
  });
}

const rotateMessage = await operate("smoke-operate-rotate", "rotate_cw", "SS--");
if (rotateMessage.type !== "operation-result" || rotateMessage.result.outputs[0] !== "-SS-") throw new Error("ZIP rotate operation contract failed");
const cutMessage = await operate("smoke-operate-cut", "half_cutter", "SSSS");
if (cutMessage.type !== "operation-result" || cutMessage.result.outputs.join("|") !== "SS--|--SS") throw new Error("ZIP cut operation contract failed");
const emptyStackMessage = await operate("smoke-operate-empty-stack", "stack", "", "SSSS");
if (emptyStackMessage.type !== "operation-result" || emptyStackMessage.result.outputs[0] !== "SSSS") throw new Error("ZIP empty binary input contract failed");

const fastMessage = await analyze("smoke-fast", "fast", "-PPP:SS-P:---P:c--P:cS-S", 5);
if (fastMessage.type !== "result") throw new Error(`fast worker returned ${fastMessage.type}`);
const fast = fastMessage.result;
if (fast.verdict !== "POSSIBLE" || fast.proof) throw new Error("fast verdict path produced proof or wrong verdict");
if (fast.diagnostics.tablesLoaded.some((name) => name.includes("witness") || name.includes("forest"))) throw new Error("fast path loaded heavy witness data");

const typeMessage = await analyze("smoke-type", "type", "-PPP:SS-P:---P:c--P:cS-S", 5);
if (typeMessage.type !== "result") throw new Error(`type worker returned ${typeMessage.type}`);
const typed = typeMessage.result;
if (typed.verdict !== "POSSIBLE" || typed.shapeType !== "CLAW" || typed.proof) throw new Error("type analysis boundary failed");
if (!typed.diagnostics.tablesLoaded.some((name) => name.includes("witness"))) throw new Error("type path did not load witness data");

const clawMessage = await analyze("smoke-claw", "proof", "-PPP:SS-P:---P:c--P:cS-S", 5);
if (clawMessage.type !== "result") throw new Error(`claw worker returned ${clawMessage.type}`);
const claw = clawMessage.result;
if (claw.verdict !== "POSSIBLE" || claw.shapeType !== "CLAW" || claw.proof?.replayStatus !== "passed") throw new Error("claw proof smoke failed");
if (!claw.processRecipe?.steps?.length || claw.processRecipe.finalShapeNodeId !== claw.proof.rootId) throw new Error("process recipe was not emitted");

const negativeMessage = await analyze("smoke-negative", "proof", "S---:S-S-:SSSS", 5);
if (negativeMessage.type !== "result") throw new Error(`negative worker returned ${negativeMessage.type}`);
const negative = negativeMessage.result;
if (negative.verdict !== "IMPOSSIBLE" || negative.negativeCertificate?.verifier !== "passed") throw new Error("negative certificate smoke failed");

const closedMessage = await analyze("smoke-pp-closed", "proof", "S---:cSS-", 3);
if (closedMessage.type !== "result") throw new Error(`closed PP worker returned ${closedMessage.type}`);
const closed = closedMessage.result;
if (closed.verdict !== "IMPOSSIBLE" || closed.route !== "pp-closure-exhausted" || closed.negativeCertificate?.verifier !== "passed") {
  throw new Error(`closed PP boundary smoke failed: ${closed.verdict}/${closed.route}`);
}

const receiptMessage = await analyze("smoke-receipt", "proof", "P-PP:S-PP:--Pc:-SSS:-P--:cS--", 6);
if (receiptMessage.type !== "result") throw new Error(`receipt worker returned ${receiptMessage.type}`);
const receipt = receiptMessage.result;
if (receipt.verdict !== "POSSIBLE" || receipt.shapeType !== "PIN_PUSH" || receipt.route !== "pp-receipt-chain" || receipt.proof?.replayStatus === "failed") {
  throw new Error(`receipt-chain smoke failed: ${receipt.verdict}/${receipt.shapeType}/${receipt.route}/${receipt.proof?.replayStatus}`);
}

const tallHalfCode = "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----";
const tallHalfMessage = await analyze("smoke-tall-half", "proof", tallHalfCode, 11);
if (tallHalfMessage.type !== "result" || tallHalfMessage.result.verdict !== "POSSIBLE" || tallHalfMessage.result.shapeType !== "HALF") {
  throw new Error(`tall HALF client boundary failed: ${tallHalfMessage.type}/${tallHalfMessage.result?.verdict}/${tallHalfMessage.result?.shapeType}`);
}

const adaptiveCode = "--PP:--PP:--Pc:SSSS:-SS-:cS-S";
const adaptiveMessage = await analyze("smoke-adaptive-pp", "proof", adaptiveCode, 7);
if (adaptiveMessage.type !== "result" || adaptiveMessage.result.verdict !== "POSSIBLE" || adaptiveMessage.result.shapeType !== "PIN_PUSH") {
  throw new Error(`adaptive PP client boundary failed: ${adaptiveMessage.type}/${adaptiveMessage.result?.verdict}/${adaptiveMessage.result?.shapeType}`);
}

console.log(JSON.stringify({
  status: "PASS",
  operations: { rotate: rotateMessage.result.outputs, cut: cutMessage.result.outputs, emptyStack: emptyStackMessage.result.outputs },
  fast: { verdict: fast.verdict, tables: fast.diagnostics.tablesLoaded, totalMs: fast.timing.totalMs },
  analysis: { verdict: typed.verdict, type: typed.shapeType, tables: typed.diagnostics.tablesLoaded, totalMs: typed.timing.totalMs },
  claw: { verdict: claw.verdict, type: claw.shapeType, replay: claw.proof.replayStatus, phases: progressByJob.get("smoke-claw"), totalMs: claw.timing.totalMs },
  negative: { verdict: negative.verdict, certificate: negative.negativeCertificate.verifier, route: negative.route },
  ppClosed: { verdict: closed.verdict, route: closed.route, certificate: closed.negativeCertificate.verifier },
  receiptChain: { verdict: receipt.verdict, type: receipt.shapeType, route: receipt.route, replay: receipt.proof.replayStatus },
  tallHalf: { verdict: tallHalfMessage.result.verdict, type: tallHalfMessage.result.shapeType, nodes: tallHalfMessage.result.proof?.nodes.length, replay: tallHalfMessage.result.proof?.replayStatus },
  adaptivePP: { verdict: adaptiveMessage.result.verdict, type: adaptiveMessage.result.shapeType, nodes: adaptiveMessage.result.proof?.nodes.length, replay: adaptiveMessage.result.proof?.replayStatus },
}, null, 2));
