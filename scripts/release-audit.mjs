import { readFile, writeFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import path from "node:path";
import { pathToFileURL } from "node:url";

let listener;
const pending = new Map();
const progressByJob = new Map();
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
await import(`${pathToFileURL(path.resolve("public/solver.worker.js")).href}?audit=${Date.now()}`);
if (!listener) throw new Error("worker listener missing");
function analyze(jobId, mode, code, cap) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${jobId} timeout`)), 120000);
    pending.set(jobId, { resolve(message) { clearTimeout(timer); resolve(message); } });
    listener({ data: { type: "analyze", jobId, mode, code, cap } });
  });
}

const screenshotTarget = "--PP:--Pc:SSSS:-SS-:cS-S";
const fastMessage = await analyze("audit-fast", "fast", screenshotTarget, 5);
const typeMessage = await analyze("audit-type", "type", screenshotTarget, 5);
const proofMessage = await analyze("audit-proof", "proof", screenshotTarget, 5);
for (const message of [fastMessage, typeMessage, proofMessage]) {
  if (message.type !== "result") throw new Error(`unexpected worker response: ${message.type}`);
}
const fast = fastMessage.result;
const typed = typeMessage.result;
const proof = proofMessage.result;
const forest = JSON.parse(gunzipSync(await readFile("public/data/half-proof-forest-cap5.json.gz")).toString("utf8"));
const report = {
  version: "2.1.0-focused-ui-main4-pp",
  generatedAt: new Date().toISOString(),
  modeSeparation: {
    fast: {
      verdict: fast.verdict,
      proofGenerated: Boolean(fast.proof),
      tablesLoaded: fast.diagnostics.tablesLoaded,
      elapsedMsThisRun: fast.timing.totalMs,
    },
    analysis: {
      verdict: typed.verdict,
      shapeType: typed.shapeType,
      proofGenerated: Boolean(typed.proof),
      tablesLoaded: typed.diagnostics.tablesLoaded,
      elapsedMsThisRun: typed.timing.totalMs,
    },
    proof: {
      verdict: proof.verdict,
      shapeType: proof.shapeType,
      proofGenerated: Boolean(proof.proof),
      tablesLoaded: proof.diagnostics.tablesLoaded,
      elapsedMsThisRun: proof.timing.totalMs,
    },
    timingNote: "동일 프로세스 순차 실행이라 뒤 실행은 브라우저/데이터 캐시 영향을 받습니다. 기능 경계와 로드 데이터 차이를 검증하는 수치이며 보편적 벤치마크가 아닙니다.",
  },
  screenshotTargetProof: proof.proof ? {
    target: screenshotTarget,
    verdict: proof.verdict,
    shapeType: proof.shapeType,
    graphNodes: proof.proof.nodes.length,
    graphEdges: proof.proof.edges.length,
    uniqueOperationCount: proof.proof.uniqueOperationCount,
    expandedTreeOperationCount: proof.proof.expandedOperationCount,
    sharedNodeCount: proof.proof.sharedNodeCount,
    primitiveComplete: proof.proof.primitiveComplete,
    replayStatus: proof.proof.replayStatus,
    omittedReasons: proof.proof.omittedReasons,
  } : null,
  halfProofForest: {
    roots: Object.keys(forest.roots ?? {}).length,
    uniqueNodes: Object.keys(forest.nodes ?? {}).length,
    version: forest.version,
  },
  progressPhases: {
    fast: progressByJob.get("audit-fast"),
    analysis: progressByJob.get("audit-type"),
    proof: progressByJob.get("audit-proof"),
  },
};
await writeFile("reports/FOCUSED_UI_PROOF_AUDIT.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
