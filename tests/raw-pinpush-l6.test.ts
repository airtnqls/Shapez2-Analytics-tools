import { describe, expect, it } from "vitest";
import { parseCode, rowsToCode } from "../lib/shape";
import { pushPin } from "../lib/physics";
import { solveRank0PinPush } from "../lib/raw-pinpush-rank0";

describe("L6 recursive PP cores", () => {
  const cores = [
    "S-PP:--Pc:-SSS:-P--:cS--",
    "S-PP:--Sc:-SSS:-P--:cS--",
    "S-PP:--cc:-SSS:-P--:cS--",
  ];
  for (const core of cores) it(`finds Rank0 parent for ${core}`, () => {
    const result = solveRank0PinPush(parseCode(core, 6), 6);
    expect(result.ok).toBe(true);
    expect(rowsToCode(pushPin(parseCode(result.predecessor!, 6), 6))).toBe(core);
  }, 120000);
});
