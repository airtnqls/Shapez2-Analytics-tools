import { describe, expect, it } from "vitest";
import type { Cell, ShapeRows } from "../lib/types";
import { isBuildableHalfRows, isSwappableRows } from "../lib/classifier";
import { stackShapes } from "../lib/physics";
import { EMPTY, rowsToCode, trimRows } from "../lib/shape";
import {
  findSwappableStackWitness,
  orientedHalfResidual,
  swappableResidual,
} from "../lib/stack-closure-dp";

const CELLS: readonly Cell[] = [EMPTY, "S", "P", "c"];

function rowsFromInteger(value: number, cap: number): ShapeRows {
  let n = value;
  return Array.from({ length: cap }, () => Array.from({ length: 4 }, () => {
    const cell = CELLS[n & 3];
    n >>>= 2;
    return cell;
  }));
}

function bruteStackExists(targetRows: ShapeRows, cap: number): boolean {
  const target = trimRows(targetRows);
  if (!target.length) return false;
  const ownership: number[] = [];

  const visit = (layer: number, previousMask: number): boolean => {
    if (layer === target.length) {
      const bottom = trimRows(target.map((row, l) => row.map((cell, q) => (
        ownership[l] & (1 << q) ? EMPTY : cell
      )) as ShapeRows[number]));
      if (!rowsToCode(bottom) || !isSwappableRows(bottom).accepted) return false;
      const topRows = target.map((row, l) => row.map((cell, q) => (
        ownership[l] & (1 << q) ? cell : EMPTY
      )) as ShapeRows[number]);
      if (!topRows.some((row) => row.some((cell) => cell !== EMPTY))) return false;
      if (topRows.some((row) => row.some((cell) => cell === "c"))) return false;
      let replay = bottom;
      for (const row of topRows) {
        if (row.every((cell) => cell === EMPTY)) continue;
        replay = stackShapes(replay, [row], cap);
      }
      return rowsToCode(replay) === rowsToCode(target);
    }

    for (let mask = previousMask; mask < 16; mask += 1) {
      if ((mask & previousMask) !== previousMask) continue;
      ownership.push(mask);
      if (visit(layer + 1, mask)) return true;
      ownership.pop();
    }
    return false;
  };

  return visit(0, 0);
}

describe("exact Half residuals", () => {
  it("matches the semantic Half theorem for every cap-2 oriented half", () => {
    for (let value = 0; value < 4 ** 4; value += 1) {
      let n = value;
      const rows: ShapeRows = Array.from({ length: 2 }, () => [
        CELLS[n & 3],
        CELLS[(n >>> 2) & 3],
        EMPTY,
        EMPTY,
      ]);
      n >>>= 4;
      rows[1][0] = CELLS[n & 3];
      rows[1][1] = CELLS[(n >>> 2) & 3];
      expect(orientedHalfResidual(rows).accepted, rowsToCode(rows)).toBe(
        isBuildableHalfRows(rows, [0, 1]),
      );
    }
  });

  it("matches the existing Swappable predicate on a deterministic cap-2 sweep", () => {
    for (let value = 0; value < 4 ** 8; value += 17) {
      const rows = rowsFromInteger(value, 2);
      expect(swappableResidual(rows).accepted, rowsToCode(rows)).toBe(
        isSwappableRows(rows).accepted,
      );
    }
  });
});

describe("target-specific StackClosure(Swappable) product", () => {
  it("matches an independent full ownership oracle for every cap-1 target", async () => {
    for (let value = 0; value < 4 ** 4; value += 1) {
      const rows = rowsFromInteger(value, 1);
      const exact = await findSwappableStackWitness(rows, 1, { yieldEvery: 1_000_000 });
      expect(Boolean(exact.witness), rowsToCode(rows)).toBe(bruteStackExists(rows, 1));
    }
  });

  it("matches the full ownership oracle on a deterministic cap-2 sweep", async () => {
    for (let value = 0; value < 4 ** 8; value += 31) {
      const rows = rowsFromInteger(value, 2);
      const exact = await findSwappableStackWitness(rows, 2, { yieldEvery: 1_000_000 });
      expect(Boolean(exact.witness), rowsToCode(rows)).toBe(bruteStackExists(rows, 2));
    }
  }, 120000);

  it("keeps high-layer work in the target product rather than the L^4 split product", async () => {
    const cap = 50;
    let target: ShapeRows = [["S", "S", "S", "S"]];
    for (let i = 1; i < cap; i += 1) target = stackShapes(target, [["S", EMPTY, EMPTY, EMPTY]], cap);
    const result = await findSwappableStackWitness(target, cap, { yieldEvery: 1_000_000 });
    expect(result.witness).not.toBeNull();
    expect(result.witness?.topPieces.length).toBeGreaterThan(0);
    expect(result.states).toBeLessThan(50_000);
    expect(result.checked).toBeLessThan(1_000_000);
  }, 120000);
});
