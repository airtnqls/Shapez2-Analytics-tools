import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ungzip } from "pako";
import { classifyShape, type ClawRecord, type HybridRecord, type KnownSample } from "../lib/classifier";

function gz<T>(path: string): T {
  return JSON.parse(new TextDecoder().decode(ungzip(readFileSync(path)))) as T;
}

describe("132-shape legacy audit bridge", () => {
  it("preserves all decided verdicts and resolves the four legacy undecided samples", async () => {
    const samples = JSON.parse(readFileSync("public/data/known_samples.json", "utf8")) as Record<string, KnownSample>;
    const claw = gz<Record<string, ClawRecord>>("public/data/claw_parent_table.json.gz");
    const hybrid = gz<Record<string, HybridRecord>>("public/data/claw_hybrid_parent_table.json.gz");
    const context = {
      knownSamples: new Map(Object.entries(samples)),
      clawTable: new Map(Object.entries(claw)),
      hybridTable: new Map(Object.entries(hybrid)),
    };
    const mismatches: string[] = [];
    for (const [code, expected] of Object.entries(samples)) {
      const result = await classifyShape(code, expected.cap ?? Math.max(1, code.split(":").length), context, { yieldEvery: 1_000_000 });
      const expectedVerdict = expected.status === "possible" ? "POSSIBLE" : "IMPOSSIBLE";
      if (result.verdict !== expectedVerdict) {
        mismatches.push(`${code}: expected ${expectedVerdict}, got ${result.verdict}/${result.shapeType}/${result.route}`);
      } else if (expected.status === "possible" && result.shapeType !== expected.shape_type) {
        mismatches.push(`${code}: expected POSSIBLE/${expected.shape_type}, got ${result.verdict}/${result.shapeType}`);
      }
    }
    expect(mismatches).toEqual([]);
  }, 120000);
});
