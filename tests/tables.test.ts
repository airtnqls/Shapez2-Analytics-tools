import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ungzip } from "pako";
import { parseCode, rowsToCode } from "../lib/shape";
import { pushPin, stackShapes } from "../lib/physics";

function table<T>(path: string): Record<string, T> {
  return JSON.parse(new TextDecoder().decode(ungzip(readFileSync(path)))) as Record<string, T>;
}

describe("certified browser data", () => {
  it("contains the complete frozen tables", () => {
    expect(Object.keys(table("public/data/claw_parent_table.json.gz"))).toHaveLength(40171);
    expect(Object.keys(table("public/data/claw_hybrid_parent_table.json.gz"))).toHaveLength(367);
  });
  it("replays every claw parent", () => {
    const rows = table<{ predecessor: string }>("public/data/claw_parent_table.json.gz");
    let failures = 0;
    for (const [target, record] of Object.entries(rows)) {
      const cap = Math.max(target.split(":").length, record.predecessor.split(":").length);
      if (rowsToCode(pushPin(parseCode(record.predecessor, cap), cap)) !== target) failures += 1;
    }
    expect(failures).toBe(0);
  }, 120000);
  it("replays every hybrid stack", () => {
    const rows = table<{ bottom: string; top: string }>("public/data/claw_hybrid_parent_table.json.gz");
    let failures = 0;
    for (const [target, record] of Object.entries(rows)) {
      const cap = Math.max(target.split(":").length, record.bottom.split(":").length, record.top.split(":").length);
      if (rowsToCode(stackShapes(parseCode(record.bottom, cap), parseCode(record.top, cap), cap)) !== target) failures += 1;
    }
    expect(failures).toBe(0);
  }, 120000);
});
