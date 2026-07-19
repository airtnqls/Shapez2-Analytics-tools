import type { ShapeRows } from "./types";
import { HALF_ACC, HALF_START, HALF_TRANS } from "./half-dfa";
import { parseCode, rowsToCode, trimRows } from "./shape";

/**
 * Browser-native port of the audited width-four target-guided Pin Push frontier.
 * It searches for a predecessor in Rank0 = StackClosure(Swappable), and returns
 * an independently replayable concrete predecessor. No SMT/Z3 or cap table.
 */

const K_COLUMNS = 4;

enum CellCode {
  Empty = 0,
  Ordinary = 1,
  Pin = 2,
  Crystal = 3,
}

type Row = number;

interface SupportState {
  row: Row;
  desired: number;
  closure: number;
  positive: number;
  negative: number;
}
interface HalfTrack { current: number; committed: number }
interface SwappableState { half: [HalfTrack, HalfTrack, HalfTrack, HalfTrack] }
interface Rank0StackState {
  switched: number;
  hasA: boolean;
  support: SupportState;
  base: SwappableState;
  initialized: boolean;
}
interface FrontierKey {
  consumed: [number, number, number, number];
  post: SupportState;
  pre: SupportState;
  destroy: number;
  seenUnsupported: number;
  family: SwappableState;
  rank0Stack: Rank0StackState;
}
interface Decision { fixed: Row; destroy: number; unsupported: number }
interface Token { targetLayer: number; kind: CellCode }

export interface Rank0PinPushResult {
  ok: boolean;
  predecessor?: string;
  transitions: number;
  maxFailedStates: number;
  bottomMask: number;
  axis: number;
  route?: "plain" | "cap-one" | "swappable-overflow" | "stack-overflow";
}

export interface Rank0PinPushHooks {
  cancelled?: () => boolean;
  transitionLimit?: number;
}

function left(q: number): number { return (q + 3) & 3; }
function right(q: number): number { return (q + 1) & 3; }
function get(row: Row, q: number): CellCode { return ((row >>> (2 * q)) & 3) as CellCode; }
function set(row: Row, q: number, cell: CellCode): Row {
  return ((row & ~(3 << (2 * q))) | (cell << (2 * q))) & 0xff;
}
function occupied(cell: CellCode): boolean { return cell !== CellCode.Empty; }
function nonPin(cell: CellCode): boolean { return cell === CellCode.Ordinary || cell === CellCode.Crystal; }
function occupiedMask(row: Row): number {
  let mask = 0;
  for (let q = 0; q < K_COLUMNS; q += 1) if (occupied(get(row, q))) mask |= 1 << q;
  return mask;
}
function crystalMask(row: Row): number {
  let mask = 0;
  for (let q = 0; q < K_COLUMNS; q += 1) if (get(row, q) === CellCode.Crystal) mask |= 1 << q;
  return mask;
}
function popcount(value: number): number {
  let n = value >>> 0;
  n -= (n >>> 1) & 0x55555555;
  n = (n & 0x33333333) + ((n >>> 2) & 0x33333333);
  return (((n + (n >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24;
}
function decodeCell(cell: string): CellCode {
  if (cell === "-") return CellCode.Empty;
  if (cell === "P") return CellCode.Pin;
  if (cell === "c") return CellCode.Crystal;
  return CellCode.Ordinary;
}
function encodeCell(cell: CellCode): string {
  if (cell === CellCode.Ordinary) return "S";
  if (cell === CellCode.Pin) return "P";
  if (cell === CellCode.Crystal) return "c";
  return "-";
}
function rowString(row: Row): string {
  let out = "";
  for (let q = 0; q < 4; q += 1) out += encodeCell(get(row, q));
  return out;
}
function rowsCode(rows: readonly Row[]): string {
  let end = rows.length;
  while (end > 0 && rows[end - 1] === 0) end -= 1;
  return rows.slice(0, end).map(rowString).join(":");
}
function rowsFromShape(rows: ShapeRows, cap: number): Row[] {
  const out = Array<number>(cap).fill(0);
  for (let l = 0; l < Math.min(cap, rows.length); l += 1) {
    let row = 0;
    for (let q = 0; q < 4; q += 1) row = set(row, q, decodeCell(rows[l][q] ?? "-"));
    out[l] = row;
  }
  return out;
}

function matrixGet(matrix: number, i: number, j: number): boolean {
  return Boolean((matrix >>> (i * 5 + j)) & 1);
}
function transitiveClosure(graph: number[], n: number): void {
  for (let k = 0; k < n; k += 1) {
    for (let i = 0; i < n; i += 1) if (graph[i] & (1 << k)) graph[i] |= graph[k];
  }
}
function minimalAntichain(bits: number): number {
  let out = 0;
  for (let population = 1; population <= 4; population += 1) {
    for (let mask = 1; mask < 16; mask += 1) {
      if (popcount(mask) !== population || !(bits & (1 << mask))) continue;
      let dominated = false;
      for (let prior = 1; prior < 16; prior += 1) {
        if ((out & (1 << prior)) && ((prior & mask) === prior)) { dominated = true; break; }
      }
      if (!dominated) out |= 1 << mask;
    }
  }
  return out;
}
function supportStart(row: Row, desired: number): SupportState {
  const root = 4;
  const graph = Array<number>(9).fill(0);
  graph[root] |= 1 << root;
  for (let q = 0; q < 4; q += 1) {
    if (!occupied(get(row, q))) continue;
    graph[q] |= 1 << q;
    graph[root] |= 1 << q;
  }
  for (let q = 0; q < 4; q += 1) {
    const n = right(q);
    if (nonPin(get(row, q)) && nonPin(get(row, n))) {
      graph[q] |= 1 << n;
      graph[n] |= 1 << q;
    }
  }
  transitiveClosure(graph, 5);
  let closure = 0;
  for (let i = 0; i < 5; i += 1) for (let j = 0; j < 5; j += 1) {
    if (graph[i] & (1 << j)) closure |= 1 << (i * 5 + j);
  }
  return { row, desired, closure: closure >>> 0, positive: 0, negative: 0 };
}
function supportStep(old: SupportState, nextRow: Row, nextDesired: number): SupportState | null {
  const root = 4;
  const graph = Array<number>(9).fill(0);
  for (let i = 0; i < 5; i += 1) for (let j = 0; j < 5; j += 1) {
    if (matrixGet(old.closure, i, j)) graph[i] |= 1 << j;
  }
  for (let q = 0; q < 4; q += 1) if (occupied(get(nextRow, q))) graph[5 + q] |= 1 << (5 + q);
  for (let q = 0; q < 4; q += 1) {
    if (!occupied(get(old.row, q)) || !occupied(get(nextRow, q))) continue;
    graph[q] |= 1 << (5 + q);
    if (get(old.row, q) === CellCode.Crystal && get(nextRow, q) === CellCode.Crystal) graph[5 + q] |= 1 << q;
  }
  for (let q = 0; q < 4; q += 1) {
    const n = right(q);
    if (nonPin(get(nextRow, q)) && nonPin(get(nextRow, n))) {
      graph[5 + q] |= 1 << (5 + n);
      graph[5 + n] |= 1 << (5 + q);
    }
  }
  transitiveClosure(graph, 9);

  let positive = 0;
  for (let obligation = 1; obligation < 16; obligation += 1) {
    if (!(old.positive & (1 << obligation))) continue;
    let satisfied = false;
    for (let q = 0; q < 4; q += 1) if ((obligation & (1 << q)) && (graph[root] & (1 << q))) { satisfied = true; break; }
    if (satisfied) continue;
    let incoming = 0;
    for (let v = 0; v < 4; v += 1) for (let q = 0; q < 4; q += 1) {
      if ((obligation & (1 << q)) && (graph[5 + v] & (1 << q))) { incoming |= 1 << v; break; }
    }
    if (!incoming) return null;
    positive |= 1 << incoming;
  }
  for (let q = 0; q < 4; q += 1) if ((old.negative & (1 << q)) && (graph[root] & (1 << q))) return null;
  let negative = 0;
  for (let v = 0; v < 4; v += 1) for (let q = 0; q < 4; q += 1) {
    if ((old.negative & (1 << q)) && (graph[5 + v] & (1 << q))) { negative |= 1 << v; break; }
  }
  for (let q = 0; q < 4; q += 1) {
    if (!occupied(get(old.row, q))) continue;
    const reached = Boolean(graph[root] & (1 << q));
    let incoming = 0;
    for (let v = 0; v < 4; v += 1) if (graph[5 + v] & (1 << q)) incoming |= 1 << v;
    const wanted = Boolean(old.desired & (1 << q));
    if (wanted) {
      if (!reached) { if (!incoming) return null; positive |= 1 << incoming; }
    } else {
      if (reached) return null;
      negative |= incoming;
    }
  }
  for (let v = 0; v < 4; v += 1) if ((negative & (1 << v)) && (graph[root] & (1 << (5 + v)))) return null;
  let filtered = 0;
  for (let obligation = 1; obligation < 16; obligation += 1) {
    if (!(positive & (1 << obligation))) continue;
    let satisfied = false;
    for (let v = 0; v < 4; v += 1) if ((obligation & (1 << v)) && (graph[root] & (1 << (5 + v)))) { satisfied = true; break; }
    if (!satisfied) filtered |= 1 << obligation;
  }
  filtered = minimalAntichain(filtered);
  const keep = [5, 6, 7, 8, root];
  let closure = 0;
  for (let i = 0; i < 5; i += 1) for (let j = 0; j < 5; j += 1) {
    if (graph[keep[i]] & (1 << keep[j])) closure |= 1 << (i * 5 + j);
  }
  return { row: nextRow, desired: nextDesired, closure: closure >>> 0, positive: filtered, negative };
}
function supportFinish(state: SupportState): boolean {
  const closed = supportStep(state, 0, 0);
  return Boolean(closed && closed.positive === 0 && closed.negative === 0);
}

function destroyPack(mask: number, labels: readonly number[]): number {
  let out = mask & 15;
  for (let q = 0; q < 4; q += 1) out |= (labels[q] + 1) << (4 + 3 * q);
  return out & 0xffff;
}
function destroyMask(state: number): number { return state & 15; }
function destroyLabels(state: number): number[] {
  return [0, 1, 2, 3].map((q) => ((state >>> (4 + 3 * q)) & 7) - 1);
}
function destroyStart(mask: number): number {
  const labels = [-1, -1, -1, -1];
  let id = 0;
  for (let q = 0; q < 4; q += 1) {
    if (!(mask & (1 << q)) || labels[q] >= 0) continue;
    const pending = [q]; labels[q] = id;
    while (pending.length) {
      const a = pending.shift()!;
      for (const n of [left(a), right(a)]) if ((mask & (1 << n)) && labels[n] < 0) { labels[n] = id; pending.push(n); }
    }
    id += 1;
  }
  return destroyPack(mask, labels);
}
function destroyStep(oldState: number, nextMask: number): number | null {
  const oldLabels = destroyLabels(oldState);
  const oldMask = destroyMask(oldState);
  let oldCount = 0;
  for (let q = 0; q < 4; q += 1) if (oldLabels[q] >= 0) oldCount = Math.max(oldCount, oldLabels[q] + 1);
  const n = oldCount + 4;
  const parent = Array.from({ length: 8 }, (_, i) => i);
  const find = (start: number): number => {
    let a = start;
    while (parent[a] !== a) { parent[a] = parent[parent[a]]; a = parent[a]; }
    return a;
  };
  const unite = (aa: number, bb: number): void => {
    let a = find(aa), b = find(bb);
    if (a !== b) parent[Math.max(a, b)] = Math.min(a, b);
  };
  for (let q = 0; q < 4; q += 1) {
    const r = right(q);
    if ((nextMask & (1 << q)) && (nextMask & (1 << r))) unite(oldCount + q, oldCount + r);
    if ((oldMask & (1 << q)) && (nextMask & (1 << q))) unite(oldLabels[q], oldCount + q);
  }
  const continues = Array<boolean>(8).fill(false);
  for (let q = 0; q < 4; q += 1) if (nextMask & (1 << q)) continues[find(oldCount + q)] = true;
  const existed = Array<boolean>(4).fill(false);
  for (let q = 0; q < 4; q += 1) if (oldLabels[q] >= 0) existed[oldLabels[q]] = true;
  for (let label = 0; label < 4; label += 1) if (existed[label] && !continues[find(label)]) return null;
  const roots: Array<[number, number]> = [];
  for (let root = 0; root < n; root += 1) {
    if (!continues[root]) continue;
    let firstQ = 9;
    for (let q = 0; q < 4; q += 1) if ((nextMask & (1 << q)) && find(oldCount + q) === root) firstQ = Math.min(firstQ, q);
    roots.push([firstQ, root]);
  }
  roots.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const canonical = Array<number>(8).fill(-1);
  roots.forEach((entry, i) => { canonical[entry[1]] = i; });
  const labels = [-1, -1, -1, -1];
  for (let q = 0; q < 4; q += 1) if (nextMask & (1 << q)) labels[q] = canonical[find(oldCount + q)];
  return destroyPack(nextMask, labels);
}

function maskRow(row: Row, mask: number): Row {
  let out = 0;
  for (let q = 0; q < 4; q += 1) if (mask & (1 << q)) out = set(out, q, get(row, q));
  return out;
}
function halfSymbol(row: Row, a: number, b: number): number { return get(row, a) * 4 + get(row, b); }
function halfAdvance(old: HalfTrack, symbol: number): HalfTrack {
  const current = HALF_TRANS[old.current][symbol];
  return { current, committed: symbol !== 0 ? current : old.committed };
}
function swappableStart(row: Row): SwappableState {
  const symbols = [halfSymbol(row, 0, 1), halfSymbol(row, 2, 3), halfSymbol(row, 3, 0), halfSymbol(row, 1, 2)];
  return { half: symbols.map((symbol) => halfAdvance({ current: HALF_START, committed: HALF_START }, symbol)) as SwappableState["half"] };
}
function swappableStep(state: SwappableState, row: Row): SwappableState {
  const symbols = [halfSymbol(row, 0, 1), halfSymbol(row, 2, 3), halfSymbol(row, 3, 0), halfSymbol(row, 1, 2)];
  return { half: state.half.map((track, i) => halfAdvance(track, symbols[i])) as SwappableState["half"] };
}
function swappableFinish(state: SwappableState): boolean {
  return Boolean((HALF_ACC[state.half[0].committed] && HALF_ACC[state.half[1].committed]) ||
    (HALF_ACC[state.half[2].committed] && HALF_ACC[state.half[3].committed]));
}
function isSwappableRows(rows: readonly Row[]): boolean {
  if (!rows.length) return false;
  let state = swappableStart(rows[0]);
  for (let i = 1; i < rows.length; i += 1) state = swappableStep(state, rows[i]);
  return swappableFinish(state);
}

function ordinaryComponents(mask: number): number[][] {
  const out: number[][] = [];
  const seen = [false, false, false, false];
  for (let q = 0; q < 4; q += 1) {
    if (!(mask & (1 << q)) || seen[q]) continue;
    const component: number[] = [];
    const pending = [q]; seen[q] = true;
    while (pending.length) {
      const a = pending.shift()!; component.push(a);
      for (const n of [left(a), right(a)]) if ((mask & (1 << n)) && !seen[n]) { seen[n] = true; pending.push(n); }
    }
    out.push(component);
  }
  return out;
}
function stackLandingValid(row: Row, bMask: number, belowOccupied: number, floor: boolean): boolean {
  if (bMask === 0 || floor) return true;
  let pinMask = 0, ordinaryMask = 0;
  for (let q = 0; q < 4; q += 1) {
    if (!(bMask & (1 << q))) continue;
    if (get(row, q) === CellCode.Pin) pinMask |= 1 << q;
    if (get(row, q) === CellCode.Ordinary) ordinaryMask |= 1 << q;
  }
  if (pinMask & ~belowOccupied) return false;
  for (const component of ordinaryComponents(ordinaryMask)) {
    let mask = 0; for (const q of component) mask |= 1 << q;
    if (!(mask & belowOccupied)) return false;
  }
  return true;
}
function emptySupport(): SupportState { return { row: 0, desired: 0, closure: 0, positive: 0, negative: 0 }; }
function emptySwappable(): SwappableState {
  return { half: [0, 1, 2, 3].map(() => ({ current: HALF_START, committed: HALF_START })) as SwappableState["half"] };
}
function emptyRank0Stack(): Rank0StackState {
  return { switched: 0, hasA: false, support: emptySupport(), base: emptySwappable(), initialized: false };
}
function rank0StackNext(old: Rank0StackState | null, row: Row, previousRow: Row, floor: boolean): Rank0StackState[] {
  const occupiedBits = occupiedMask(row);
  const crystals = crystalMask(row);
  const switched = old?.switched ?? 0;
  if (switched & crystals) return [];
  const startable = occupiedBits & ~crystals & ~switched & 15;
  const out: Rank0StackState[] = [];
  for (let subset = startable;; subset = (subset - 1) & startable) {
    const nextMask = switched | subset;
    const bMask = occupiedBits & nextMask;
    if (stackLandingValid(row, bMask, occupiedMask(previousRow), floor)) {
      const aRow = maskRow(row, ~nextMask & 15);
      const support = old ? supportStep(old.support, aRow, occupiedMask(aRow)) : supportStart(aRow, occupiedMask(aRow));
      const base = old ? swappableStep(old.base, aRow) : swappableStart(aRow);
      if (support) out.push({ switched: nextMask, hasA: Boolean((old?.hasA ?? false) || occupiedMask(aRow)), support, base, initialized: true });
    }
    if (subset === 0) break;
  }
  return out;
}
function rank0StackFinish(state: Rank0StackState): boolean {
  return state.initialized && state.switched !== 0 && state.hasA && supportFinish(state.support) && swappableFinish(state.base);
}
function supportKey(s: SupportState): string { return `${s.row},${s.desired},${s.closure >>> 0},${s.positive},${s.negative}`; }
function swappableKey(s: SwappableState): string { return s.half.map((h) => `${h.current}.${h.committed}`).join(","); }
function rank0StackKey(s: Rank0StackState): string { return `${s.switched}|${+s.hasA}|${+s.initialized}|${supportKey(s.support)}|${swappableKey(s.base)}`; }
function dedupeRank0(states: Rank0StackState[]): Rank0StackState[] {
  const map = new Map<string, Rank0StackState>();
  for (const state of states) map.set(rank0StackKey(state), state);
  return [...map.values()];
}
function isRank0Rows(rows: readonly Row[]): boolean {
  if (!rows.length) return false;
  if (isSwappableRows(rows)) return true;
  let states = rank0StackNext(null, rows[0], 0, true);
  for (let i = 1; i < rows.length && states.length; i += 1) {
    const next: Rank0StackState[] = [];
    for (const state of states) next.push(...rank0StackNext(state, rows[i], rows[i - 1], false));
    states = dedupeRank0(next);
  }
  return states.some(rank0StackFinish);
}

function blockerHeight(highestCrystalBelow: number[][], sequences: Token[][], consumed: readonly number[], bottomMask: number, q: number, sourceResultLayer: number): number {
  let highest = bottomMask & (1 << q) ? 0 : -1;
  highest = Math.max(highest, highestCrystalBelow[q][sourceResultLayer]);
  if (consumed[q] > 0) highest = Math.max(highest, sequences[q][consumed[q] - 1].targetLayer);
  return highest;
}
function topRows(): Row[] {
  return Array.from({ length: 255 }, (_, i) => i + 1).sort((a, b) => {
    const score = (row: number): [number, number, number] => {
      let occupiedCount = 0, crystals = 0;
      for (let q = 0; q < 4; q += 1) { const c = get(row, q); occupiedCount += c !== CellCode.Empty ? 1 : 0; crystals += c === CellCode.Crystal ? 1 : 0; }
      return [crystals, occupiedCount, row];
    };
    const sa = score(a), sb = score(b);
    return sa[0] - sb[0] || sa[1] - sb[1] || sa[2] - sb[2];
  });
}
const TOP_ROWS = topRows();

function frontierKey(key: FrontierKey): string {
  return `${key.consumed.join(".")}|${supportKey(key.post)}|${supportKey(key.pre)}|${key.destroy}|${key.seenUnsupported}|${swappableKey(key.family)}|${rank0StackKey(key.rank0Stack)}`;
}

function solvePlainInverse(target: readonly Row[]): Row[] | null {
  const cap = target.length;
  if (cap < 1) return null;
  const predecessorBottom = cap >= 2 ? target[1] : 0;
  let expectedReceipt = 0;
  for (let q = 0; q < 4; q += 1) if (occupied(get(predecessorBottom, q))) expectedReceipt = set(expectedReceipt, q, CellCode.Pin);
  if (target[0] !== expectedReceipt) return null;
  const predecessor = Array<Row>(cap).fill(0);
  for (let layer = 0; layer + 1 < cap; layer += 1) predecessor[layer] = target[layer + 1];
  let height = cap - 1;
  while (height > 0 && predecessor[height - 1] === 0) height -= 1;
  if (height === 0) return predecessor;
  let state = supportStart(predecessor[0], occupiedMask(predecessor[0]));
  for (let layer = 1; layer < height; layer += 1) {
    const next = supportStep(state, predecessor[layer], occupiedMask(predecessor[layer]));
    if (!next) return null;
    state = next;
  }
  return supportFinish(state) ? predecessor : null;
}
function solveCapOne(target: readonly Row[]): Row[] | null {
  if (target.length !== 1) return null;
  let witness = 0;
  for (let q = 0; q < 4; q += 1) {
    const c = get(target[0], q);
    if (c === CellCode.Empty) continue;
    if (c !== CellCode.Pin) return null;
    witness = set(witness, q, CellCode.Ordinary);
  }
  return [witness];
}

function solveOverflow(target: readonly Row[], requireSwappable: boolean, requireRank0Stack: boolean, hooks: Rank0PinPushHooks = {}): Rank0PinPushResult {
  const layers = target.length;
  const result: Rank0PinPushResult = { ok: false, transitions: 0, maxFailedStates: 0, bottomMask: 0, axis: -1 };
  if (layers < 2) return result;
  for (let q = 0; q < 4; q += 1) if (get(target[0], q) === CellCode.Crystal) return result;

  const rawSequences: Token[][] = [[], [], [], []];
  const bottomPinColumns: number[] = [];
  for (let q = 0; q < 4; q += 1) {
    for (let layer = 0; layer < layers; layer += 1) {
      const c = get(target[layer], q);
      if (c === CellCode.Ordinary || c === CellCode.Pin) rawSequences[q].push({ targetLayer: layer, kind: c });
    }
    if (get(target[0], q) === CellCode.Pin) bottomPinColumns.push(q);
  }
  const survivingCrystals = Array<number>(layers - 1).fill(0);
  for (let source = 0; source < layers - 1; source += 1) {
    let mask = 0;
    for (let q = 0; q < 4; q += 1) if (get(target[source + 1], q) === CellCode.Crystal) mask |= 1 << q;
    survivingCrystals[source] = mask;
  }
  const highestCrystalBelow = Array.from({ length: 4 }, () => Array<number>(layers + 1).fill(-1));
  for (let q = 0; q < 4; q += 1) {
    let highest = -1;
    for (let row = 0; row <= layers; row += 1) {
      highestCrystalBelow[q][row] = highest;
      if (row < layers && get(target[row], q) === CellCode.Crystal) highest = row;
    }
  }
  const bottomSubsets = Array.from({ length: 1 << bottomPinColumns.length }, (_, i) => i).sort((a, b) => popcount(b) - popcount(a) || b - a);
  const baseChooseOrder = Array.from({ length: 16 }, (_, i) => i).sort((a, b) => popcount(a) - popcount(b) || a - b);
  const destroyOrders: number[][] = Array.from({ length: 16 }, () => []);
  const unsupportedOrders: number[][] = Array.from({ length: 16 }, () => []);
  for (let free = 0; free < 16; free += 1) {
    for (let subset = free;; subset = (subset - 1) & free) { destroyOrders[free].push(subset); if (subset === 0) break; }
    destroyOrders[free].sort((a, b) => {
      if (a === 0 || b === 0) return a === 0 ? -1 : 1;
      if (a === free || b === free) return a === free ? -1 : 1;
      return popcount(b) - popcount(a) || b - a;
    });
    unsupportedOrders[free].push(0);
    const rest: number[] = [];
    for (let subset = free; subset; subset = (subset - 1) & free) rest.push(subset);
    rest.sort((a, b) => popcount(a) - popcount(b) || a - b);
    unsupportedOrders[free].push(...rest);
  }

  for (const bottomSubset of bottomSubsets) {
    if (hooks.cancelled?.()) return result;
    let bottomMask = 0;
    for (let j = 0; j < bottomPinColumns.length; j += 1) if (bottomSubset & (1 << j)) bottomMask |= 1 << bottomPinColumns[j];
    const sequences = rawSequences.map((seq) => seq.slice());
    let valid = true;
    for (let q = 0; q < 4; q += 1) {
      if (!(bottomMask & (1 << q))) continue;
      if (!sequences[q].length || sequences[q][0].targetLayer !== 0 || sequences[q][0].kind !== CellCode.Pin) { valid = false; break; }
      sequences[q].shift();
    }
    if (!valid) continue;
    const goal = sequences.map((seq) => seq.length) as FrontierKey["consumed"];
    const failed = Array.from({ length: layers }, () => new Set<string>());
    const path: Decision[] = Array.from({ length: layers - 1 }, () => ({ fixed: 0, destroy: 0, unsupported: 0 }));
    let finalTop = 0;

    const dfs = (source: number, oldKey: FrontierKey | null): boolean => {
      if (hooks.cancelled?.()) return false;
      if (hooks.transitionLimit !== undefined && result.transitions >= hooks.transitionLimit) return false;
      if (source === layers - 1) {
        if (!oldKey) return false;
        if (oldKey.consumed.some((value, q) => value !== goal[q]) || !supportFinish(oldKey.post)) return false;
        const previousNondestroyed = crystalMask(oldKey.post.row);
        for (const top of TOP_ROWS) {
          const destroy = crystalMask(top);
          if (destroy & previousNondestroyed) continue;
          if (destroyStep(oldKey.destroy, destroy) === null) continue;
          const pre = supportStep(oldKey.pre, top, occupiedMask(top));
          if (!pre || !supportFinish(pre)) continue;
          const finalFamily = swappableStep(oldKey.family, top);
          if (requireSwappable && !swappableFinish(finalFamily)) continue;
          if (requireRank0Stack) {
            let accepted = false;
            for (const state of rank0StackNext(oldKey.rank0Stack, top, oldKey.pre.row, false)) if (rank0StackFinish(state)) { accepted = true; break; }
            if (!accepted) continue;
          }
          finalTop = top;
          return true;
        }
        return false;
      }
      if (oldKey) {
        const memo = frontierKey(oldKey);
        if (failed[source].has(memo)) return false;
      }
      const resultLayer = source + 1;
      const keepCrystals = survivingCrystals[source];
      const consumed = oldKey ? [...oldKey.consumed] as FrontierKey["consumed"] : [0, 0, 0, 0];
      const eligible = [false, false, false, false];
      let immediatelyStatic = 0;
      for (let q = 0; q < 4; q += 1) {
        eligible[q] = !(keepCrystals & (1 << q)) && consumed[q] < sequences[q].length && sequences[q][consumed[q]].targetLayer <= resultLayer;
        if (eligible[q] && sequences[q][consumed[q]].targetLayer === resultLayer) immediatelyStatic |= 1 << q;
      }
      const chooseOrder = [...baseChooseOrder].sort((a, b) => {
        const da = popcount(a ^ immediatelyStatic), db = popcount(b ^ immediatelyStatic);
        if (da !== db) return da - db;
        const ma = popcount(a & immediatelyStatic), mb = popcount(b & immediatelyStatic);
        if (ma !== mb) return mb - ma;
        return popcount(a) - popcount(b);
      });
      for (const choose of chooseOrder) {
        if (choose & keepCrystals) continue;
        let bad = false;
        for (let q = 0; q < 4; q += 1) if ((choose & (1 << q)) && !eligible[q]) { bad = true; break; }
        if (bad) continue;
        let fixed = 0;
        const targetLayers = [-1, -1, -1, -1];
        const nextConsumed = [...consumed] as FrontierKey["consumed"];
        let desiredSupport = keepCrystals;
        for (let q = 0; q < 4; q += 1) {
          if (keepCrystals & (1 << q)) fixed = set(fixed, q, CellCode.Crystal);
          else if (choose & (1 << q)) {
            const token = sequences[q][consumed[q]];
            fixed = set(fixed, q, token.kind);
            targetLayers[q] = token.targetLayer;
            nextConsumed[q] += 1;
            if (token.targetLayer === resultLayer) desiredSupport |= 1 << q;
          }
        }
        const fixedOccupied = occupiedMask(fixed);
        let fallingOrdinary = 0;
        for (let q = 0; q < 4; q += 1) if (get(fixed, q) === CellCode.Ordinary && !(desiredSupport & (1 << q))) fallingOrdinary |= 1 << q;
        let landingOk = true;
        for (const component of ordinaryComponents(fallingOrdinary)) {
          let targetLayer = -2;
          for (const q of component) {
            if (targetLayer === -2) targetLayer = targetLayers[q];
            else if (targetLayer !== targetLayers[q]) { landingOk = false; break; }
          }
          if (!landingOk || targetLayer < 0 || targetLayer >= resultLayer) { landingOk = false; break; }
          let highest = -1;
          for (const q of component) highest = Math.max(highest, blockerHeight(highestCrystalBelow, sequences, consumed, bottomMask, q, resultLayer));
          if (highest + 1 !== targetLayer) { landingOk = false; break; }
        }
        if (!landingOk) continue;
        for (let q = 0; q < 4; q += 1) {
          if (get(fixed, q) !== CellCode.Pin || (desiredSupport & (1 << q))) continue;
          const targetLayer = targetLayers[q];
          if (targetLayer < 0 || targetLayer >= resultLayer || blockerHeight(highestCrystalBelow, sequences, consumed, bottomMask, q, resultLayer) + 1 !== targetLayer) { landingOk = false; break; }
        }
        if (!landingOk) continue;
        const free = ~fixedOccupied & 15;
        for (const destroy of destroyOrders[free]) {
          const remaining = free & ~destroy;
          for (const unsupported of unsupportedOrders[remaining]) {
            result.transitions += 1;
            if (source === 0 && (fixedOccupied | destroy | unsupported) !== bottomMask) continue;
            const nondestroyed = keepCrystals | unsupported;
            if (destroy & nondestroyed) continue;
            let adjacentMixed = false;
            for (let q = 0; q < 4; q += 1) if ((destroy & (1 << q)) && ((nondestroyed & (1 << left(q))) || (nondestroyed & (1 << right(q))))) { adjacentMixed = true; break; }
            if (adjacentMixed) continue;
            if (source > 0 && oldKey) {
              const priorDestroy = destroyMask(oldKey.destroy);
              const priorNondestroyed = crystalMask(oldKey.post.row);
              if ((priorDestroy & nondestroyed) || (destroy & priorNondestroyed)) continue;
            }
            let postRow = fixed;
            for (let q = 0; q < 4; q += 1) if (unsupported & (1 << q)) postRow = set(postRow, q, CellCode.Crystal);
            let post: SupportState | null;
            if (source === 0) {
              let generated = 0;
              for (let q = 0; q < 4; q += 1) if (bottomMask & (1 << q)) generated = set(generated, q, CellCode.Pin);
              post = supportStep(supportStart(generated, bottomMask), postRow, desiredSupport);
            } else post = supportStep(oldKey!.post, postRow, desiredSupport);
            if (!post) continue;
            let sourceRow = postRow;
            for (let q = 0; q < 4; q += 1) if (destroy & (1 << q)) sourceRow = set(sourceRow, q, CellCode.Crystal);
            const pre = source === 0 ? supportStart(sourceRow, occupiedMask(sourceRow)) : supportStep(oldKey!.pre, sourceRow, occupiedMask(sourceRow));
            if (!pre) continue;
            const destroyState = source === 0 ? destroyStart(destroy) : destroyStep(oldKey!.destroy, destroy);
            if (destroyState === null) continue;
            const family = source === 0 ? swappableStart(sourceRow) : swappableStep(oldKey!.family, sourceRow);
            const stackStates = requireRank0Stack ? rank0StackNext(source === 0 ? null : oldKey!.rank0Stack, sourceRow, source === 0 ? 0 : oldKey!.pre.row, source === 0) : [emptyRank0Stack()];
            if (!stackStates.length) continue;
            path[source] = { fixed, destroy, unsupported };
            for (const rank0Stack of stackStates) {
              const next: FrontierKey = { consumed: nextConsumed, post, pre, destroy: destroyState, seenUnsupported: Number(Boolean((oldKey?.seenUnsupported ?? 0) || unsupported)), family, rank0Stack };
              if (dfs(source + 1, next)) return true;
            }
          }
        }
      }
      if (oldKey) {
        const memo = frontierKey(oldKey);
        failed[source].add(memo);
        result.maxFailedStates = Math.max(result.maxFailedStates, failed[source].size);
      }
      return false;
    };

    if (dfs(0, null)) {
      result.ok = true; result.bottomMask = bottomMask;
      const rows = Array<Row>(layers).fill(0);
      for (let source = 0; source < layers - 1; source += 1) {
        let row = path[source].fixed;
        for (let q = 0; q < 4; q += 1) if ((path[source].destroy | path[source].unsupported) & (1 << q)) row = set(row, q, CellCode.Crystal);
        rows[source] = row;
      }
      rows[layers - 1] = finalTop;
      result.predecessor = rowsCode(rows);
      result.route = requireSwappable ? "swappable-overflow" : "stack-overflow";
      return result;
    }
  }
  return result;
}

export function solveRank0PinPush(targetRows: ShapeRows, cap: number, hooks: Rank0PinPushHooks = {}): Rank0PinPushResult {
  const target = rowsFromShape(targetRows, cap);
  const plain = solvePlainInverse(target);
  if (plain && isRank0Rows(plain)) return { ok: true, predecessor: rowsCode(plain), transitions: 0, maxFailedStates: 0, bottomMask: occupiedMask(plain[0] ?? 0), axis: -2, route: "plain" };
  if (cap === 1) {
    const capOne = solveCapOne(target);
    if (capOne && isRank0Rows(capOne)) return { ok: true, predecessor: rowsCode(capOne), transitions: 0, maxFailedStates: 0, bottomMask: occupiedMask(capOne[0]), axis: -3, route: "cap-one" };
    return { ok: false, transitions: 0, maxFailedStates: 0, bottomMask: 0, axis: -3 };
  }
  const direct = solveOverflow(target, true, false, hooks);
  if (direct.ok) return direct;
  return solveOverflow(target, false, true, hooks);
}

export function uniquePlainPinPushPredecessor(targetRows: ShapeRows, cap: number): string | null {
  const rows = solvePlainInverse(rowsFromShape(targetRows, cap));
  return rows ? rowsCode(rows) : null;
}

export function isRank0Code(code: string, cap: number): boolean {
  return isRank0Rows(rowsFromShape(parseCode(code, cap), cap));
}

export function normalizeRank0Predecessor(code: string, cap: number): string {
  return rowsToCode(trimRows(parseCode(code, cap)));
}
