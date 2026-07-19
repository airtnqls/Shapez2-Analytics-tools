import type { OperationName, OperationResult, ProofGraph, ProofNodeData } from "./types";
import { solverClient } from "./solver-client";

export async function runZipOperation(input: {
  operation: OperationName;
  inputA: string;
  inputB?: string;
  cap: number;
  paintColor?: string;
  crystalColor?: string;
}): Promise<OperationResult> {
  return solverClient.operate(input);
}

/** ZIP proof backpointers are the sole reverse-operation source. */
export async function traceZipInputs(code: string, cap: number): Promise<{ operation: string; inputs: ProofNodeData[]; graph: ProofGraph }> {
  const result = await solverClient.analyze(code, cap, "proof").promise;
  const graph = result.proof;
  if (!graph) throw new Error("ZIP client worker가 proof DAG를 반환하지 않았습니다.");
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const rootProducer = graph.edges
    .filter((edge) => edge.target === graph.rootId)
    .map((edge) => byId.get(edge.source))
    .find((node) => node?.kind === "operation");
  if (!rootProducer) throw new Error("목표 도형의 직전 ZIP 연산을 찾지 못했습니다.");
  const inputs = graph.edges
    .filter((edge) => edge.target === rootProducer.id)
    .map((edge) => byId.get(edge.source))
    .filter((node): node is ProofNodeData => node?.kind === "shape");
  return { operation: rootProducer.operation ?? rootProducer.label, inputs, graph };
}
