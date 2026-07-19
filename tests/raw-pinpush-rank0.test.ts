import { describe, expect, it } from "vitest";
import { parseCode } from "../lib/shape";
import { pushPin } from "../lib/physics";
import { rowsToCode } from "../lib/shape";
import { solveRank0PinPush, uniquePlainPinPushPredecessor } from "../lib/raw-pinpush-rank0";

describe("browser-native Rank0 Pin Push frontier", () => {
  it("recovers a known Claw predecessor and replays", () => {
    const target = "PPPP:-PSS:-P--:-ScS";
    const result = solveRank0PinPush(parseCode(target, 5), 5);
    expect(result.ok).toBe(true);
    expect(result.predecessor).toBeTruthy();
    expect(rowsToCode(pushPin(parseCode(result.predecessor!, 5), 5))).toBe(target);
  }, 120000);

  it("recovers the unique no-overflow receipt predecessor", () => {
    const target = "P-PP:S-PP:--Pc:-SSS:-P--:cS--";
    const predecessor = uniquePlainPinPushPredecessor(parseCode(target, 6), 6);
    expect(predecessor).toBe("S-PP:--Pc:-SSS:-P--:cS--");
    expect(rowsToCode(pushPin(parseCode(predecessor!, 6), 6))).toBe(target);
  });
});
