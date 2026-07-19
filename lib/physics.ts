import type { Cell, ShapeRows } from "./types";
import {
  ADJ,
  CRYSTAL,
  EMPTY,
  ORDINARY,
  PIN,
  cloneRows,
  emptyRow,
  getCell,
  nonPin,
  occupied,
  padRows,
  rowsToCode,
  trimRows,
} from "./shape";

type CoordKey = string;

const coordKey = (layer: number, column: number): CoordKey => `${layer},${column}`;
const parseCoord = (key: CoordKey): [number, number] => key.split(",").map(Number) as [number, number];

export function crystalComponent(rows: ShapeRows, seeds: Array<[number, number]>): Set<CoordKey> {
  const todo: Array<[number, number]> = [];
  const seen = new Set<CoordKey>();
  for (const [l, q] of seeds) {
    if (getCell(rows, l, q) === CRYSTAL) {
      const key = coordKey(l, q);
      seen.add(key);
      todo.push([l, q]);
    }
  }
  while (todo.length) {
    const [l, q] = todo.shift()!;
    for (const nq of ADJ[q]) {
      const key = coordKey(l, nq);
      if (!seen.has(key) && getCell(rows, l, nq) === CRYSTAL) {
        seen.add(key);
        todo.push([l, nq]);
      }
    }
    for (const nl of [l - 1, l + 1]) {
      const key = coordKey(nl, q);
      if (nl >= 0 && nl < rows.length && !seen.has(key) && getCell(rows, nl, q) === CRYSTAL) {
        seen.add(key);
        todo.push([nl, q]);
      }
    }
  }
  return seen;
}

export function supportClosure(rows: ShapeRows): Set<CoordKey> {
  const supported = new Set<CoordKey>();
  const todo: Array<[number, number]> = [];
  if (rows.length) {
    for (let q = 0; q < 4; q += 1) {
      if (occupied(rows[0][q])) {
        supported.add(coordKey(0, q));
        todo.push([0, q]);
      }
    }
  }
  const add = (l: number, q: number) => {
    const key = coordKey(l, q);
    if (!supported.has(key)) {
      supported.add(key);
      todo.push([l, q]);
    }
  };
  while (todo.length) {
    const [l, q] = todo.shift()!;
    const cell = rows[l][q];
    if (l + 1 < rows.length && occupied(rows[l + 1][q])) add(l + 1, q);
    if (nonPin(cell)) {
      for (const nq of ADJ[q]) if (nonPin(rows[l][nq])) add(l, nq);
    }
    if (cell === CRYSTAL && l > 0 && rows[l - 1][q] === CRYSTAL) add(l - 1, q);
  }
  return supported;
}

function ordinaryGroupAtLayer(rows: ShapeRows, layer: number, startQ: number, allowed: Set<CoordKey>): Set<CoordKey> {
  const start = coordKey(layer, startQ);
  if (!allowed.has(start)) return new Set();
  if (getCell(rows, layer, startQ) === PIN) return new Set([start]);
  const group = new Set<CoordKey>();
  const todo = [startQ];
  while (todo.length) {
    const q = todo.pop()!;
    const key = coordKey(layer, q);
    if (group.has(key) || !allowed.has(key) || getCell(rows, layer, q) !== ORDINARY) continue;
    group.add(key);
    for (const nq of ADJ[q]) if (allowed.has(coordKey(layer, nq)) && getCell(rows, layer, nq) === ORDINARY) todo.push(nq);
  }
  return group;
}

export function applyGravity(rows: ShapeRows): ShapeRows {
  const work = cloneRows(rows);
  const supported = supportClosure(work);
  const unsupportedCrystals: Array<[number, number]> = [];
  for (let l = 0; l < work.length; l += 1) {
    for (let q = 0; q < 4; q += 1) {
      if (work[l][q] === CRYSTAL && !supported.has(coordKey(l, q))) unsupportedCrystals.push([l, q]);
    }
  }
  for (const key of crystalComponent(work, unsupportedCrystals)) {
    const [l, q] = parseCoord(key);
    work[l][q] = EMPTY;
  }

  const unsupported = new Set<CoordKey>();
  for (let l = 0; l < work.length; l += 1) {
    for (let q = 0; q < 4; q += 1) {
      if ((work[l][q] === ORDINARY || work[l][q] === PIN) && !supported.has(coordKey(l, q))) {
        unsupported.add(coordKey(l, q));
      }
    }
  }

  const consumed = new Set<CoordKey>();
  const highestBelow = [-1, -1, -1, -1];
  for (let sourceLayer = 0; sourceLayer < work.length; sourceLayer += 1) {
    for (let startQ = 0; startQ < 4; startQ += 1) {
      const start = coordKey(sourceLayer, startQ);
      if (!unsupported.has(start) || consumed.has(start)) continue;
      const allowed = new Set([...unsupported].filter((key) => !consumed.has(key)));
      const group = ordinaryGroupAtLayer(work, sourceLayer, startQ, allowed);
      if (!group.size) continue;
      for (const key of group) consumed.add(key);
      const pieces = [...group].map((key) => {
        const [l, q] = parseCoord(key);
        return { l, q, cell: work[l][q] };
      });
      for (const { l, q } of pieces) work[l][q] = EMPTY;
      const drop = Math.min(...pieces.map(({ q }) => sourceLayer - highestBelow[q] - 1));
      for (const { l, q, cell } of pieces) {
        const target = l - drop;
        work[target][q] = cell;
        if (target > highestBelow[q]) highestBelow[q] = target;
      }
    }
    for (let q = 0; q < 4; q += 1) if (work[sourceLayer][q] !== EMPTY) highestBelow[q] = sourceLayer;
  }
  return trimRows(work);
}

export function isStable(rows: ShapeRows): boolean {
  const work = cloneRows(rows);
  const count = work.reduce((sum, row) => sum + row.filter(occupied).length, 0);
  return supportClosure(work).size === count;
}

export function pushPin(rows: ShapeRows, cap: number): ShapeRows {
  const old = padRows(rows, cap);
  const shifted = Array.from({ length: cap + 1 }, emptyRow);
  for (let q = 0; q < 4; q += 1) if (occupied(old[0][q])) shifted[0][q] = PIN;
  for (let l = 0; l < cap; l += 1) shifted[l + 1] = [...old[l]];
  const seeds: Array<[number, number]> = [];
  for (let q = 0; q < 4; q += 1) if (shifted[cap][q] === CRYSTAL) seeds.push([cap, q]);
  for (const key of crystalComponent(shifted, seeds)) {
    const [l, q] = parseCoord(key);
    shifted[l][q] = EMPTY;
  }
  shifted.pop();
  return applyGravity(shifted);
}

function cutSeeds(rows: ShapeRows): Array<[number, number]> {
  const seeds: Array<[number, number]> = [];
  rows.forEach((row, l) => {
    for (const [a, b] of [[1, 2], [3, 0]] as const) {
      if (row[a] === CRYSTAL && row[b] === CRYSTAL) {
        seeds.push([l, a], [l, b]);
      }
    }
  });
  return seeds;
}

export function cutShape(rows: ShapeRows, cap: number): [ShapeRows, ShapeRows] {
  const work = padRows(rows, cap);
  for (const key of crystalComponent(work, cutSeeds(work))) {
    const [l, q] = parseCoord(key);
    work[l][q] = EMPTY;
  }
  const east = work.map((row) => [row[0], row[1], EMPTY, EMPTY] as Cell[]);
  const west = work.map((row) => [EMPTY, EMPTY, row[2], row[3]] as Cell[]);
  return [applyGravity(east), applyGravity(west)];
}

export function combineHalves(east: ShapeRows, west: ShapeRows, cap: number): ShapeRows {
  const a = padRows(east, cap);
  const b = padRows(west, cap);
  return trimRows(Array.from({ length: cap }, (_, l) => [a[l][0], a[l][1], b[l][2], b[l][3]]));
}

export function swapShapes(a: ShapeRows, b: ShapeRows, cap: number): [ShapeRows, ShapeRows] {
  const [ae, aw] = cutShape(a, cap);
  const [be, bw] = cutShape(b, cap);
  return [combineHalves(ae, bw, cap), combineHalves(be, aw, cap)];
}

export function stackShapes(bottom: ShapeRows, top: ShapeRows, cap: number): ShapeRows {
  const b = padRows(bottom, cap);
  const t = padRows(top, cap);
  const work = Array.from({ length: 2 * cap + 1 }, emptyRow);
  for (let l = 0; l < cap; l += 1) work[l] = [...b[l]];
  for (let l = 0; l < cap; l += 1) work[cap + 1 + l] = [...t[l]];
  return trimRows(applyGravity(work).slice(0, cap));
}

export function generateCrystals(rows: ShapeRows, cap: number): ShapeRows {
  const work = padRows(rows, cap);
  let height = 0;
  work.forEach((row, l) => {
    if (row.some(occupied)) height = l + 1;
  });
  for (let l = 0; l < height; l += 1) {
    for (let q = 0; q < 4; q += 1) if (work[l][q] === EMPTY || work[l][q] === PIN) work[l][q] = CRYSTAL;
  }
  return trimRows(work);
}

export function replayEquals(rows: ShapeRows, expectedCode: string): boolean {
  return rowsToCode(rows) === expectedCode;
}
