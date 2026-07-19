from __future__ import annotations

from collections import Counter
from typing import Any

from .corner_half.proof_dag import ProofDagError, ProofNode, shape_raw_proof, verify_proof


class ProofExpansionError(RuntimeError):
    pass


class _GraphWriter:
    def __init__(self, graph: dict[str, Any]) -> None:
        self.graph = graph
        self.nodes: list[dict[str, Any]] = graph["nodes"]
        self.edges: list[dict[str, Any]] = graph["edges"]
        self._serial = 0
        self._memo: dict[int, str] = {}

    def id(self, prefix: str) -> str:
        self._serial += 1
        return f"raw-{prefix}-{self._serial}"

    def edge(self, source: str, target: str, label: str) -> None:
        self.edges.append({"id": self.id("edge"), "source": source, "target": target, "label": label})

    def materialize(self, node: ProofNode, output_id: str | None = None) -> str:
        cached = self._memo.get(id(node))
        if cached:
            if output_id and output_id != cached:
                # The already materialized result is reused directly by redirecting
                # callers; duplicate result widgets are not required for a proof DAG.
                return cached
            return cached

        operation_id = self.id("op")
        metadata: dict[str, Any] = {"primitive": True, "constructor": "Corner/Half all-layer raw proof DAG"}
        if node.parameter is not None:
            metadata["parameter"] = str(node.parameter)
        if node.note:
            metadata["note"] = node.note
        self.nodes.append({
            "id": operation_id,
            "kind": "operation",
            "label": node.operation,
            "operation": node.operation,
            "status": "positive",
            "metadata": metadata,
        })
        child_ids = [self.materialize(child) for child in node.children]
        labels = self._input_labels(node.operation, len(child_ids))
        for child_id, label in zip(child_ids, labels):
            self.edge(child_id, operation_id, label)

        shape_id = output_id or self.id("shape")
        if output_id:
            target = next((item for item in self.nodes if item.get("id") == output_id), None)
            if target is not None:
                target.update({"kind": "shape", "label": node.result or "<빈 도형>", "code": node.result, "status": "positive"})
        else:
            self.nodes.append({"id": shape_id, "kind": "shape", "label": node.result or "<빈 도형>", "code": node.result, "status": "positive"})
        self.edge(operation_id, shape_id, "출력")
        self._memo[id(node)] = shape_id
        return shape_id

    @staticmethod
    def _input_labels(operation: str, count: int) -> list[str]:
        if operation == "STACK":
            return ["바닥", "상단"]
        if operation == "SWAP":
            return ["입력 A", "입력 B"]
        return ["입력" if count == 1 else f"입력 {index + 1}" for index in range(count)]


def expand_certified_macros(graph: dict[str, Any], cap: int) -> dict[str, Any]:
    """Replace every CERTIFIED_MACRO node with a replay-verified raw proof DAG."""
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ProofExpansionError("잘못된 proof graph 형식")

    macro_ids = {
        str(node.get("id"))
        for node in nodes
        if node.get("kind") == "operation" and node.get("operation") == "CERTIFIED_MACRO"
    }
    if not macro_ids:
        graph["primitiveComplete"] = not graph.get("omittedReasons")
        return graph

    output_for_macro: dict[str, str] = {}
    for edge in edges:
        if str(edge.get("source")) in macro_ids:
            output_for_macro[str(edge["source"])] = str(edge["target"])

    node_by_id = {str(node.get("id")): node for node in nodes}
    certificate_ids = {
        str(edge.get("source"))
        for edge in edges
        if str(edge.get("target")) in macro_ids and node_by_id.get(str(edge.get("source")), {}).get("kind") == "certificate"
    }
    remove_ids = macro_ids | certificate_ids
    nodes[:] = [node for node in nodes if str(node.get("id")) not in remove_ids]
    edges[:] = [
        edge for edge in edges
        if str(edge.get("source")) not in remove_ids and str(edge.get("target")) not in remove_ids
    ]

    writer = _GraphWriter(graph)
    failures: list[str] = []
    for macro_id, output_id in output_for_macro.items():
        output = node_by_id.get(output_id, {})
        code = str(output.get("code", ""))
        try:
            root = shape_raw_proof(code, cap)
            audit = verify_proof(root)
            if not audit.replay_ok or audit.result != code:
                raise ProofExpansionError(f"replay mismatch: {audit.result!r} != {code!r}")
            # Keep sharing inside each constructor DAG. Separate macro sites
            # retain their existing output node IDs so downstream edges and
            # the selected root never become orphaned.
            writer._memo.clear()
            writer.materialize(root, output_id)
        except (ProofDagError, ProofExpansionError, ValueError) as exc:
            failures.append(f"{code or '<빈 도형>'}: {exc}")

    if failures:
        raise ProofExpansionError("constructor 완전 전개 실패: " + " | ".join(failures))

    operation_count = sum(
        node.get("kind") == "operation" and node.get("operation") != "RAW_INPUT"
        for node in nodes
    )
    source_counts = Counter(str(edge.get("source")) for edge in edges)
    graph.update({
        "operationCount": operation_count,
        "uniqueOperationCount": operation_count,
        "expandedOperationCount": operation_count,
        "sharedNodeCount": sum(count > 1 for count in source_counts.values()),
        "primitiveComplete": True,
        "omittedReasons": [],
        "replayStatus": "passed",
    })
    return graph
