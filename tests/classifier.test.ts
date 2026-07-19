import { describe, expect, it } from "vitest";
import { classifyShape, classifyShapeFast } from "../lib/classifier";
import { buildProofGraph } from "../lib/proof";
import type { AnalysisResult } from "../lib/types";

const emptyContext = { knownSamples: new Map(), clawTable: new Map(), hybridTable: new Map() };

function asResult(outcome: Awaited<ReturnType<typeof classifyShape>>, code: string, cap: number): AnalysisResult {
  return {
    jobId: "test",
    mode: "proof",
    originalCode: code,
    normalizedCode: code,
    cap,
    verdict: outcome.verdict,
    shapeType: outcome.shapeType,
    route: outcome.route,
    reason: outcome.reason,
    explanation: outcome.explanation,
    facts: outcome.facts,
    columns: outcome.columns,
    timing: { totalMs: 0, normalizeMs: 0, familyMs: 0, proofMs: 0, tableLoadMs: 0 },
    witness: outcome.witness,
    diagnostics: {
      backend: "test",
      backendVersion: "test",
      cacheHit: false,
      statesVisited: outcome.statesVisited,
      candidatesChecked: outcome.candidatesChecked,
      tablesLoaded: [],
      warnings: outcome.warnings,
    },
  };
}

describe("focused UI + main4 PP classifier", () => {
  it("classifies basic", async () => {
    const result = await classifyShape("SSSS", 2, emptyContext);
    expect(result.verdict).toBe("POSSIBLE");
    expect(result.shapeType).toBe("BASIC");
    expect(result.facts.coverage).toBe("complete");
  });

  it("uses strict claw table", async () => {
    const code = "-PPP:SS-P:---P:c--P:cS-S";
    const result = await classifyShape(code, 5, { ...emptyContext, clawTable: new Map([[code, { predecessor: "cPSS:cP-c:cScS:c---:c---", backend: "test" }]]) });
    expect(result.shapeType).toBe("CLAW");
    expect(result.verdict).toBe("POSSIBLE");
  });

  it("does not reuse the frozen cap-5 Claw table at another cap", async () => {
    const code = "-PPP:SS-P:---P:c--P:cS-S";
    const result = await classifyShape(code, 9, { ...emptyContext, clawTable: new Map([[code, { predecessor: "cPSS:cP-c:cScS:c---:c---", backend: "test" }]]) });
    expect(result.route).not.toBe("claw-table");
  });

  it("has a separate verdict-only path", async () => {
    const code = "-PPP:SS-P:---P:c--P:cS-S";
    const result = await classifyShapeFast(code, 5, { knownSamples: new Map(), clawTargets: new Set([code]), hybridTargets: new Set() });
    expect(result.verdict).toBe("POSSIBLE");
    expect(result.route).toBe("claw-target-index");
    expect(result.explanation).toEqual([]);
  });

  it("closes the former open PP boundary as a complete negative", async () => {
    const result = await classifyShape("S---:cSS-", 3, emptyContext);
    expect(result.verdict).toBe("IMPOSSIBLE");
    expect(result.route).toBe("pp-closure-exhausted");
    expect(result.facts.ppTerminationProof).toBe("bottom-pin-receipt-rank");
    expect(result.facts.coverage).toBe("complete");
  });

  it("constructs and replays an actual L6 higher-rank receipt chain", async () => {
    const code = "P-PP:S-PP:--Pc:-SSS:-P--:cS--";
    const outcome = await classifyShape(code, 6, emptyContext, { yieldEvery: 1_000_000 });
    expect(outcome.verdict).toBe("POSSIBLE");
    expect(outcome.shapeType).toBe("PIN_PUSH");
    expect(outcome.route).toBe("pp-receipt-chain");
    const proof = buildProofGraph(asResult(outcome, code, 6));
    expect(proof.replayStatus).not.toBe("failed");
    expect(proof.nodes.some((node) => node.operation === "PIN_PUSH")).toBe(true);
  }, 120000);
});
