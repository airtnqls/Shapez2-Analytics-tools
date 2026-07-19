import type {
  ProcessRecipe,
  ProcessRecipePort,
  ProcessRecipeStep,
  ProofEdgeData,
  ProofGraph,
  ProofNodeData,
} from "./types";

function addToIndex(index: Map<string, ProofEdgeData[]>, key: string, edge: ProofEdgeData): void {
  index.set(key, [...(index.get(key) ?? []), edge]);
}

function portFor(node: ProofNodeData, edge: ProofEdgeData, selected: boolean): ProcessRecipePort {
  return {
    nodeId: node.id,
    code: node.code,
    label: node.label,
    role: edge.label,
    selected,
    ghost: node.status === "ghost",
  };
}

/** Build a stable operation recipe from the proof DAG's parent backpointers. */
export function buildProcessRecipe(graph: ProofGraph): ProcessRecipe {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const incoming = new Map<string, ProofEdgeData[]>();
  const outgoing = new Map<string, ProofEdgeData[]>();
  for (const edge of graph.edges) {
    addToIndex(incoming, edge.target, edge);
    addToIndex(outgoing, edge.source, edge);
  }

  // Only nodes which can reach the requested root belong to the selected
  // construction. Ghost outputs remain visible as unselected operation ports.
  const selectedPath = new Set<string>();
  const visitIncoming = (id: string): void => {
    if (selectedPath.has(id)) return;
    selectedPath.add(id);
    for (const edge of incoming.get(id) ?? []) visitIncoming(edge.source);
  };
  visitIncoming(graph.rootId);

  const operationNodes = graph.nodes.filter(
    (node) => node.kind === "operation" && selectedPath.has(node.id),
  );
  const operationIds = new Set(operationNodes.map((node) => node.id));
  const producerByShape = new Map<string, string>();
  for (const operation of operationNodes) {
    for (const edge of outgoing.get(operation.id) ?? []) {
      const output = nodeById.get(edge.target);
      if (output?.kind === "shape") producerByShape.set(output.id, operation.id);
    }
  }

  const dependencySets = new Map<string, Set<string>>();
  const dependents = new Map<string, Set<string>>();
  for (const operation of operationNodes) {
    const deps = new Set<string>();
    for (const edge of incoming.get(operation.id) ?? []) {
      const producer = producerByShape.get(edge.source);
      if (producer && producer !== operation.id && operationIds.has(producer)) deps.add(producer);
    }
    dependencySets.set(operation.id, deps);
    for (const dependency of deps) {
      dependents.set(dependency, new Set([...(dependents.get(dependency) ?? []), operation.id]));
    }
  }

  // Kahn ordering is deterministic by original node order when independent.
  const remaining = new Map([...dependencySets].map(([id, deps]) => [id, new Set(deps)]));
  const sourceOrder = new Map(operationNodes.map((node, index) => [node.id, index]));
  const depth = new Map<string, number>();
  const ready = operationNodes.filter((node) => !(remaining.get(node.id)?.size));
  const ordered: ProofNodeData[] = [];
  const sortReady = (): void => {
    ready.sort((a, b) => (sourceOrder.get(a.id) ?? 0) - (sourceOrder.get(b.id) ?? 0));
  };
  sortReady();
  while (ready.length) {
    const operation = ready.shift()!;
    ordered.push(operation);
    depth.set(operation.id, Math.max(
      0,
      ...[...(dependencySets.get(operation.id) ?? [])].map((id) => (depth.get(id) ?? 0) + 1),
    ));
    for (const dependent of dependents.get(operation.id) ?? []) {
      const deps = remaining.get(dependent);
      if (!deps) continue;
      deps.delete(operation.id);
      if (!deps.size) {
        const node = nodeById.get(dependent);
        if (node) ready.push(node);
      }
    }
    sortReady();
  }

  const warnings = [...graph.omittedReasons];
  if (ordered.length !== operationNodes.length) {
    warnings.push("제작 공정 의존성에 순환 또는 끊어진 backpointer가 있습니다.");
    const emitted = new Set(ordered.map((node) => node.id));
    ordered.push(...operationNodes.filter((node) => !emitted.has(node.id)));
  }

  const stepIdByOperation = new Map(ordered.map((node, index) => [node.id, `step-${index + 1}`]));
  const steps: ProcessRecipeStep[] = ordered.map((operation, index) => {
    const inputEdges = (incoming.get(operation.id) ?? []).filter(
      (edge) => nodeById.get(edge.source)?.kind === "shape",
    );
    const outputEdges = (outgoing.get(operation.id) ?? []).filter(
      (edge) => nodeById.get(edge.target)?.kind === "shape",
    );
    const dependencyStepIds = new Set<string>();
    for (const edge of inputEdges) {
      const producer = producerByShape.get(edge.source);
      if (producer && stepIdByOperation.has(producer)) dependencyStepIds.add(stepIdByOperation.get(producer)!);
    }
    const inputs = inputEdges.flatMap((edge) => {
      const node = nodeById.get(edge.source);
      return node ? [portFor(node, edge, selectedPath.has(node.id))] : [];
    });
    const outputs = outputEdges.flatMap((edge) => {
      const node = nodeById.get(edge.target);
      return node ? [portFor(node, edge, selectedPath.has(node.id))] : [];
    });
    return {
      id: stepIdByOperation.get(operation.id)!,
      index: index + 1,
      operationNodeId: operation.id,
      operation: operation.operation ?? "UNKNOWN",
      label: operation.label,
      primitive: operation.operation === "RAW_INPUT",
      depth: depth.get(operation.id) ?? 0,
      dependencyStepIds: [...dependencyStepIds],
      inputs,
      outputs,
      selectedOutputNodeIds: outputs.filter((output) => output.selected && !output.ghost).map((output) => output.nodeId),
      metadata: operation.metadata,
    };
  });

  const consumerCounts = new Map<string, number>();
  for (const edge of graph.edges) {
    if (nodeById.get(edge.source)?.kind === "shape" && nodeById.get(edge.target)?.kind === "operation") {
      consumerCounts.set(edge.source, (consumerCounts.get(edge.source) ?? 0) + 1);
    }
  }
  const root = nodeById.get(graph.rootId);
  return {
    version: 1,
    finalShapeNodeId: graph.rootId,
    finalCode: root?.code,
    steps,
    sharedShapeNodeIds: [...consumerCounts.entries()].filter(([, count]) => count > 1).map(([id]) => id),
    primitiveComplete: graph.primitiveComplete,
    replayStatus: graph.replayStatus,
    warnings,
  };
}
