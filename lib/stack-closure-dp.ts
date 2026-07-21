import type { Cell, ShapeRows, StackWitness } from "./types";
import { HALF_ACC, HALF_START, HALF_TRANS } from "./half-dfa";
import { EMPTY, rowsToCode, trimRows } from "./shape";
import { stackShapes } from "./physics";

export interface StackClosureHooks {
  cancelled?: () => boolean;
  progress?: (current: number, total: number, message: string) => void | Promise<void>;
  yieldEvery?: number;
}

export interface StackClosureResult {
  witness: StackWitness | null;
  checked: number;
  states: number;
}

interface ProductState {
  axis: 0 | 1;
  switched: number;
  hasBottom: boolean;
  firstHalf: number;
  secondHalf: number;
  ended: number;
}

interface PathRecord {
  state: ProductState;
  cost: number;
  previousKey: number;
  ownershipMask: number;
}

const CELL_INDEX: Record<Cell, number> = { "-": 0, S: 1, P: 2, c: 3 };
const HALF_REJECT = HALF_TRANS.findIndex((row, state) => (
  !HALF_ACC[state] && row.every((next) => next === state)
));
const HALF_STATES = HALF_TRANS.length;
const ADJACENT: readonly (readonly number[])[] = [[1, 3], [0, 2], [1, 3], [0, 2]];
const AXIS_PAIRS: readonly [readonly [number, number], readonly [number, number]][] = [
  [[0, 1], [2, 3]],
  [[3, 0], [1, 2]],
];

function bitCount(value: number): number {
  let n = value & 15;
  let count = 0;
  while (n) {
    n &= n - 1;
    count += 1;
  }
  return count;
}

function rowMasks(row: ShapeRows[number]): { occupied: number; crystal: number; pin: number; ordinary: number } {
  let occupied = 0;
  let crystal = 0;
  let pin = 0;
  let ordinary = 0;
  for (let q = 0; q < 4; q += 1) {
    const bit = 1 << q;
    const cell = row[q] ?? EMPTY;
    if (cell === EMPTY) continue;
    occupied |= bit;
    if (cell === "c") crystal |= bit;
    else if (cell === "P") pin |= bit;
    else ordinary |= bit;
  }
  return { occupied, crystal, pin, ordinary };
}

function ordinaryComponents(mask: number): number[] {
  const out: number[] = [];
  let remaining = mask & 15;
  while (remaining) {
    const lowest = remaining & -remaining;
    const start = Math.log2(lowest) | 0;
    const stack = [start];
    let component = 0;
    while (stack.length) {
      const q = stack.pop()!;
      const bit = 1 << q;
      if ((component & bit) || !(remaining & bit)) continue;
      component |= bit;
      for (const neighbor of ADJACENT[q]) {
        const next = 1 << neighbor;
        if ((remaining & next) && !(component & next)) stack.push(neighbor);
      }
    }
    out.push(component);
    remaining &= ~component;
  }
  return out;
}

function landingRowIsValid(
  isFloor: boolean,
  bMask: number,
  masks: ReturnType<typeof rowMasks>,
  belowOccupied: number,
): boolean {
  if (!bMask || isFloor) return true;
  if ((masks.pin & bMask) & ~belowOccupied) return false;
  const ordinary = masks.ordinary & bMask;
  return ordinaryComponents(ordinary).every((component) => Boolean(component & belowOccupied));
}

function halfSymbol(row: ShapeRows[number], keepMask: number, pair: readonly [number, number]): number {
  const left = keepMask & (1 << pair[0]) ? row[pair[0]] : EMPTY;
  const right = keepMask & (1 << pair[1]) ? row[pair[1]] : EMPTY;
  return CELL_INDEX[left] * 4 + CELL_INDEX[right];
}

function advanceHalf(state: number, ended: boolean, symbol: number): { state: number; ended: boolean } | null {
  if (symbol === 0) return { state, ended: true };
  if (ended) return null;
  const next = HALF_TRANS[state]?.[symbol];
  if (next == null || (HALF_REJECT >= 0 && next === HALF_REJECT)) return null;
  return { state: next, ended: false };
}

export interface HalfResidualTrace {
  accepted: boolean;
  state: number;
  symbols: number[];
}

export function orientedHalfResidual(
  rows: ShapeRows,
  pair: readonly [number, number] = [0, 1],
): HalfResidualTrace {
  const projected = trimRows(rows.map((row) => [
    row[pair[0]] ?? EMPTY,
    row[pair[1]] ?? EMPTY,
    EMPTY,
    EMPTY,
  ]));
  let state: number = HALF_START;
  const symbols: number[] = [];
  for (const row of projected) {
    const symbol = CELL_INDEX[row[0]] * 4 + CELL_INDEX[row[1]];
    symbols.push(symbol);
    state = HALF_TRANS[state][symbol];
  }
  return { accepted: Boolean(HALF_ACC[state]), state, symbols };
}

export function swappableResidual(
  rows: ShapeRows,
): { accepted: boolean; axis: 0 | 1; states: readonly [number, number] } {
  const work = trimRows(rows);
  for (const axis of [0, 1] as const) {
    const pairs = AXIS_PAIRS[axis];
    const first = orientedHalfResidual(work, pairs[0]);
    const second = orientedHalfResidual(work, pairs[1]);
    if (first.accepted && second.accepted) {
      return { accepted: true, axis, states: [first.state, second.state] };
    }
  }
  return { accepted: false, axis: 0, states: [HALF_START, HALF_START] };
}

function stateKey(state: ProductState): number {
  let key = state.axis;
  key = key * 16 + state.switched;
  key = key * 2 + Number(state.hasBottom);
  key = key * HALF_STATES + state.firstHalf;
  key = key * HALF_STATES + state.secondHalf;
  key = key * 4 + state.ended;
  return key;
}

function transitionState(
  state: ProductState,
  row: ShapeRows[number],
  nextSwitched: number,
): ProductState | null {
  const keepMask = ~nextSwitched & 15;
  const pairs = AXIS_PAIRS[state.axis];
  const first = advanceHalf(state.firstHalf, Boolean(state.ended & 1), halfSymbol(row, keepMask, pairs[0]));
  if (!first) return null;
  const second = advanceHalf(state.secondHalf, Boolean(state.ended & 2), halfSymbol(row, keepMask, pairs[1]));
  if (!second) return null;
  return {
    axis: state.axis,
    switched: nextSwitched,
    hasBottom: state.hasBottom || row.some((cell, q) => cell !== EMPTY && Boolean(keepMask & (1 << q))),
    firstHalf: first.state,
    secondHalf: second.state,
    ended: Number(first.ended) | (Number(second.ended) << 1),
  };
}

function accepted(state: ProductState): boolean {
  return state.switched !== 0
    && state.hasBottom
    && Boolean(HALF_ACC[state.firstHalf])
    && Boolean(HALF_ACC[state.secondHalf]);
}

function materializeWitness(
  target: ShapeRows,
  cap: number,
  ownershipPath: number[],
): StackWitness {
  const bottomRows = target.map((row, layer) => row.map((cell, q) => (
    ownershipPath[layer] & (1 << q) ? EMPTY : cell
  )) as ShapeRows[number]);
  const topRows = target.map((row, layer) => row.map((cell, q) => (
    ownershipPath[layer] & (1 << q) ? cell : EMPTY
  )) as ShapeRows[number]);
  const topPieces = topRows.map((row) => rowsToCode([row])).filter(Boolean);
  const splitHeights = Array.from({ length: 4 }, (_, q) => {
    const found = ownershipPath.findIndex((mask) => Boolean(mask & (1 << q)));
    return found < 0 ? target.length : found;
  });
  const bottom = trimRows(bottomRows);
  let replay = bottom;
  for (const row of topRows) {
    if (row.every((cell) => cell === EMPTY)) continue;
    replay = stackShapes(replay, [row], cap);
  }
  if (rowsToCode(replay) !== rowsToCode(target)) {
    throw new Error("STACK_PRODUCT_CONTRACT_FAILURE: ownership witness did not replay");
  }
  return { bottom: rowsToCode(bottom), topPieces, splitHeights };
}

/**
 * Exact target-specific StackClosure(Swappable) product.
 *
 * The four split heights are represented as a monotone 4-bit ownership mask.
 * Bottom-family history is quotiented by two exact 210-state Half residuals;
 * future Stack landing depends only on the current ownership mask and the fixed
 * target row below. Therefore merging equal product states preserves both
 * soundness and completeness while avoiding the `(L+1)^4` split product.
 */
export async function findSwappableStackWitness(
  rows: ShapeRows,
  cap: number,
  hooks: StackClosureHooks = {},
): Promise<StackClosureResult> {
  const target = trimRows(rows);
  if (!target.length) return { witness: null, checked: 0, states: 0 };

  let current = new Map<number, PathRecord>();
  for (const axis of [0, 1] as const) {
    const state: ProductState = {
      axis,
      switched: 0,
      hasBottom: false,
      firstHalf: HALF_START,
      secondHalf: HALF_START,
      ended: 0,
    };
    current.set(stateKey(state), { state, cost: 0, previousKey: -1, ownershipMask: 0 });
  }

  const predecessorLayers: Array<Map<number, PathRecord>> = [];
  let checked = 0;
  let states = current.size;
  const yieldEvery = Math.max(1, hooks.yieldEvery ?? 4096);

  for (let layer = 0; layer < target.length; layer += 1) {
    const row = target[layer];
    const masks = rowMasks(row);
    const belowOccupied = layer ? rowMasks(target[layer - 1]).occupied : 0;
    const next = new Map<number, PathRecord>();

    for (const [previousKey, record] of current) {
      if (hooks.cancelled?.()) throw new Error("CANCELLED");
      const state = record.state;
      if (state.switched & masks.crystal) continue;
      const startable = masks.occupied & ~masks.crystal & ~state.switched & 15;
      let subset = startable;
      while (true) {
        checked += 1;
        const nextSwitched = state.switched | subset;
        const bMask = masks.occupied & nextSwitched;
        if (landingRowIsValid(layer === 0, bMask, masks, belowOccupied)) {
          const candidateState = transitionState(state, row, nextSwitched);
          if (candidateState) {
            const key = stateKey(candidateState);
            const candidate: PathRecord = {
              state: candidateState,
              cost: record.cost + bitCount(bMask),
              previousKey,
              ownershipMask: nextSwitched,
            };
            const old = next.get(key);
            if (!old || candidate.cost < old.cost || (
              candidate.cost === old.cost && candidate.ownershipMask < old.ownershipMask
            )) next.set(key, candidate);
          }
        }
        if (subset === 0) break;
        subset = (subset - 1) & startable;
      }

      if (checked % yieldEvery === 0) {
        await hooks.progress?.(layer + 1, target.length, `Stack product ${layer + 1}/${target.length} · ${next.size.toLocaleString()} states`);
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    }

    predecessorLayers.push(next);
    current = next;
    states += current.size;
    if (!current.size) return { witness: null, checked, states };
  }

  let winner: [number, PathRecord] | null = null;
  for (const entry of current) {
    if (!accepted(entry[1].state)) continue;
    if (!winner || entry[1].cost < winner[1].cost || (
      entry[1].cost === winner[1].cost && entry[0] < winner[0]
    )) winner = entry;
  }
  if (!winner) return { witness: null, checked, states };

  const ownershipReversed: number[] = [];
  let key = winner[0];
  for (let layer = predecessorLayers.length - 1; layer >= 0; layer -= 1) {
    const record = predecessorLayers[layer].get(key);
    if (!record) throw new Error("STACK_PRODUCT_BACKPOINTER_FAILURE");
    ownershipReversed.push(record.ownershipMask);
    key = record.previousKey;
  }
  ownershipReversed.reverse();
  const witness = materializeWitness(target, cap, ownershipReversed);
  return { witness, checked, states };
}
