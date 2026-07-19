import { describe, expect, it } from "vitest";
import { applyGravity, cutShape, generateCrystals, isStable, pushPin, stackShapes, swapShapes } from "../lib/physics";
import { parseCode, rowsToCode } from "../lib/shape";

describe("forward physics", () => {
  it("recognizes stable inputs", () => expect(isStable(parseCode("SS--:S---", 3))).toBe(true));
  it("pin push inserts receipt pins", () => {
    expect(rowsToCode(pushPin(parseCode("S---", 3), 3))).toBe("P---:S---");
  });
  it("generator fills gaps and pins up to occupied height", () => {
    expect(rowsToCode(generateCrystals(parseCode("P---:S---", 3), 3))).toBe("cccc:Sccc");
  });
  it("cut and swap are deterministic", () => {
    const [east, west] = cutShape(parseCode("SSSS", 2), 2);
    expect(rowsToCode(east)).toBe("SS--");
    expect(rowsToCode(west)).toBe("--SS");
    const [a, b] = swapShapes(parseCode("SS--", 2), parseCode("--PP", 2), 2);
    expect(rowsToCode(a)).toBe("SSPP");
    expect(rowsToCode(b)).toBe("");
  });
  it("stack replays a single piece", () => {
    expect(rowsToCode(stackShapes(parseCode("S---", 3), parseCode("-S--", 3), 3))).toBe("SS--");
  });
  it("gravity is idempotent", () => {
    const once = applyGravity(parseCode("S---:---S", 3));
    expect(rowsToCode(applyGravity(once))).toBe(rowsToCode(once));
  });
});
