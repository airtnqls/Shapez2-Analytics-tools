from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProofOptimizationStats:
    nodes_before: int
    nodes_after: int
    operations_before: int
    operations_after: int

    @property
    def removed_nodes(self) -> int:
        return self.nodes_before - self.nodes_after

    @property
    def removed_operations(self) -> int:
        return self.operations_before - self.operations_after


def _indexes(graph: dict[str, Any]):
    by_id = {str(node.get("id")): node for node in graph.get("nodes", [])}
    incoming: dict[str, list[dict[str, Any]]] = {}
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("edges", []):
        incoming.setdefault(str(edge.get("target")), []).append(edge)
        outgoing.setdefault(str(edge.get("source")), []).append(edge)
    return by_id, incoming, outgoing


def _prune_to_root(graph: dict[str, Any]) -> None:
    _, incoming, _ = _indexes(graph)
    keep: set[str] = set()
    pending = [str(graph.get("rootId") or "")]
    while pending:
        node_id = pending.pop()
        if not node_id or node_id in keep:
            continue
        keep.add(node_id)
        pending.extend(str(edge.get("source")) for edge in incoming.get(node_id, []))
    graph["nodes"] = [node for node in graph.get("nodes", []) if str(node.get("id")) in keep]
    graph["edges"] = [
        edge for edge in graph.get("edges", [])
        if str(edge.get("source")) in keep and str(edge.get("target")) in keep
    ]


def _remove_passthrough_operations(graph: dict[str, Any]) -> None:
    """Remove operations whose selected output is byte-for-byte an input.

    Examples are ROTATE(empty), STACK(empty, X) -> X and a SWAP output which
    simply returns an operand. These are valid replays but add no construction
    information and were the largest source of visual noise.
    """
    for _ in range(32):
        by_id, incoming, outgoing = _indexes(graph)
        redirects: dict[str, str] = {}
        producer_edges: set[str] = set()
        for node in graph.get("nodes", []):
            if node.get("kind") != "operation" or node.get("operation") == "RAW_INPUT":
                continue
            operation_id = str(node.get("id"))
            input_ids = [
                str(edge.get("source")) for edge in incoming.get(operation_id, [])
                if by_id.get(str(edge.get("source")), {}).get("kind") == "shape"
            ]
            for edge in outgoing.get(operation_id, []):
                output_id = str(edge.get("target"))
                output = by_id.get(output_id, {})
                if output.get("kind") != "shape":
                    continue
                identical_input = next((
                    input_id for input_id in input_ids
                    if by_id.get(input_id, {}).get("code") == output.get("code")
                ), None)
                if identical_input:
                    redirects[output_id] = identical_input
                    producer_edges.add(str(edge.get("id")))
        if not redirects:
            break

        def resolve(node_id: str) -> str:
            visited: set[str] = set()
            while node_id in redirects and node_id not in visited:
                visited.add(node_id)
                node_id = redirects[node_id]
            return node_id

        edges: list[dict[str, Any]] = []
        seen_edges: set[tuple[str, str, str, bool]] = set()
        for edge in graph.get("edges", []):
            if str(edge.get("id")) in producer_edges:
                continue
            source = resolve(str(edge.get("source")))
            target = resolve(str(edge.get("target")))
            if source == target:
                continue
            key = (source, target, str(edge.get("label") or ""), bool(edge.get("dashed")))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({**edge, "source": source, "target": target})
        graph["rootId"] = resolve(str(graph.get("rootId") or ""))
        graph["edges"] = edges
        graph["nodes"] = [node for node in graph.get("nodes", []) if str(node.get("id")) not in redirects]
        _prune_to_root(graph)


def _share_raw_input(graph: dict[str, Any]) -> None:
    by_id, _, outgoing = _indexes(graph)
    outputs: list[tuple[str, str]] = []
    for node in graph.get("nodes", []):
        if node.get("kind") != "operation" or node.get("operation") != "RAW_INPUT":
            continue
        operation_id = str(node.get("id"))
        shape_id = next((
            str(edge.get("target")) for edge in outgoing.get(operation_id, [])
            if by_id.get(str(edge.get("target")), {}).get("kind") == "shape"
            and by_id.get(str(edge.get("target")), {}).get("code") == "SSSS"
        ), "")
        if shape_id:
            outputs.append((operation_id, shape_id))
    if len(outputs) < 2:
        return
    _, canonical_shape = outputs[0]
    duplicate_shapes = {shape for _, shape in outputs[1:]}
    duplicate_operations = {operation for operation, _ in outputs[1:]}
    new_edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, bool]] = set()
    for edge in graph.get("edges", []):
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source in duplicate_operations or target in duplicate_shapes:
            continue
        if source in duplicate_shapes:
            source = canonical_shape
        key = (source, target, str(edge.get("label") or ""), bool(edge.get("dashed")))
        if key in seen:
            continue
        seen.add(key)
        new_edges.append({**edge, "source": source, "target": target})
    graph["edges"] = new_edges
    graph["nodes"] = [
        node for node in graph.get("nodes", [])
        if str(node.get("id")) not in duplicate_shapes | duplicate_operations
    ]
    if str(graph.get("rootId")) in duplicate_shapes:
        graph["rootId"] = canonical_shape
    _prune_to_root(graph)


def _node_depths(graph: dict[str, Any]) -> dict[str, int]:
    """Return dependency depth for deterministic shallowest-producer choice."""
    by_id, incoming, _ = _indexes(graph)
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        if node_id in visiting:
            # The proof contract is acyclic. Keep the optimizer conservative if
            # malformed external data reaches this pass.
            return len(by_id) + 1
        visiting.add(node_id)
        parents = [str(edge.get("source")) for edge in incoming.get(node_id, [])]
        result = 0 if not parents else 1 + max(depth(parent) for parent in parents)
        visiting.remove(node_id)
        memo[node_id] = result
        return result

    for node_id in by_id:
        depth(node_id)
    return memo


def _merge_exact_duplicate_operations(graph: dict[str, Any]) -> None:
    """Hash-cons equal primitive transitions while preserving the shallow proof.

    Two operations are interchangeable only when their operation name, labelled
    input shape codes and labelled non-ghost output shape codes are identical.
    The shallowest occurrence is kept. Consumers of later duplicate outputs are
    redirected to the kept output, then ordinary root pruning removes the dead
    duplicate branch. The ZIP replay gate after this pass remains authoritative.
    """
    by_id, incoming, outgoing = _indexes(graph)
    depths = _node_depths(graph)
    operation_ids = [
        str(node.get("id")) for node in graph.get("nodes", [])
        if node.get("kind") == "operation" and node.get("operation") != "RAW_INPUT"
    ]
    operation_ids.sort(key=lambda node_id: (depths.get(node_id, 0), node_id))

    canonical_by_key: dict[tuple[Any, ...], tuple[str, list[tuple[str, str, str]]]] = {}
    remove_operations: set[str] = set()
    remove_shapes: set[str] = set()
    redirects: dict[str, str] = {}

    for operation_id in operation_ids:
        node = by_id.get(operation_id, {})
        inputs = sorted(
            (
                str(edge.get("label") or ""),
                str(by_id.get(str(edge.get("source")), {}).get("code") or ""),
            )
            for edge in incoming.get(operation_id, [])
            if by_id.get(str(edge.get("source")), {}).get("kind") == "shape"
        )
        outputs = sorted(
            (
                str(edge.get("label") or ""),
                str(by_id.get(str(edge.get("target")), {}).get("code") or ""),
                str(edge.get("target")),
            )
            for edge in outgoing.get(operation_id, [])
            if by_id.get(str(edge.get("target")), {}).get("kind") == "shape"
            and by_id.get(str(edge.get("target")), {}).get("status") != "ghost"
        )
        if not outputs:
            continue
        key = (
            str(node.get("operation") or ""),
            tuple(inputs),
            tuple((label, code) for label, code, _ in outputs),
        )
        canonical = canonical_by_key.get(key)
        if canonical is None:
            canonical_by_key[key] = (operation_id, outputs)
            continue
        _, canonical_outputs = canonical
        if len(canonical_outputs) != len(outputs):
            continue
        remove_operations.add(operation_id)
        for duplicate, kept in zip(outputs, canonical_outputs):
            duplicate_id = duplicate[2]
            kept_id = kept[2]
            if duplicate_id != kept_id:
                redirects[duplicate_id] = kept_id
                remove_shapes.add(duplicate_id)

    if not redirects and not remove_operations:
        return

    def resolve(node_id: str) -> str:
        visited: set[str] = set()
        while node_id in redirects and node_id not in visited:
            visited.add(node_id)
            node_id = redirects[node_id]
        return node_id

    new_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, bool]] = set()
    for edge in graph.get("edges", []):
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source in remove_operations or target in remove_operations:
            continue
        # Producer edges into removed duplicate output shapes are dead; consumer
        # edges are redirected to the canonical output.
        if target in remove_shapes:
            continue
        source = resolve(source)
        target = resolve(target)
        if source == target:
            continue
        key = (source, target, str(edge.get("label") or ""), bool(edge.get("dashed")))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        new_edges.append({**edge, "source": source, "target": target})

    graph["rootId"] = resolve(str(graph.get("rootId") or ""))
    graph["edges"] = new_edges
    removed = remove_operations | remove_shapes
    graph["nodes"] = [node for node in graph.get("nodes", []) if str(node.get("id")) not in removed]
    _prune_to_root(graph)


def _update_metrics(graph: dict[str, Any]) -> None:
    operation_count = sum(
        node.get("kind") == "operation" and node.get("operation") != "RAW_INPUT"
        for node in graph.get("nodes", [])
    )
    source_counts = Counter(str(edge.get("source")) for edge in graph.get("edges", []))
    graph.update({
        "operationCount": operation_count,
        "uniqueOperationCount": operation_count,
        "expandedOperationCount": operation_count,
        "sharedNodeCount": sum(count > 1 for count in source_counts.values()),
    })


def optimize_proof_graph(graph: dict[str, Any]) -> ProofOptimizationStats:
    nodes_before = len(graph.get("nodes", []))
    operations_before = sum(node.get("kind") == "operation" for node in graph.get("nodes", []))
    _prune_to_root(graph)
    _remove_passthrough_operations(graph)
    _share_raw_input(graph)
    _merge_exact_duplicate_operations(graph)
    _remove_passthrough_operations(graph)
    _merge_exact_duplicate_operations(graph)
    _update_metrics(graph)
    return ProofOptimizationStats(
        nodes_before=nodes_before,
        nodes_after=len(graph.get("nodes", [])),
        operations_before=operations_before,
        operations_after=sum(node.get("kind") == "operation" for node in graph.get("nodes", [])),
    )
