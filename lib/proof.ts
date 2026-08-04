import type {
  AnalysisResult,
  ClawWitness,
  HybridWitness,
  PinPushWitness,
  NegativeCertificate,
  ProofEdgeData,
  ProofGraph,
  ProofNodeData,
  StackWitness,
} from "./types";
import type { HalfProofForest } from "./proof-forest";
import { maskColumns, parseCode, rotateRows, rowsToCode } from "./shape";
import { cutShape, generateCrystals, pushPin, stackShapes, swapShapes } from "./physics";
import { halfOrientation, isRawInput, isSwappableRows } from "./classifier";
import { koOperation } from "./ko";

class GraphBuilder {
  nodes: ProofNodeData[] = [];
  edges: ProofEdgeData[] = [];
  omissions = new Set<string>();
  private index = 0;
  private forestMemo = new Map<number, string>();

  id(prefix: string): string { this.index += 1; return `${prefix}-${this.index}`; }

  shape(code: string, status: ProofNodeData["status"] = "positive", metadata?: ProofNodeData["metadata"]): string {
    const id = this.id("shape");
    this.nodes.push({ id, kind: "shape", label: code || "<빈 도형>", code, status, metadata });
    return id;
  }

  operation(operation: string, status: ProofNodeData["status"] = "positive", metadata?: ProofNodeData["metadata"]): string {
    const id = this.id("op");
    this.nodes.push({ id, kind: "operation", label: koOperation(operation), operation, status, metadata });
    return id;
  }

  certificate(label: string, status: ProofNodeData["status"], metadata?: ProofNodeData["metadata"]): string {
    const id = this.id("cert");
    this.nodes.push({ id, kind: "certificate", label, status, metadata });
    return id;
  }

  edge(source: string, target: string, label: string, dashed = false): void {
    this.edges.push({ id: this.id("edge"), source, target, label, dashed });
  }

  memoForest(index: number, id?: string): string | undefined {
    if (id) this.forestMemo.set(index, id);
    return this.forestMemo.get(index);
  }
}

function rawPrimitive(builder: GraphBuilder): string {
  const op = builder.operation("RAW_INPUT", "positive", { primitive: true });
  const shape = builder.shape("SSSS", "positive", { primitive: true });
  builder.edge(op, shape, "출력");
  return shape;
}

function macroShape(builder: GraphBuilder, code: string, reason: string, metadata?: ProofNodeData["metadata"]): string {
  builder.omissions.add(reason);
  const cert = builder.certificate(reason, "unknown", { ...metadata, omitted: true });
  const op = builder.operation("CERTIFIED_MACRO", "unknown", { ...metadata, omitted: true });
  builder.edge(cert, op, "미세 공정 미포함", true);
  const shape = builder.shape(code, "unknown", metadata);
  builder.edge(op, shape, "출력", true);
  return shape;
}

function operationInputLabels(op: string, count: number): string[] {
  if (op === "STACK") return ["바닥", "상단"];
  if (op === "SWAP") return ["입력 A", "입력 B"];
  return Array.from({ length: count }, (_, i) => count === 1 ? "입력" : `입력 ${i + 1}`);
}

function addUnusedOutput(builder: GraphBuilder, operationId: string, code: string, label = "사용하지 않은 출력"): void {
  const ghost = builder.shape(code, "ghost", { unused: true });
  builder.edge(operationId, ghost, label, true);
}

function forestNodeReplay(forest: HalfProofForest, index: number): { selected: string; unused?: string } {
  const node = forest.nodes[index];
  const childCodes = node.children.map((child) => forest.nodes[child].result);
  try {
    if (node.op === "RAW_INPUT") return { selected: "SSSS" };
    if (node.op === "ROTATE") return { selected: rowsToCode(rotateRows(parseCode(childCodes[0], node.cap), Number(node.parameter ?? 0))) };
    if (node.op === "CUT") {
      const outputs = cutShape(parseCode(childCodes[0], node.cap), node.cap).map(rowsToCode);
      const selectedIndex = node.parameter === "west" ? 1 : 0;
      return { selected: outputs[selectedIndex], unused: outputs[1 - selectedIndex] };
    }
    if (node.op === "SWAP") {
      const outputs = swapShapes(parseCode(childCodes[0], node.cap), parseCode(childCodes[1], node.cap), node.cap).map(rowsToCode);
      const selectedIndex = Number(node.parameter ?? 0) === 1 ? 1 : 0;
      return { selected: outputs[selectedIndex], unused: outputs[1 - selectedIndex] };
    }
    if (node.op === "STACK") return { selected: rowsToCode(stackShapes(parseCode(childCodes[0], node.cap), parseCode(childCodes[1], node.cap), node.cap)) };
    if (node.op === "GENERATE") return { selected: rowsToCode(generateCrystals(parseCode(childCodes[0], node.cap), node.cap)) };
    if (node.op === "PIN_PUSH") return { selected: rowsToCode(pushPin(parseCode(childCodes[0], node.cap), node.cap)) };
  } catch {}
  return { selected: node.result };
}

function materializeForestNode(builder: GraphBuilder, forest: HalfProofForest, index: number): string {
  const memo = builder.memoForest(index);
  if (memo) return memo;
  const node = forest.nodes[index];
  if (!node) return macroShape(builder, "", "Half proof forest 노드 누락", { forestIndex: index });
  if (node.op === "RAW_INPUT") {
    const shape = rawPrimitive(builder);
    builder.memoForest(index, shape);
    return shape;
  }

  const children = node.children.map((child) => materializeForestNode(builder, forest, child));
  const operation = builder.operation(node.op, "positive", {
    parameter: node.parameter == null ? "" : String(node.parameter),
    forestIndex: index,
    theorem: "Corner/Half all-layer constructor",
  });
  const labels = operationInputLabels(node.op, children.length);
  children.forEach((child, i) => builder.edge(child, operation, labels[i]));
  const output = builder.shape(node.result, "positive", { forestIndex: index });
  builder.edge(operation, output, "출력");
  const replay = forestNodeReplay(forest, index);
  if ((node.op === "CUT" || node.op === "SWAP") && replay.unused !== undefined) addUnusedOutput(builder, operation, replay.unused, "다른 출력");
  if (replay.selected !== node.result) builder.omissions.add(`forest replay mismatch #${index}`);
  builder.memoForest(index, output);
  return output;
}

function materializeHalf(builder: GraphBuilder, code: string, cap: number, forest?: HalfProofForest): string {
  if (cap === 5 && forest && Object.prototype.hasOwnProperty.call(forest.roots, code)) return materializeForestNode(builder, forest, forest.roots[code]);
  if (code === "SSSS") return rawPrimitive(builder);
  return macroShape(builder, code, "해당 Half의 세부 constructor가 웹 번들에 포함되지 않았습니다.", { family: "Half", cap });
}

function swappableProof(builder: GraphBuilder, code: string, cap: number, forest?: HalfProofForest): { root: string; replay: boolean } {
  const rows = parseCode(code, cap);
  const orientation = isSwappableRows(rows);
  if (!orientation.accepted) return { root: macroShape(builder, code, "Swappable 분해 실패"), replay: false };
  const oriented = rotateRows(rows, orientation.turns);
  const eastCode = rowsToCode(maskColumns(oriented, [0, 1]));
  const westRotatedCode = rowsToCode(rotateRows(maskColumns(oriented, [2, 3]), 2));
  const east = materializeHalf(builder, eastCode, cap, forest);
  const westRotated = materializeHalf(builder, westRotatedCode, cap, forest);

  const westRotate = builder.operation("ROTATE", "positive", { turns: 2, purpose: "서쪽 Half 원위치" });
  builder.edge(westRotated, westRotate, "입력");
  const westOriginalCode = rowsToCode(rotateRows(parseCode(westRotatedCode, cap), 2));
  const westOriginal = builder.shape(westOriginalCode);
  builder.edge(westRotate, westOriginal, "출력");

  const swap = builder.operation("SWAP", "positive", { selectedOutput: 0, orientationTurns: orientation.turns });
  builder.edge(east, swap, "입력 A");
  builder.edge(westOriginal, swap, "입력 B");
  const outputs = swapShapes(parseCode(eastCode, cap), parseCode(westOriginalCode, cap), cap).map(rowsToCode);
  const orientedCode = rowsToCode(oriented);
  const combined = builder.shape(orientedCode);
  builder.edge(swap, combined, "사용 출력");
  addUnusedOutput(builder, swap, outputs[1], "미사용 출력");

  if (orientation.turns === 0) return { root: combined, replay: outputs[0] === code };
  const undoTurns = (4 - orientation.turns) % 4;
  const rotate = builder.operation("ROTATE", "positive", { turns: undoTurns, purpose: "정규화 회전 복원" });
  builder.edge(combined, rotate, "입력");
  const output = builder.shape(code);
  builder.edge(rotate, output, "출력");
  return { root: output, replay: rowsToCode(rotateRows(parseCode(orientedCode, cap), undoTurns)) === code && outputs[0] === orientedCode };
}

function materializeKnownShape(builder: GraphBuilder, code: string, cap: number, forest?: HalfProofForest, metadata?: ProofNodeData["metadata"]): string {
  if (cap === 5 && forest && Object.prototype.hasOwnProperty.call(forest.roots, code)) return materializeForestNode(builder, forest, forest.roots[code]);
  const rows = parseCode(code, cap);
  if (isSwappableRows(rows).accepted) return swappableProof(builder, code, cap, forest).root;
  if (code === "SSSS") return rawPrimitive(builder);
  if (halfOrientation(rows).accepted) return materializeHalf(builder, code, cap, forest);
  if (isRawInput(rows)) return macroShape(builder, code, "기본 family constructor의 세부 연산 데이터가 없습니다.", metadata);
  return macroShape(builder, code, "인증 하위 도형의 세부 constructor가 제공되지 않았습니다.", metadata);
}

function stackProof(builder: GraphBuilder, target: string, cap: number, witness: StackWitness, forest?: HalfProofForest): { root: string; replay: boolean } {
  let current = materializeKnownShape(builder, witness.bottom, cap, forest, { role: "stack bottom" });
  let replayRows = parseCode(witness.bottom, cap);
  witness.topPieces.forEach((piece, index) => {
    const top = materializeKnownShape(builder, piece, cap, forest, { role: `stack top ${index + 1}` });
    const stack = builder.operation("STACK", "positive", { step: index + 1, splitHeights: witness.splitHeights.join(",") });
    builder.edge(current, stack, "바닥");
    builder.edge(top, stack, "상단");
    replayRows = stackShapes(replayRows, parseCode(piece, cap), cap);
    current = builder.shape(rowsToCode(replayRows));
    builder.edge(stack, current, "출력");
  });
  return { root: current, replay: rowsToCode(replayRows) === target };
}

function clawProof(builder: GraphBuilder, target: string, cap: number, witness: ClawWitness, forest?: HalfProofForest): { root: string; replay: boolean } {
  const predecessor = materializeKnownShape(builder, witness.predecessor, cap, forest, { backend: witness.backend, role: "Claw predecessor" });
  const pin = builder.operation("PIN_PUSH", "positive", { backend: witness.backend });
  builder.edge(predecessor, pin, "입력");
  const tableTarget = witness.targetCode ?? target;
  const pushed = builder.shape(tableTarget);
  builder.edge(pin, pushed, "출력");
  const pinReplay = rowsToCode(pushPin(parseCode(witness.predecessor, cap), cap)) === tableTarget;
  const turns = witness.restoreTurns ?? 0;
  if (!turns) return { root: pushed, replay: pinReplay && tableTarget === target };
  const rotate = builder.operation("ROTATE", "positive", { turns, purpose: "Claw 정규화 회전 복원" });
  builder.edge(pushed, rotate, "입력");
  const root = builder.shape(target);
  builder.edge(rotate, root, "출력");
  return { root, replay: pinReplay && rowsToCode(rotateRows(parseCode(tableTarget, cap), turns)) === target };
}

function pinPushProof(builder: GraphBuilder, target: string, cap: number, witness: PinPushWitness, forest?: HalfProofForest): { root: string; replay: boolean } {
  let currentRoot: string;
  let replay = true;
  if (witness.predecessorStack) {
    const built = stackProof(builder, witness.predecessor, cap, witness.predecessorStack, forest);
    currentRoot = built.root;
    replay = built.replay;
  } else {
    currentRoot = materializeKnownShape(builder, witness.predecessor, cap, forest, {
      backend: witness.backend,
      family: "Rank0 predecessor",
    });
  }

  let replayRows = parseCode(witness.predecessor, cap);
  for (const outputCode of witness.receiptTargets) {
    const pin = builder.operation("PIN_PUSH", "positive", { backend: witness.backend, kind: witness.kind });
    builder.edge(currentRoot, pin, "입력");
    replayRows = pushPin(replayRows, cap);
    const output = builder.shape(outputCode);
    builder.edge(pin, output, "출력");
    replay &&= rowsToCode(replayRows) === outputCode;
    currentRoot = output;
  }
  return { root: currentRoot, replay: replay && witness.receiptTargets.at(-1) === target };
}

function hybridProof(builder: GraphBuilder, target: string, cap: number, witness: HybridWitness, forest?: HalfProofForest): { root: string; replay: boolean } {
  const bottom = witness.bottomClaw
    ? clawProof(builder, witness.bottom, cap, witness.bottomClaw, forest).root
    : materializeKnownShape(builder, witness.bottom, cap, forest, { backend: witness.backend, role: "Hybrid bottom" });
  const top = materializeKnownShape(builder, witness.top, cap, forest, { role: "Hybrid top" });
  const stack = builder.operation("STACK", "positive", { cuts: witness.cuts.join(","), backend: witness.backend });
  builder.edge(bottom, stack, "바닥");
  builder.edge(top, stack, "상단");
  const root = builder.shape(target);
  builder.edge(stack, root, "출력");
  return { root, replay: rowsToCode(stackShapes(parseCode(witness.bottom, cap), parseCode(witness.top, cap), cap)) === target };
}

export function buildNegativeCertificate(result: AnalysisResult): NegativeCertificate {
  const items: NegativeCertificate["items"] = [];
  items.push({ id: "stability", family: "물리 안정성", status: result.facts.stable ? "rejected" : "exhausted", reason: result.facts.stable ? "안정성 통과" : "중력 적용 시 도형이 변함" });
  for (const column of result.columns) items.push({ id: `corner-${column.quadrant}`, family: `Corner ${column.quadrant + 1}사분면`, status: column.accepted ? "rejected" : "exhausted", reason: column.accepted ? "필요조건 통과" : `${column.violatedRule ?? "규칙"} 위반`, details: { pillar: column.pillar || "<empty>" } });
  items.push({ id: "half", family: "Half", status: result.facts.half ? "rejected" : "exhausted", reason: result.facts.half ? "Half 수용" : "수용 orientation 없음" });
  items.push({ id: "swap", family: "Swap", status: result.facts.swappable ? "rejected" : "exhausted", reason: result.facts.swappable ? "Swappable" : "두 축 모두 실패" });
  items.push({ id: "stack", family: "Stack closure", status: result.facts.stackable ? "rejected" : "exhausted", reason: result.facts.stackable ? "witness 존재" : "목표 지향 후보 소진" });
  items.push({
    id: "pp",
    family: "PP 정규형 closure",
    status: result.verdict === "UNKNOWN" ? "open" : "exhausted",
    reason: result.verdict === "UNKNOWN" ? "판정 중단 또는 외부 오류" : "Rank0 frontier와 모든 유일 receipt predecessor를 소진",
    details: { receiptRank: result.facts.receiptRank, chainUpperBound: result.facts.ppChainUpperBound, batchUpperBound: result.facts.ppBatchUpperBound },
  });
  const complete = result.verdict === "IMPOSSIBLE" && result.facts.coverage === "complete";
  return { complete, verifier: complete ? "passed" : "partial", items };
}

function expandedOperationCount(graph: Pick<ProofGraph, "nodes" | "edges" | "rootId">): number {
  const nodeMap = new Map(graph.nodes.map((node) => [node.id, node]));
  const incoming = new Map<string, ProofEdgeData[]>();
  graph.edges.forEach((edge) => incoming.set(edge.target, [...(incoming.get(edge.target) ?? []), edge]));
  let count = 0;
  const visit = (id: string, path: Set<string>) => {
    const node = nodeMap.get(id);
    if (!node || path.has(id)) return;
    if (node.kind === "operation" && node.operation !== "RAW_INPUT") count += 1;
    const next = new Set(path).add(id);
    for (const edge of incoming.get(id) ?? []) visit(edge.source, next);
  };
  visit(graph.rootId, new Set());
  return count;
}

export function buildProofGraph(result: AnalysisResult, forest?: HalfProofForest): ProofGraph {
  const builder = new GraphBuilder();
  let rootId = "";
  let replay: ProofGraph["replayStatus"] = "not-applicable";

  if (result.verdict === "IMPOSSIBLE") {
    const root = builder.shape(result.normalizedCode, "negative");
    const certificate = result.negativeCertificate ?? buildNegativeCertificate(result);
    for (const item of certificate.items) {
      const node = builder.certificate(`${item.family}: ${item.reason}`, item.status === "open" ? "unknown" : "negative", item.details);
      builder.edge(node, root, item.status);
    }
    rootId = root; replay = certificate.complete ? "passed" : "partial";
  } else if (result.verdict === "UNKNOWN") {
    const root = builder.shape(result.normalizedCode, "unknown");
    const rank = builder.certificate(`PP 종료성: σ=${result.facts.receiptRank}, 깊이≤${result.facts.ppChainUpperBound}`, "positive");
    const open = builder.certificate("판정이 정상적으로 완료되지 않았습니다.", "unknown");
    builder.edge(rank, root, "종료 상한"); builder.edge(open, root, "중단 상태", true);
    rootId = root; replay = "partial";
  } else if (result.witness && Array.isArray((result.witness as PinPushWitness).receiptTargets)) {
    // Keep the historical display family (CLAW/CLAW_HYBRID) while building
    // the graph from the actual constructive ZIP receipt-chain witness.
    const built = pinPushProof(builder, result.normalizedCode, result.cap, result.witness as PinPushWitness, forest);
    rootId = built.root; replay = built.replay && !builder.omissions.size ? "passed" : built.replay ? "partial" : "failed";
  } else if (result.shapeType === "BASIC" || result.shapeType === "HALF") {
    rootId = materializeKnownShape(builder, result.normalizedCode, result.cap, forest); replay = builder.omissions.size ? "partial" : "passed";
  } else if (result.shapeType === "SWAPPABLE") {
    const built = swappableProof(builder, result.normalizedCode, result.cap, forest); rootId = built.root; replay = built.replay && !builder.omissions.size ? "passed" : built.replay ? "partial" : "failed";
  } else if (result.shapeType === "STACKABLE" && result.witness) {
    const built = stackProof(builder, result.normalizedCode, result.cap, result.witness as StackWitness, forest); rootId = built.root; replay = built.replay && !builder.omissions.size ? "passed" : built.replay ? "partial" : "failed";
  } else if (result.shapeType === "CLAW" && result.witness) {
    const built = clawProof(builder, result.normalizedCode, result.cap, result.witness as ClawWitness, forest); rootId = built.root; replay = built.replay && !builder.omissions.size ? "passed" : built.replay ? "partial" : "failed";
  } else if (result.shapeType === "PIN_PUSH" && result.witness) {
    const witness = result.witness as PinPushWitness;
    const built = Array.isArray(witness.receiptTargets)
      ? pinPushProof(builder, result.normalizedCode, result.cap, witness, forest)
      : clawProof(builder, result.normalizedCode, result.cap, result.witness as ClawWitness, forest);
    rootId = built.root; replay = built.replay && !builder.omissions.size ? "passed" : built.replay ? "partial" : "failed";
  } else if (result.shapeType === "CLAW_HYBRID" && result.witness) {
    const built = hybridProof(builder, result.normalizedCode, result.cap, result.witness as HybridWitness, forest); rootId = built.root; replay = built.replay && !builder.omissions.size ? "passed" : built.replay ? "partial" : "failed";
  } else {
    rootId = macroShape(builder, result.normalizedCode, "이 family의 세부 proof builder가 없습니다."); replay = "partial";
  }

  const uniqueOperationCount = builder.nodes.filter((node) => node.kind === "operation" && node.operation !== "RAW_INPUT").length;
  const sharedSources = new Map<string, number>();
  builder.edges.forEach((edge) => sharedSources.set(edge.source, (sharedSources.get(edge.source) ?? 0) + 1));
  const base = { nodes: builder.nodes, edges: builder.edges, rootId };
  return {
    ...base,
    operationCount: uniqueOperationCount,
    uniqueOperationCount,
    expandedOperationCount: expandedOperationCount(base),
    sharedNodeCount: [...sharedSources.values()].filter((count) => count > 1).length,
    primitiveComplete: builder.omissions.size === 0,
    omittedReasons: [...builder.omissions],
    replayStatus: replay,
  };
}
