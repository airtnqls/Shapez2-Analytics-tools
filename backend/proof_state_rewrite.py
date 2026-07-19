from __future__ import annotations

from collections import defaultdict
from typing import Any


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


def _depths(graph: dict[str, Any]) -> dict[str, int]:
    by_id, incoming, _ = _indexes(graph)
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def visit(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        if node_id in visiting:
            return len(by_id) + 1
        visiting.add(node_id)
        parents = [str(edge.get("source")) for edge in incoming.get(node_id, [])]
        value = 0 if not parents else 1 + max(visit(parent) for parent in parents)
        visiting.remove(node_id)
        memo[node_id] = value
        return value

    for node_id in by_id:
        visit(node_id)
    return memo


def _ancestors(node_id: str, incoming: dict[str, list[dict[str, Any]]]) -> set[str]:
    found: set[str] = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        for edge in incoming.get(current, []):
            source = str(edge.get("source"))
            if source not in found:
                found.add(source)
                pending.append(source)
    return found


def remove_redundant_state_returns(graph: dict[str, Any]) -> int:
    """Bypass operation chains that return to an identical prior shape state.

    The proof graph is a state-transition DAG. If a later positive shape node has
    exactly the same code as an ancestor shape node, every operation between the
    two states is observationally redundant for the selected construction. The
    later consumers may use the earlier state directly. Only ancestor matches are
    used, so the rewrite cannot introduce a dependency cycle. The independent ZIP
    replay validator remains the final acceptance gate.
    """
    total_removed = 0
    for _ in range(64):
        by_id, incoming, _ = _indexes(graph)
        depths = _depths(graph)
        shapes_by_code: dict[str, list[str]] = defaultdict(list)
        for node_id, node in by_id.items():
            if node.get("kind") != "shape" or node.get("status") in {"ghost", "negative", "unknown"}:
                continue
            code = str(node.get("code") or "")
            shapes_by_code[code].append(node_id)

        redirect_later = ""
        redirect_earlier = ""
        for code, shape_ids in shapes_by_code.items():
            if len(shape_ids) < 2:
                continue
            ordered = sorted(shape_ids, key=lambda item: (depths.get(item, 0), item))
            for later in ordered[1:]:
                ancestors = _ancestors(later, incoming)
                earlier = next((candidate for candidate in ordered if candidate != later and candidate in ancestors), None)
                if earlier is not None:
                    redirect_later = later
                    redirect_earlier = earlier
                    break
            if redirect_later:
                break

        if not redirect_later:
            break

        new_edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, bool]] = set()
        for edge in graph.get("edges", []):
            source = str(edge.get("source"))
            target = str(edge.get("target"))
            # Drop the producer edge(s) of the repeated state. Its consumers are
            # rewired to the already-proved ancestor state.
            if target == redirect_later:
                continue
            if source == redirect_later:
                source = redirect_earlier
            if source == target:
                continue
            key = (source, target, str(edge.get("label") or ""), bool(edge.get("dashed")))
            if key in seen:
                continue
            seen.add(key)
            new_edges.append({**edge, "source": source, "target": target})
        if str(graph.get("rootId") or "") == redirect_later:
            graph["rootId"] = redirect_earlier
        graph["edges"] = new_edges
        graph["nodes"] = [node for node in graph.get("nodes", []) if str(node.get("id")) != redirect_later]
        before = len(graph["nodes"])
        _prune_to_root(graph)
        total_removed += 1 + max(0, before - len(graph["nodes"]))

    return total_removed
