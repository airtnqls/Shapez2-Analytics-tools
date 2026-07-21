import type {
  AnalysisFacts,
  ColumnFact,
  HybridWitness,
  PinPushWitness,
  ShapeRows,
  StackWitness,
  Verdict,
  ShapeType,
} from "./types";
import {
  CRYSTAL,
  EMPTY,
  PIN,
  activeColumnCount,
  canonicalCode,
  cloneRows,
  maskColumns,
  occupiedCount,
  padRows,
  parseCode,
  pillars,
  rotateRows,
  rowsToCode,
  shapeHeight,
  trimRows,
} from "./shape";
import { generateCrystals, isStable, pushPin, stackShapes } from "./physics";
import { bottomPinReceiptProfile, bottomPinReceiptRank, forwardBatchUpperBound, ppChainUpperBound } from "./pp-rank";
import { solveRank0PinPush, uniquePlainPinPushPredecessor } from "./raw-pinpush-rank0";
import { findSwappableStackWitness, orientedHalfResidual } from "./stack-closure-dp";

export const CORNER_RULES: Array<[string, RegExp]> = [
  ["R1", /-P/],
  ["R2", /^P*-+c/],
  ["R3", /[^P]P.*c/],
  ["R4", /c-.*c/],
  ["R5", /cS-+c/],
  ["R6", /^S*-?S*c(.*c)?(S-+)+c/],
];

export interface KnownSample {
  status: "possible" | "impossible" | "unknown";
  route: string;
  shape_type: string;
  reason: string;
  cap?: number;
}

export interface ClawRecord {
  predecessor: string;
  backend: string;
}

export interface HybridRecord {
  bottom: string;
  top: string;
  cuts: number[];
  backend: string;
}

export interface ClassificationContext {
  knownSamples: Map<string, KnownSample>;
  clawTable?: Map<string, ClawRecord>;
  hybridTable?: Map<string, HybridRecord>;
}

export interface FastClassificationContext {
  knownSamples: Map<string, KnownSample>;
  clawTargets?: Set<string>;
  hybridTargets?: Set<string>;
}

export interface ClassificationHooks {
  cancelled?: () => boolean;
  progress?: (current: number, total: number, message: string) => void | Promise<void>;
  yieldEvery?: number;
}

export interface ClassificationOutcome {
  verdict: Verdict;
  shapeType: ShapeType;
  route: string;
  reason: string;
  explanation: string[];
  facts: AnalysisFacts;
  columns: ColumnFact[];
  witness?: StackWitness | ClawRecord | PinPushWitness | HybridWitness | Record<string, unknown>;
  candidatesChecked: number;
  statesVisited: number;
  warnings: string[];
}

export function cornerCheck(pillar: string): { accepted: boolean; violatedRule?: string } {
  for (const [name, pattern] of CORNER_RULES) {
    if (pattern.test(pillar)) return { accepted: false, violatedRule: name };
  }
  return { accepted: true };
}

export function columnFacts(rows: ShapeRows): ColumnFact[] {
  return pillars(rows).map((pillar, q) => {
    const checked = cornerCheck(pillar);
    return {
      quadrant: q,
      pillar,
      accepted: checked.accepted,
      violatedRule: checked.violatedRule,
    };
  });
}

export function isRawInput(rows: ShapeRows): boolean {
  const work = trimRows(rows);
  if (!work.length) return false;
  for (let q = 0; q < 4; q += 1) {
    let sawGap = false;
    for (let l = 0; l < work.length; l += 1) {
      const cell = work[l][q];
      if (cell === EMPTY || cell === PIN) sawGap = true;
      else if (sawGap) return false;
    }
  }
  return work.every((row) => row.every((cell) => cell !== PIN));
}

function halfColumns(rows: ShapeRows): number[] | null {
  const active = [0, 1, 2, 3].filter((q) => rows.some((row) => row[q] !== EMPTY));
  if (!active.length) return [0, 1];
  for (const cols of [[0, 1], [1, 2], [2, 3], [3, 0]]) {
    if (active.every((q) => cols.includes(q))) return cols;
  }
  return null;
}

/** Exact 210-state residual membership for one oriented adjacent half. */
export function isBuildableHalfRows(rows: ShapeRows, columns: number[] = [0, 1]): boolean {
  if (columns.length !== 2) return false;
  return orientedHalfResidual(rows, [columns[0], columns[1]]).accepted;
}

export function halfOrientation(rows: ShapeRows): { accepted: boolean; turns: number; columns: number[] } {
  let oriented = trimRows(rows);
  for (let turns = 0; turns < 4; turns += 1) {
    const cols = halfColumns(oriented);
    if (cols && isBuildableHalfRows(oriented, cols)) return { accepted: true, turns, columns: cols };
    oriented = rotateRows(oriented, 1);
  }
  return { accepted: false, turns: 0, columns: [] };
}

export function isSwappableRows(rows: ShapeRows): { accepted: boolean; turns: number; axis: number } {
  let oriented = trimRows(rows);
  for (let turns = 0; turns < 4; turns += 1) {
    const east = maskColumns(oriented, [0, 1]);
    const west = rotateRows(maskColumns(oriented, [2, 3]), 2);
    if (isBuildableHalfRows(east, [0, 1]) && isBuildableHalfRows(west, [0, 1])) {
      return { accepted: true, turns, axis: turns % 2 };
    }
    oriented = rotateRows(oriented, 1);
  }
  return { accepted: false, turns: 0, axis: 0 };
}

function generatorPredecessor(rows: ShapeRows, cap: number): string | null {
  const work = padRows(rows, cap);
  const height = shapeHeight(work);
  if (!height) return null;
  const predecessor = cloneRows(work);
  let changed = false;
  for (let l = 0; l < height; l += 1) {
    for (let q = 0; q < 4; q += 1) {
      if (work[l][q] === CRYSTAL) {
        predecessor[l][q] = EMPTY;
        changed = true;
      }
    }
  }
  if (!changed) return null;
  const candidate = rowsToCode(predecessor);
  return rowsToCode(generateCrystals(predecessor, cap)) === rowsToCode(rows) ? candidate : null;
}

function splitCandidates(rows: ShapeRows): number[][] {
  const height = shapeHeight(rows);
  return Array.from({ length: 4 }, (_, q) => {
    const values = new Set<number>([0, height]);
    for (let l = 0; l < height; l += 1) {
      if (rows[l][q] !== EMPTY) values.add(l + 1);
    }
    return [...values].sort((a, b) => a - b);
  });
}

function makeBottomAndPieces(rows: ShapeRows, cap: number, splits: number[]): { bottom: ShapeRows; pieces: string[] } | null {
  const work = padRows(rows, cap);
  const bottom = work.map((row, l) => row.map((cell, q) => (l < splits[q] ? cell : EMPTY)) as (typeof row));
  const topRows = work.map((row, l) => row.map((cell, q) => (l >= splits[q] ? cell : EMPTY)) as (typeof row));
  if (topRows.some((row) => row.some((cell) => cell === CRYSTAL))) return null;
  const pieces = topRows.map((row) => rowsToCode([row])).filter(Boolean);
  return { bottom: trimRows(bottom), pieces };
}

/** Legacy Cartesian split oracle retained only for differential tests. */
export async function findStackWitness(
  rows: ShapeRows,
  cap: number,
  basePredicate: (bottom: ShapeRows) => boolean,
  hooks: ClassificationHooks = {},
): Promise<{ witness: StackWitness | null; checked: number }> {
  const candidates = splitCandidates(rows);
  const total = candidates.reduce((n, values) => n * values.length, 1);
  let checked = 0;
  const yieldEvery = hooks.yieldEvery ?? 2048;
  for (const a of candidates[0]) {
    for (const b of candidates[1]) {
      for (const c of candidates[2]) {
        for (const d of candidates[3]) {
          if (hooks.cancelled?.()) throw new Error("CANCELLED");
          const splits = [a, b, c, d];
          checked += 1;
          const parts = makeBottomAndPieces(rows, cap, splits);
          if (parts && rowsToCode(parts.bottom) !== rowsToCode(rows) && basePredicate(parts.bottom)) {
            let replay = parts.bottom;
            for (const piece of parts.pieces) replay = stackShapes(replay, parseCode(piece, cap), cap);
            if (rowsToCode(replay) === rowsToCode(rows)) {
              return { witness: { bottom: rowsToCode(parts.bottom), topPieces: parts.pieces, splitHeights: splits }, checked };
            }
          }
          if (checked % yieldEvery === 0) {
            await hooks.progress?.(checked, total, `Stack ownership ${checked.toLocaleString()} / ${total.toLocaleString()}`);
            await new Promise((resolve) => setTimeout(resolve, 0));
          }
        }
      }
    }
  }
  return { witness: null, checked };
}

export async function brutePinPushPredecessor(
  target: ShapeRows,
  cap: number,
  predicate: (rows: ShapeRows) => boolean,
  hooks: ClassificationHooks = {},
): Promise<{ predecessor: string | null; checked: number }> {
  if (cap > 2) return { predecessor: null, checked: 0 };
  const cells = 4 * cap;
  const total = 4 ** cells;
  const chars = [EMPTY, "S", PIN, CRYSTAL] as const;
  let checked = 0;
  for (let value = 0; value < total; value += 1) {
    if (hooks.cancelled?.()) throw new Error("CANCELLED");
    let n = value;
    const rows = Array.from({ length: cap }, () => [EMPTY, EMPTY, EMPTY, EMPTY] as ShapeRows[number]);
    for (let i = 0; i < cells; i += 1) {
      rows[Math.floor(i / 4)][i % 4] = chars[n & 3];
      n >>>= 2;
    }
    checked += 1;
    if (isStable(rows) && predicate(rows) && rowsToCode(pushPin(rows, cap)) === rowsToCode(target)) {
      return { predecessor: rowsToCode(rows), checked };
    }
    if (checked % 2048 === 0) {
      await hooks.progress?.(checked, total, `Pin Push 전상 ${checked.toLocaleString()} / ${total.toLocaleString()}`);
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
  }
  return { predecessor: null, checked };
}

async function findPinPushWitness(
  target: ShapeRows,
  cap: number,
  context: ClassificationContext,
  hooks: ClassificationHooks,
): Promise<{ witness: PinPushWitness | null; checked: number; states: number; depth: number }> {
  const chain: Array<{ code: string; rows: ShapeRows }> = [];
  let current = padRows(target, cap);
  let checked = 0;
  let states = 0;

  for (let depth = 0; depth < 4 * cap; depth += 1) {
    if (hooks.cancelled?.()) throw new Error("CANCELLED");
    const currentCode = rowsToCode(current);
    const predecessor = uniquePlainPinPushPredecessor(current, cap);
    if (!predecessor) break;
    const predecessorRows = padRows(parseCode(predecessor, cap), cap);
    if (rowsToCode(predecessorRows) === currentCode) break;
    const before = bottomPinReceiptRank(current, cap);
    const after = bottomPinReceiptRank(predecessorRows, cap);
    if (after >= before) break;
    chain.push({ code: currentCode, rows: current });
    current = predecessorRows;
  }

  const candidates = [{ code: rowsToCode(current), rows: current }, ...chain.slice().reverse()];
  for (let index = 0; index < candidates.length; index += 1) {
    if (hooks.cancelled?.()) throw new Error("CANCELLED");
    const candidate = candidates[index];
    const receiptOutputs = chain.slice(0, chain.length - index).reverse().map((item) => item.code);

    const table = context.clawTable?.get(candidate.code);
    if (table && rowsToCode(pushPin(parseCode(table.predecessor, cap), cap)) === candidate.code) {
      return {
        witness: {
          predecessor: table.predecessor,
          backend: `${table.backend}+cap-verified-fastpath`,
          kind: receiptOutputs.length ? "receipt-chain" : "primitive-rank0",
          receiptTargets: [candidate.code, ...receiptOutputs],
        },
        checked, states, depth: receiptOutputs.length,
      };
    }

    await hooks.progress?.(index, Math.max(1, candidates.length), `Rank0 Pin Push core 검사 · receipt 후보 ${index + 1}/${candidates.length}`);
    const direct = solveRank0PinPush(candidate.rows, cap, { cancelled: hooks.cancelled });
    checked += direct.transitions;
    states += direct.maxFailedStates;
    if (!direct.ok || direct.predecessor === undefined) continue;

    const predecessorRows = parseCode(direct.predecessor, cap);
    let predecessorStack: StackWitness | undefined;
    if (!isSwappableRows(predecessorRows).accepted) {
      const stack = await findSwappableStackWitness(predecessorRows, cap, hooks);
      checked += stack.checked;
      states += stack.states;
      if (!stack.witness) throw new Error("RANK0_FRONTIER_CONTRACT_FAILURE: accepted Rank0 predecessor has no Stack/Swap witness");
      predecessorStack = stack.witness;
    }
    return {
      witness: {
        predecessor: direct.predecessor,
        backend: `browser-rank0-frontier:${direct.route ?? "overflow"}`,
        kind: receiptOutputs.length ? "receipt-chain" : "primitive-rank0",
        receiptTargets: [candidate.code, ...receiptOutputs],
        predecessorStack,
      },
      checked, states, depth: receiptOutputs.length,
    };
  }

  return { witness: null, checked, states, depth: chain.length };
}

function mapKnownType(value: string): ShapeType {
  const normalized = value.toUpperCase().replace("SWAPABLE", "SWAPPABLE");
  const allowed: ShapeType[] = ["EMPTY", "BASIC", "HALF", "SWAPPABLE", "STACKABLE", "CLAW", "CLAW_HYBRID", "PIN_PUSH", "IMPOSSIBLE", "UNKNOWN"];
  return allowed.includes(normalized as ShapeType) ? (normalized as ShapeType) : "UNKNOWN";
}

function baseFacts(rows: ShapeRows, columns: ColumnFact[]): AnalysisFacts {
  const half = halfOrientation(rows).accepted;
  const swappable = isSwappableRows(rows).accepted;
  const cap = Math.max(1, rows.length);
  const receiptProfile = bottomPinReceiptProfile(rows, cap);
  const receiptRank = bottomPinReceiptRank(rows, cap);
  return {
    stable: isStable(rows), basic: isRawInput(rows), half, swappable,
    stackable: false, claw: false, hybrid: false,
    generatorImage: Boolean(generatorPredecessor(rows, Math.max(1, rows.length))),
    height: shapeHeight(rows), occupiedCells: occupiedCount(rows), activeColumns: activeColumnCount(rows),
    receiptProfile, receiptRank,
    ppChainUpperBound: ppChainUpperBound(rows, cap), ppBatchUpperBound: forwardBatchUpperBound(cap),
    ppTerminationProof: "bottom-pin-receipt-rank", coverage: "complete",
  };
}

function rotatedLookup<T>(rows: ShapeRows, cap: number, table?: Map<string, T>): { value: T; matchedCode: string; restoreTurns: number } | null {
  if (cap !== 5 || !table) return null;
  let rotated = trimRows(rows);
  for (let turns = 0; turns < 4; turns += 1) {
    const matchedCode = rowsToCode(rotated);
    const value = table.get(matchedCode);
    if (value) return { value, matchedCode, restoreTurns: (4 - turns) % 4 };
    rotated = rotateRows(rotated, 1);
  }
  return null;
}

function rotatedSetHas(rows: ShapeRows, cap: number, set?: Set<string>): boolean {
  if (cap !== 5 || !set) return false;
  let rotated = trimRows(rows);
  for (let turns = 0; turns < 4; turns += 1) {
    if (set.has(rowsToCode(rotated))) return true;
    rotated = rotateRows(rotated, 1);
  }
  return false;
}

export async function classifyShape(
  code: string,
  cap: number,
  context: ClassificationContext,
  hooks: ClassificationHooks = {},
): Promise<ClassificationOutcome> {
  const rows = parseCode(code, cap);
  const normalized = rowsToCode(rows);
  const columns = columnFacts(rows);
  const facts = baseFacts(rows, columns);
  const warnings: string[] = [];
  let candidatesChecked = 0;
  let statesVisited = 0;

  const finish = (
    partial: Omit<ClassificationOutcome, "facts" | "columns" | "candidatesChecked" | "statesVisited" | "warnings">,
    factPatch: Partial<AnalysisFacts> = {},
  ): ClassificationOutcome => ({
    ...partial,
    facts: { ...facts, ...factPatch }, columns, candidatesChecked, statesVisited, warnings,
  });

  if (!normalized) return finish({ verdict: "IMPOSSIBLE", shapeType: "EMPTY", route: "empty", reason: "빈 도형은 제작 목표로 취급하지 않습니다.", explanation: ["입력에 점유 셀이 없습니다."] });
  if (!facts.stable) return finish({ verdict: "IMPOSSIBLE", shapeType: "IMPOSSIBLE", route: "unstable", reason: "최종 도형이 중력 적용 후 변하므로 제작 가능한 안정 출력이 아닙니다.", explanation: ["support closure가 모든 점유 셀을 포함하지 않습니다."] });

  const known = context.knownSamples.get(normalized);
  if (known?.status === "impossible") return finish({ verdict: "IMPOSSIBLE", shapeType: "IMPOSSIBLE", route: known.route || "known-negative-certificate", reason: known.reason, explanation: ["0.8.0 전건 감사에서 완전 음성 certificate가 봉인된 도형입니다."] });

  if (known?.status === "possible") {
    const expectedType = mapKnownType(known.shape_type);
    const expectedFamilyMatches = (expectedType === "BASIC" && facts.basic) || (expectedType === "HALF" && facts.half) || (expectedType === "SWAPPABLE" && facts.swappable);
    if (expectedFamilyMatches) return finish({ verdict: "POSSIBLE", shapeType: expectedType, route: known.route || expectedType.toLowerCase(), reason: known.reason, explanation: ["레거시 전건 감사의 ShapeType 우선순위를 보존했습니다."] });
  }

  if (facts.basic) return finish({ verdict: "POSSIBLE", shapeType: "BASIC", route: "basic", reason: "각 기둥이 원재료 입력의 연속 구조를 만족합니다.", explanation: ["추가 역연산 없이 입력 도형으로 사용할 수 있습니다."] });
  if (facts.half) return finish({ verdict: "POSSIBLE", shapeType: "HALF", route: "half-dfa", reason: "전층 210-state Half residual과 constructor 정리를 만족합니다.", explanation: ["Corner(left) ∧ Corner(right) ∧ Stable(left,right)", "판정은 exact minimized Half DFA를 사용합니다."] });
  if (facts.swappable) return finish({ verdict: "POSSIBLE", shapeType: "SWAPPABLE", route: "swap-half-dfa", reason: "한 축에서 양쪽 Half가 전층 Half family에 속합니다.", explanation: ["두 Half를 각각 제작한 뒤 Swapper로 결합할 수 있습니다."] });

  const clawLookup = rotatedLookup(rows, cap, context.clawTable);
  const claw = clawLookup?.value;
  if (claw && clawLookup) {
    facts.claw = true; facts.ppDepth = 1;
    return finish({ verdict: "POSSIBLE", shapeType: "CLAW", route: "claw-table", reason: "40,171개 인증 Claw parent table에서 회전 동등한 exact Pin Push predecessor를 찾았습니다.", explanation: [`predecessor: ${claw.predecessor}`, `backend: ${claw.backend}`], witness: { ...claw, targetCode: clawLookup.matchedCode, restoreTurns: clawLookup.restoreTurns } });
  }

  const hybrid = cap === 5 ? context.hybridTable?.get(normalized) : undefined;
  if (hybrid) {
    facts.hybrid = true;
    const bottomRows = parseCode(hybrid.bottom, cap);
    const bottomLookup = rotatedLookup(bottomRows, cap, context.clawTable);
    const bottomClaw = bottomLookup ? { ...bottomLookup.value, targetCode: bottomLookup.matchedCode, restoreTurns: bottomLookup.restoreTurns } : undefined;
    return finish({ verdict: "POSSIBLE", shapeType: "CLAW_HYBRID", route: "claw-hybrid-table", reason: "367개 인증 Claw-Hybrid 분해 테이블에서 exact Stack witness를 찾았습니다.", explanation: [`bottom: ${hybrid.bottom}`, `top: ${hybrid.top}`, bottomClaw ? "bottom의 Claw parent도 함께 materialize됩니다." : "bottom constructor는 인증 macro로 축약 표시됩니다."], witness: { ...hybrid, bottomClaw } as HybridWitness });
  }

  let ppResult: Awaited<ReturnType<typeof findPinPushWitness>> | null = null;
  if (facts.receiptRank > 0 && known?.status !== "possible") {
    await hooks.progress?.(0, Math.max(1, 4 * cap), "receipt chain 우선 압축");
    ppResult = await findPinPushWitness(rows, cap, context, hooks);
    candidatesChecked += ppResult.checked; statesVisited += ppResult.states;
    if (ppResult.witness?.kind === "receipt-chain") {
      facts.ppDepth = ppResult.witness.receiptTargets.length;
      return finish({ verdict: "POSSIBLE", shapeType: "PIN_PUSH", route: "pp-receipt-chain", reason: `유일한 no-overflow receipt predecessor를 ${ppResult.witness.receiptTargets.length - 1}회 압축한 뒤 Rank0 overflow core를 찾았습니다.`, explanation: [`primitive predecessor: ${ppResult.witness.predecessor || "<empty>"}`, `Pin Push outputs: ${ppResult.witness.receiptTargets.length}개`, "양성 witness는 각 Pin Push edge를 독립 정방향 replay해 확인했습니다."], witness: ppResult.witness });
    }
  }

  await hooks.progress?.(0, Math.max(1, shapeHeight(rows)), "StackClosure(Swappable) exact product");
  const stack = await findSwappableStackWitness(rows, cap, hooks);
  candidatesChecked += stack.checked; statesVisited += stack.states;
  if (stack.witness) {
    facts.stackable = true; facts.stackDepth = stack.witness.topPieces.length;
    return finish({ verdict: "POSSIBLE", shapeType: "STACKABLE", route: "stack-product-dp", reason: "Swappable base와 단층 top piece sequence가 exact target product에서 복원됐습니다.", explanation: [`base: ${stack.witness.bottom || "<빈 도형>"}`, `top pieces: ${stack.witness.topPieces.length}개`, "열별 split Cartesian product 대신 monotone ownership × Half residual DP를 사용했습니다."], witness: stack.witness });
  }

  if (known?.status === "possible") {
    const shapeType = mapKnownType(known.shape_type);
    return finish({ verdict: "POSSIBLE", shapeType, route: known.route || "validated-sample", reason: known.reason, explanation: ["0.8.0 샘플 회귀 세트에서 제작 Proof replay가 통과했습니다."] }, { stackable: shapeType === "STACKABLE", claw: shapeType === "CLAW", hybrid: shapeType === "CLAW_HYBRID" });
  }

  if (cap <= 2) {
    const brute = await brutePinPushPredecessor(rows, cap, (predecessor) => isRawInput(predecessor) || halfOrientation(predecessor).accepted || isSwappableRows(predecessor).accepted, hooks);
    candidatesChecked += brute.checked; statesVisited += brute.checked;
    if (brute.predecessor) {
      facts.ppDepth = 1;
      return finish({ verdict: "POSSIBLE", shapeType: "PIN_PUSH", route: "cap2-exhaustive-pinpush", reason: "Cap≤2 전체 안정 전상 열거에서 제작 가능한 Pin Push predecessor를 찾았습니다.", explanation: [`predecessor: ${brute.predecessor}`], witness: { predecessor: brute.predecessor, backend: "cap2-exhaustive" } });
    }
  }

  if (!ppResult) {
    await hooks.progress?.(0, Math.max(1, 4 * cap), "PP 정규형 탐색");
    ppResult = await findPinPushWitness(rows, cap, context, hooks);
    candidatesChecked += ppResult.checked; statesVisited += ppResult.states;
  }
  if (ppResult.witness) {
    facts.ppDepth = ppResult.witness.receiptTargets.length;
    return finish({ verdict: "POSSIBLE", shapeType: "PIN_PUSH", route: ppResult.witness.kind === "receipt-chain" ? "pp-receipt-chain" : "rank0-pinpush-frontier", reason: ppResult.witness.kind === "receipt-chain" ? `유일한 no-overflow receipt predecessor를 ${ppResult.witness.receiptTargets.length - 1}회 제거한 뒤 Rank0 overflow core를 찾았습니다.` : "전층 Rank0 Pin Push frontier가 Swappable/Stackable predecessor를 직접 복원했습니다.", explanation: [`primitive predecessor: ${ppResult.witness.predecessor || "<empty>"}`, `Pin Push outputs: ${ppResult.witness.receiptTargets.length}개`, "양성 witness는 각 Pin Push edge를 독립 정방향 replay해 확인했습니다."], witness: ppResult.witness });
  }

  if (!columns.every((column) => column.accepted)) warnings.push("Corner 필요조건 위반이 음성 certificate에 포함됐습니다.");
  return finish({ verdict: "IMPOSSIBLE", shapeType: "IMPOSSIBLE", route: "pp-closure-exhausted", reason: "Rank0/Stack/primitive-overflow 경로와 모든 유일 receipt predecessor를 소진했습니다.", explanation: ["Basic/Half/Swap/Stack/Generator/인증 Claw·Hybrid 경로에서 witness가 없습니다.", `Rank0 Pin Push frontier와 최대 ${facts.ppChainUpperBound}단계의 유일 receipt chain을 소진했습니다.`, "full-height PP-essential overflow는 Swappable 또는 Stackable 종단형으로 정규화됩니다."] });
}

function fastFacts(rows: ShapeRows): AnalysisFacts {
  const cap = Math.max(1, rows.length);
  const receiptProfile = bottomPinReceiptProfile(rows, cap);
  const receiptRank = bottomPinReceiptRank(rows, cap);
  return { stable: true, basic: false, half: false, swappable: false, stackable: false, claw: false, hybrid: false, generatorImage: false, height: shapeHeight(rows), occupiedCells: occupiedCount(rows), activeColumns: activeColumnCount(rows), receiptProfile, receiptRank, ppChainUpperBound: ppChainUpperBound(rows, cap), ppBatchUpperBound: forwardBatchUpperBound(cap), ppTerminationProof: "bottom-pin-receipt-rank", coverage: "complete" };
}

export async function classifyShapeFast(
  code: string,
  cap: number,
  context: FastClassificationContext,
  hooks: ClassificationHooks = {},
): Promise<ClassificationOutcome> {
  const rows = parseCode(code, cap);
  const normalized = rowsToCode(rows);
  const columns = columnFacts(rows);
  const facts = fastFacts(rows);
  const warnings: string[] = [];
  let candidatesChecked = 0;
  let statesVisited = 4 * Math.max(1, rows.length);
  const done = (partial: Omit<ClassificationOutcome, "facts" | "columns" | "candidatesChecked" | "statesVisited" | "warnings">): ClassificationOutcome => ({ ...partial, facts, columns, candidatesChecked, statesVisited, warnings });

  if (!normalized) return done({ verdict: "IMPOSSIBLE", shapeType: "EMPTY", route: "empty", reason: "빈 도형입니다.", explanation: [] });
  facts.stable = isStable(rows);
  if (!facts.stable) return done({ verdict: "IMPOSSIBLE", shapeType: "IMPOSSIBLE", route: "unstable", reason: "중력 적용 뒤 모양이 바뀌는 불안정 도형입니다.", explanation: [] });
  const known = context.knownSamples.get(normalized);
  if (known?.status === "impossible") return done({ verdict: "IMPOSSIBLE", shapeType: "IMPOSSIBLE", route: known.route || "known-negative-certificate", reason: known.reason, explanation: [] });

  facts.basic = isRawInput(rows);
  if (facts.basic) return done({ verdict: "POSSIBLE", shapeType: "BASIC", route: "basic", reason: "기본 입력으로 제작할 수 있습니다.", explanation: [] });
  facts.half = halfOrientation(rows).accepted;
  if (facts.half) return done({ verdict: "POSSIBLE", shapeType: "HALF", route: "half-dfa", reason: "전층 Half residual이 accept합니다.", explanation: [] });
  facts.swappable = isSwappableRows(rows).accepted;
  if (facts.swappable) return done({ verdict: "POSSIBLE", shapeType: "SWAPPABLE", route: "swap-half-dfa", reason: "두 Half를 교환기로 결합할 수 있습니다.", explanation: [] });

  if (rotatedSetHas(rows, cap, context.clawTargets)) { facts.claw = true; facts.ppDepth = 1; return done({ verdict: "POSSIBLE", shapeType: "CLAW", route: "claw-target-index", reason: "인증 Claw 집합에 포함됩니다.", explanation: [] }); }
  if (rotatedSetHas(rows, cap, context.hybridTargets)) { facts.hybrid = true; return done({ verdict: "POSSIBLE", shapeType: "CLAW_HYBRID", route: "hybrid-target-index", reason: "인증 Claw-Hybrid 집합에 포함됩니다.", explanation: [] }); }

  let ppResult: Awaited<ReturnType<typeof findPinPushWitness>> | null = null;
  if (facts.receiptRank > 0 && known?.status !== "possible") {
    await hooks.progress?.(0, Math.max(1, 4 * cap), "receipt chain 우선 판정");
    ppResult = await findPinPushWitness(rows, cap, { knownSamples: context.knownSamples }, hooks);
    candidatesChecked += ppResult.checked; statesVisited += ppResult.states;
    if (ppResult.witness) { facts.ppDepth = ppResult.witness.receiptTargets.length; return done({ verdict: "POSSIBLE", shapeType: "PIN_PUSH", route: ppResult.witness.kind === "receipt-chain" ? "pp-receipt-chain" : "rank0-pinpush-frontier", reason: "PP 정규형 predecessor가 존재합니다.", explanation: [], witness: ppResult.witness }); }
  }

  await hooks.progress?.(0, Math.max(1, shapeHeight(rows)), "Stack exact product");
  const stack = await findSwappableStackWitness(rows, cap, hooks);
  candidatesChecked += stack.checked; statesVisited += stack.states;
  if (stack.witness) { facts.stackable = true; facts.stackDepth = stack.witness.topPieces.length; return done({ verdict: "POSSIBLE", shapeType: "STACKABLE", route: "stack-product-dp", reason: "exact ownership × Half residual product가 accept합니다.", explanation: [], witness: stack.witness }); }

  if (known?.status === "possible") return done({ verdict: "POSSIBLE", shapeType: mapKnownType(known.shape_type), route: known.route || "validated-sample", reason: known.reason, explanation: [] });
  if (!ppResult) {
    await hooks.progress?.(0, Math.max(1, 4 * cap), "PP 정규형 판정");
    ppResult = await findPinPushWitness(rows, cap, { knownSamples: context.knownSamples }, hooks);
    candidatesChecked += ppResult.checked; statesVisited += ppResult.states;
  }
  if (ppResult.witness) { facts.ppDepth = ppResult.witness.receiptTargets.length; return done({ verdict: "POSSIBLE", shapeType: "PIN_PUSH", route: ppResult.witness.kind === "receipt-chain" ? "pp-receipt-chain" : "rank0-pinpush-frontier", reason: "PP 정규형 predecessor가 존재합니다.", explanation: [], witness: ppResult.witness }); }
  return done({ verdict: "IMPOSSIBLE", shapeType: "IMPOSSIBLE", route: "pp-closure-exhausted", reason: "모든 제작 family와 PP 정규형 predecessor를 소진했습니다.", explanation: [] });
}

export function canonicalLookupKey(code: string, cap: number): string {
  return canonicalCode(code, cap);
}
