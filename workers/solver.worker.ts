/// <reference lib="webworker" />
import { ungzip } from "pako";
import {
  classifyShape,
  classifyShapeFast,
  type ClawRecord,
  type HybridRecord,
  type KnownSample,
} from "../lib/classifier";
import type { HalfProofForest } from "../lib/proof-forest";
import { maskColumns, mirrorRows, normalizeCode, parseCode, rotateRows, rowsToCode, simplifyExactCode } from "../lib/shape";
import { applyGravity, cutShape, generateCrystals, pushPin, stackShapes, swapShapes } from "../lib/physics";
import { buildNegativeCertificate, buildProofGraph } from "../lib/proof";
import { buildProcessRecipe } from "../lib/process-recipe";
import type { AnalysisResult, ProofGraph, WorkerInbound, WorkerOutbound } from "../lib/types";

const scope = self as unknown as DedicatedWorkerGlobalScope;
const cancelled = new Set<string>();
const cache = new Map<string, AnalysisResult>();
let knownSamplesPromise: Promise<Map<string, KnownSample>> | null = null;
let clawPromise: Promise<Map<string, ClawRecord>> | null = null;
let hybridPromise: Promise<Map<string, HybridRecord>> | null = null;
let clawTargetsPromise: Promise<Set<string>> | null = null;
let hybridTargetsPromise: Promise<Set<string>> | null = null;
let halfForestPromise: Promise<HalfProofForest> | null = null;
let clientProofCachePromise: Promise<Record<string, ProofGraph>> | null = null;

function assetUrl(relative: string): string { return new URL(relative, scope.location.href).toString(); }

async function loadJson<T>(relative: string): Promise<T> {
  const response = await fetch(assetUrl(relative));
  if (!response.ok) throw new Error(`데이터 로드 실패: ${relative} (${response.status})`);
  return response.json() as Promise<T>;
}

async function loadGzipJson<T>(relative: string): Promise<T> {
  const response = await fetch(assetUrl(relative));
  if (!response.ok) throw new Error(`압축 데이터 로드 실패: ${relative} (${response.status})`);
  const buffer = new Uint8Array(await response.arrayBuffer());
  return JSON.parse(new TextDecoder().decode(ungzip(buffer))) as T;
}

function knownSamples(): Promise<Map<string, KnownSample>> {
  knownSamplesPromise ??= loadJson<Record<string, KnownSample>>("./data/known_samples.json").then((value) => new Map(Object.entries(value)));
  return knownSamplesPromise;
}
function clawTable(): Promise<Map<string, ClawRecord>> {
  clawPromise ??= loadGzipJson<Record<string, ClawRecord>>("./data/claw_parent_table.json.gz").then((value) => new Map(Object.entries(value)));
  return clawPromise;
}
function hybridTable(): Promise<Map<string, HybridRecord>> {
  hybridPromise ??= loadGzipJson<Record<string, HybridRecord>>("./data/claw_hybrid_parent_table.json.gz").then((value) => new Map(Object.entries(value)));
  return hybridPromise;
}
function clawTargets(): Promise<Set<string>> {
  clawTargetsPromise ??= loadGzipJson<string[]>("./data/claw_targets_cap5.json.gz").then((value) => new Set(value));
  return clawTargetsPromise;
}
function hybridTargets(): Promise<Set<string>> {
  hybridTargetsPromise ??= loadGzipJson<string[]>("./data/hybrid_targets_cap5.json.gz").then((value) => new Set(value));
  return hybridTargetsPromise;
}
function halfForest(): Promise<HalfProofForest> {
  halfForestPromise ??= loadGzipJson<HalfProofForest>("./data/half-proof-forest-cap5.json.gz");
  return halfForestPromise;
}
function clientProofCache(): Promise<Record<string, ProofGraph>> {
  clientProofCachePromise ??= loadGzipJson<Record<string, ProofGraph>>("./data/client_proof_cache.json.gz");
  return clientProofCachePromise;
}

function post(message: WorkerOutbound): void { scope.postMessage(message); }
function isCancelled(jobId: string): boolean { return cancelled.has(jobId); }

function operate(message: Extract<WorkerInbound, { type: "operate" }>): void {
    const { jobId, operation, cap } = message;
  try {
    const a = parseCode(normalizeCode(message.inputA, cap), cap);
    const hasInputB = message.inputBPresent ?? Boolean(message.inputB);
    const b = hasInputB ? parseCode(normalizeCode(message.inputB ?? "", cap), cap) : [];
    let outputs: string[] = [];
    let note = "ZIP 구조 연산 완료";
    if (operation === "apply_physics") outputs = [rowsToCode(applyGravity(a))];
    else if (operation === "push_pin") outputs = [rowsToCode(pushPin(a, cap))];
    else if (operation === "crystal_generator") outputs = [rowsToCode(generateCrystals(a, cap))];
    else if (operation === "rotate_cw") outputs = [rowsToCode(rotateRows(a, 1))];
    else if (operation === "rotate_ccw") outputs = [rowsToCode(rotateRows(a, 3))];
    else if (operation === "rotate_180") outputs = [rowsToCode(rotateRows(a, 2))];
    else if (operation === "mirror") outputs = [rowsToCode(mirrorRows(a))];
    else if (operation === "stack") {
      if (!hasInputB) throw new Error("입력 B가 필요합니다.");
      outputs = [rowsToCode(stackShapes(a, b, cap))];
    } else if (operation === "swap") {
      if (!hasInputB) throw new Error("입력 B가 필요합니다.");
      outputs = swapShapes(a, b, cap).map(rowsToCode);
    } else if (operation === "half_cutter" || operation === "simple_cutter") outputs = cutShape(a, cap).map(rowsToCode);
    else if (operation === "destroy_half") outputs = [rowsToCode(cutShape(a, cap)[0])];
    else if (operation === "quad_cutter") {
      outputs = [0, 1, 2, 3].map((quadrant) => rowsToCode(rotateRows(maskColumns(a, [quadrant]), (4 - quadrant) % 4)));
    } else if (operation === "corner_1q" || operation === "cornerize") outputs = [rowsToCode(maskColumns(a, [0]))];
    else if (operation === "reverse") outputs = [rowsToCode([...a].reverse())];
    else if (operation === "simplify" || operation === "detail") outputs = [simplifyExactCode(message.inputA)];
    else if (operation === "paint") {
      outputs = [rowsToCode(a)];
      note = "ZIP 구조 엔진은 색상을 판정 상태에 포함하지 않으므로 구조를 유지했습니다.";
    } else throw new Error(`지원하지 않는 ZIP 연산: ${operation}`);
    post({ type: "operation-result", jobId, result: { operation, outputs, message: note } });
  } catch (error) {
    post({ type: "error", jobId, error: error instanceof Error ? error.message : String(error) });
  }
}

async function analyze(message: Extract<WorkerInbound, { type: "analyze" }>): Promise<void> {
  const started = performance.now();
  const { jobId, mode, code, cap } = message;
  cancelled.delete(jobId);
  post({ type: "progress", jobId, phase: "normalize", current: 0, total: 1, message: "도형 코드 확인", elapsedMs: 0 });

  let normalized: string;
  const normalizeStarted = performance.now();
  try { normalized = normalizeCode(code, cap); parseCode(normalized, cap); }
  catch (error) { post({ type: "error", jobId, error: error instanceof Error ? error.message : String(error) }); return; }
  const normalizeMs = performance.now() - normalizeStarted;
  const key = `${mode}|${cap}|${normalized}`;
  const cached = cache.get(key);
  if (cached) {
    const result = structuredClone(cached);
    result.jobId = jobId; result.originalCode = code; result.diagnostics.cacheHit = true; result.timing.totalMs = performance.now() - started;
    post({ type: "result", jobId, result }); return;
  }

  const tableStarted = performance.now();
  let samples: Map<string, KnownSample>;
  let claw = new Map<string, ClawRecord>();
  let hybrid = new Map<string, HybridRecord>();
  let clawTargetSet = new Set<string>();
  let hybridTargetSet = new Set<string>();
  let forest: HalfProofForest | undefined;
  const tablesLoaded: string[] = ["검증 샘플"];

  post({ type: "progress", jobId, phase: "data", current: 0, total: mode === "fast" ? 2 : mode === "type" ? 3 : 4, message: mode === "fast" ? "빠른 판정 인덱스 준비" : "분석 데이터 준비", elapsedMs: performance.now() - started });
  samples = await knownSamples();
  if (isCancelled(jobId)) { post({ type: "cancelled", jobId }); return; }

  if (mode === "fast") {
    if (cap === 5) {
      [clawTargetSet, hybridTargetSet] = await Promise.all([clawTargets(), hybridTargets()]);
      tablesLoaded.push("Claw 목표 인덱스", "Hybrid 목표 인덱스");
    }
  } else {
    post({ type: "progress", jobId, phase: "data", current: 1, total: mode === "type" ? 3 : 4, message: "Claw·Hybrid witness 준비", elapsedMs: performance.now() - started });
    if (cap === 5) {
      [claw, hybrid] = await Promise.all([clawTable(), hybridTable()]);
      tablesLoaded.push("Claw 40,171 witness", "Hybrid 367 witness");
    }
    if (mode === "proof" && cap === 5) {
      post({ type: "progress", jobId, phase: "data", current: 3, total: 4, message: "전층 Half 세부 공정 forest 준비", elapsedMs: performance.now() - started });
      forest = await halfForest();
      tablesLoaded.push("Half 세부 공정 forest");
    }
  }
  const tableLoadMs = performance.now() - tableStarted;
  if (isCancelled(jobId)) { post({ type: "cancelled", jobId }); return; }

  const familyStarted = performance.now();
  post({ type: "progress", jobId, phase: mode === "fast" ? "verdict" : "analysis", current: 0, total: 1, message: mode === "fast" ? "제작 가능 여부만 판정" : "도형 family와 witness 분석", elapsedMs: performance.now() - started });

  try {
    const hooks = {
      cancelled: () => isCancelled(jobId),
      progress: async (current: number, total: number, text: string) => {
        post({ type: "progress", jobId, phase: mode === "fast" ? "verdict" : "analysis", current, total, message: text, statesVisited: current, elapsedMs: performance.now() - started });
      },
    };
    const outcome = mode === "fast"
      ? await classifyShapeFast(normalized, cap, { knownSamples: samples, clawTargets: clawTargetSet, hybridTargets: hybridTargetSet }, hooks)
      : await classifyShape(normalized, cap, { knownSamples: samples, clawTable: claw, hybridTable: hybrid }, hooks);

    if (isCancelled(jobId)) { post({ type: "cancelled", jobId }); return; }
    const familyMs = performance.now() - familyStarted;
    const result: AnalysisResult = {
      jobId, mode, originalCode: code, normalizedCode: normalized, cap,
      verdict: outcome.verdict, shapeType: outcome.shapeType, route: outcome.route, reason: outcome.reason,
      explanation: mode === "fast" ? [] : outcome.explanation,
      facts: outcome.facts,
      columns: mode === "fast" ? [] : outcome.columns,
      timing: { totalMs: 0, normalizeMs, familyMs, proofMs: 0, tableLoadMs },
      witness: mode === "fast" ? undefined : outcome.witness,
      diagnostics: {
        backend: mode === "fast" ? "브라우저 빠른 판정기" : mode === "type" ? "브라우저 분석기" : "브라우저 공정 생성기",
        backendVersion: "2.1.0-focused-ui-main4-pp",
        cacheHit: false,
        statesVisited: outcome.statesVisited,
        candidatesChecked: outcome.candidatesChecked,
        tablesLoaded,
        warnings: outcome.warnings,
      },
    };

    if (mode !== "fast" && outcome.verdict !== "POSSIBLE") result.negativeCertificate = buildNegativeCertificate(result);
    if (mode === "proof") {
      const proofStarted = performance.now();
      post({ type: "progress", jobId, phase: "proof", current: 0, total: 1, message: "기본 입력까지 제작 공정 확장", elapsedMs: performance.now() - started });
      const cachedProof = (await clientProofCache())[`${cap}|${normalized}`];
      result.proof = cachedProof ? structuredClone(cachedProof) : buildProofGraph(result, forest);
      if (cachedProof) result.diagnostics.tablesLoaded.push("ZIP replay 검증 client proof cache");
      result.processRecipe = buildProcessRecipe(result.proof);
      result.timing.proofMs = performance.now() - proofStarted;
    }
    result.timing.totalMs = performance.now() - started;
    cache.set(key, structuredClone(result));
    post({ type: "result", jobId, result });
  } catch (error) {
    if (String(error).includes("CANCELLED") || isCancelled(jobId)) post({ type: "cancelled", jobId });
    else post({ type: "error", jobId, error: error instanceof Error ? error.message : String(error) });
  } finally { cancelled.delete(jobId); }
}

scope.addEventListener("message", (event: MessageEvent<WorkerInbound>) => {
  const message = event.data;
  if (message.type === "cancel") { cancelled.add(message.jobId); return; }
  if (message.type === "warmup") {
    const jobs: Promise<unknown>[] = [];
    if (!message.tables || message.tables.includes("samples")) jobs.push(knownSamples());
    if (!message.tables || message.tables.includes("targets")) jobs.push(clawTargets(), hybridTargets());
    void Promise.all(jobs).then(() => post({ type: "progress", jobId: message.jobId, phase: "warmup", current: 1, total: 1, message: "빠른 판정기 준비 완료" }))
      .catch((error) => post({ type: "error", jobId: message.jobId, error: String(error) }));
    return;
  }
  if (message.type === "operate") { operate(message); return; }
  void analyze(message);
});
