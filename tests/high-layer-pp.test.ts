import { describe, expect, it } from "vitest";
import { classifyShape } from "../lib/classifier";
import { parseCode, rowsToCode } from "../lib/shape";
import { pushPin } from "../lib/physics";

const emptyContext = { knownSamples: new Map(), clawTable: new Map(), hybridTable: new Map() };

function liftedClawTarget(cap: number): string {
  let rows = parseCode("P-P-:--P-:-ScS", cap);
  for (let i = 0; i < cap - 3; i += 1) rows = pushPin(rows, cap);
  return rowsToCode(rows);
}

describe("high-layer receipt compression in the main4 PP engine", () => {
  for (const cap of [10, 20, 50, 100]) {
    it(`constructs a ${cap}-layer receipt tower without rank enumeration`, async () => {
      const code = liftedClawTarget(cap);
      const started = performance.now();
      const result = await classifyShape(code, cap, emptyContext, { yieldEvery: 1_000_000 });
      const elapsed = performance.now() - started;
      expect(result.verdict).toBe("POSSIBLE");
      expect(result.shapeType).toBe("PIN_PUSH");
      expect(result.route).toBe("pp-receipt-chain");
      expect(result.facts.ppDepth).toBe(cap - 2);
      expect(elapsed).toBeLessThan(30_000);
    }, 120000);
  }
});
