import { describe, expect, it } from "vitest";
import type { Cell, ShapeRows } from "../lib/types";
import { cornerCheck } from "../lib/classifier";
import { isStable, stackShapes } from "../lib/physics";
import { EMPTY, maskColumns, pillars, rotateRows, rowsToCode, trimRows } from "../lib/shape";
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

/** Independent statement of Corner(left) ∧ Corner(right) ∧ Stable(left,right). */
function semanticHalf(rows: ShapeRows, columns: readonly [number, number] = [0, 1]): boolean {
  const masked = maskColumns(rows, [...columns]);
  const ps = pillars(masked).filter((_, q) => columns.includes(q));
  return ps.every((pillar) => cornerCheck(pillar).accepted) && isStable(masked);
}

/** Independent two-axis Swappable theorem, deliberately not using the Half DFA. */
function semanticSwappable(rows: ShapeRows): boolean {
  let oriented = trimRows(rows);
  for (let turns = 0; turns < 4; turns += 1) {
    const east = maskColumns(oriented, [0, 1]);
    const west = rotateRows(maskColumns(oriented, [2, 3]), 2);
    if (semanticHalf(east) && semanticHalf(west)) return true;
    oriented = rotateRows(oriented, 1);
  }
  return false;
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
      if (!rowsToCode(bottom) || !semanticSwappable(bottom)) return false;
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
  it("matches the independent semantic Half theorem for every cap-2 oriented half", () => {
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
        semanticHalf(rows),
      );
    }
  });

  it("matches the independent Swappable theorem on a deterministic cap-2 sweep", () => {
    for (let value = 0; value < 4 ** 8; value += 17) {
      const rows = rowsFromInteger(value, 2);
      expect(swappableResidual(rows).accepted, rowsToCode(rows)).toBe(
        semanticSwappable(rows),
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

  it("collapses the dense 50-layer L^4 split worst case into the target product", async () => {
    const cap = 50;
    const target: ShapeRows = Array.from(
      { length: cap },
      () => ["S", "S", "S", "S"] as ShapeRows[number],
    );
    const legacySplitCandidates = (cap + 1) ** 4;
    expect(legacySplitCandidates).toBe(6_765_201);

    const result = await findSwappableStackWitness(target, cap, { yieldEvery: 1_000_000 });
    expect(result.witness).not.toBeNull();
    expect(result.witness?.topPieces.length).toBeGreaterThan(0);
    expect(result.states).toBeLessThan(50_000);
    expect(result.checked).toBeLessThan(1_000_000);
    expect(result.checked).toBeLessThan(legacySplitCandidates);
  }, 120000);
});
