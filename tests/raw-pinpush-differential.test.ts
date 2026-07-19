import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import { parseCode, rowsToCode } from "../lib/shape";
import { pushPin } from "../lib/physics";
import { solveRank0PinPush } from "../lib/raw-pinpush-rank0";

type OracleRow = { target: string; sat: boolean };

const oracle = JSON.parse(
  gunzipSync(readFileSync("tests/fixtures/raw-pinpush-cap3-native-1000.json.gz")).toString("utf8"),
) as OracleRow[];

describe("TS frontier matches the frozen native audited frontier", () => {
  it("matches 1000 deterministic cap-3 targets", () => {
    const mismatches: string[] = [];
    for (const { target, sat } of oracle) {
      const actual = solveRank0PinPush(parseCode(target, 3), 3);
      if (actual.ok !== sat) mismatches.push(`${target} native=${sat} ts=${actual.ok}`);
      if (actual.ok && rowsToCode(pushPin(parseCode(actual.predecessor!, 3), 3)) !== rowsToCode(parseCode(target, 3))) {
        mismatches.push(`${target} replay`);
      }
    }
    expect(mismatches).toEqual([]);
  }, 120000);
});
