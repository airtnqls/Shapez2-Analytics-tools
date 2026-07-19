import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ungzip } from "pako";
import { classifyShape } from "../lib/classifier";
import { buildProofGraph } from "../lib/proof";
import type { HalfProofForest } from "../lib/proof-forest";
import type { AnalysisResult } from "../lib/types";

function gzipJson<T>(path: string): T {
  return JSON.parse(new TextDecoder().decode(ungzip(readFileSync(path)))) as T;
}

function resultFrom(target: string, cap: number, outcome: Awaited<ReturnType<typeof classifyShape>>): AnalysisResult {
  return {
    jobId: "proof-test", mode: "proof", originalCode: target, normalizedCode: target, cap,
    verdict: outcome.verdict, shapeType: outcome.shapeType, route: outcome.route, reason: outcome.reason,
    explanation: outcome.explanation, facts: outcome.facts, columns: outcome.columns, witness: outcome.witness,
    timing: { totalMs: 0, normalizeMs: 0, tableLoadMs: 0, familyMs: 0, proofMs: 0 },
    diagnostics: { backend: "browser-core", backendVersion: "2.1.0", cacheHit: false, statesVisited: outcome.statesVisited, candidatesChecked: outcome.candidatesChecked, tablesLoaded: [], warnings: outcome.warnings },
  };
}

describe("proof graph materialization", () => {
  const hybrids = gzipJson<Record<string, { bottom: string; top: string; cuts: number[]; backend: string }>>("public/data/claw_hybrid_parent_table.json.gz");
  const claws = gzipJson<Record<string, { predecessor: string; backend: string }>>("public/data/claw_parent_table.json.gz");
  const forest = gzipJson<HalfProofForest>("public/data/half-proof-forest-cap5.json.gz");

  it("expands a certified Claw predecessor to primitive operations", async () => {
    const [target] = Object.entries(claws)[0];
    const outcome = await classifyShape(target, 5, { knownSamples: new Map(), clawTable: new Map(Object.entries(claws)), hybridTable: new Map() });
    const graph = buildProofGraph(resultFrom(target, 5, outcome), forest);
    expect(graph.replayStatus).toBe("passed");
    expect(graph.primitiveComplete).toBe(true);
    expect(graph.uniqueOperationCount).toBeGreaterThan(10);
    expect(graph.nodes.some((node) => node.operation === "PIN_PUSH")).toBe(true);
    expect(graph.nodes.some((node) => node.operation === "RAW_INPUT" && node.metadata?.primitive === true)).toBe(true);
  }, 120000);

  it("shows an explicit omission instead of pretending a Hybrid macro is fully expanded", async () => {
    const [target, record] = Object.entries(hybrids)[0];
    const outcome = await classifyShape(target, 5, { knownSamples: new Map(), clawTable: new Map(Object.entries(claws)), hybridTable: new Map(Object.entries(hybrids)) });
    const graph = buildProofGraph(resultFrom(target, 5, outcome), forest);
    expect(graph.nodes.some((node) => node.kind === "operation" && node.operation === "STACK")).toBe(true);
    expect(graph.nodes.some((node) => node.kind === "shape" && node.code === target)).toBe(true);
    expect(graph.nodes.some((node) => node.kind === "shape" && node.code === record.bottom)).toBe(true);
    if (!graph.primitiveComplete) {
      expect(graph.replayStatus).toBe("partial");
      expect(graph.omittedReasons.length).toBeGreaterThan(0);
      expect(graph.nodes.some((node) => node.operation === "CERTIFIED_MACRO")).toBe(true);
    }
  }, 120000);
  it("fully expands the Claw-Hybrid shown in the UI report, including a rotated Claw bottom", async () => {
    const target = "--PP:--Pc:SSSS:-SS-:cS-S";
    const outcome = await classifyShape(target, 5, { knownSamples: new Map(), clawTable: new Map(Object.entries(claws)), hybridTable: new Map(Object.entries(hybrids)) });
    const graph = buildProofGraph(resultFrom(target, 5, outcome), forest);
    expect(outcome.shapeType).toBe("CLAW_HYBRID");
    expect(graph.replayStatus).toBe("passed");
    expect(graph.primitiveComplete).toBe(true);
    expect(graph.uniqueOperationCount).toBeGreaterThan(150);
    expect(graph.expandedOperationCount).toBeGreaterThan(graph.uniqueOperationCount);
    expect(graph.sharedNodeCount).toBeGreaterThan(0);
  }, 120000);

});
