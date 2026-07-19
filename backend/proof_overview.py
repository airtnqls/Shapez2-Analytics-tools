from __future__ import annotations

from typing import Any

from .corner_half.corner_ir import CornerRule, compile_corner_ir


_RULE_LABELS = {
    CornerRule.C1_TOP_DEPOSIT: "상단 조각 적층",
    CornerRule.C2_ANCHORED_DEPOSIT: "지지 조각 적층",
    CornerRule.C3_GENERATE: "크리스탈 생성",
    CornerRule.C4_SHATTER: "크리스탈 선택 파괴",
    CornerRule.C5_DESCEND: "핀 지지 제거 후 낙하",
    CornerRule.C6_PUSH: "Pin Push",
    CornerRule.C7_EVENT: "Overflow Pin Push 이벤트",
}


def _structural_rows(code: str) -> list[str]:
    rows: list[str] = []
    for layer in (part for part in code.split(":") if part):
        if len(layer) == 4:
            rows.append(layer)
            continue
        if len(layer) != 8:
            return []
        row = []
        for index in range(0, 8, 2):
            cell = layer[index : index + 2]
            if cell == "--":
                row.append("-")
            elif cell[0] == "c":
                row.append("c")
            elif cell[0] == "P":
                row.append("P")
            else:
                row.append("S")
        rows.append("".join(row))
    return rows


def _pillar(rows: list[str], quadrant: int) -> str:
    return "".join(row[quadrant] for row in rows).rstrip("-")


def _adjacent(a: int, b: int) -> bool:
    return (a - b) % 4 in {1, 3}


def _state_code(state: str, support_quadrant: int, target_quadrant: int, cap: int) -> str:
    rows: list[str] = []
    for layer in range(cap):
        row = ["-", "-", "-", "-"]
        row[support_quadrant] = "S"
        if layer < len(state):
            row[target_quadrant] = state[layer]
        rows.append("".join(row))
    while rows and rows[-1] == "----":
        rows.pop()
    return ":".join(rows)


def build_proof_overview(code: str, cap: int, primitive_graph: dict[str, Any]) -> dict[str, Any] | None:
    """Return an O(L)-sized semantic process view for a supported Half family.

    The primitive graph remains the authoritative replay certificate. This view
    only contracts already-verified primitive subgraphs into the deterministic
    Corner IR transitions, matching the sequential process users need to read.
    """
    rows = _structural_rows(code)
    if not rows:
        return None
    cap = max(cap, len(rows))
    padded = rows + ["----"] * (cap - len(rows))
    active = [q for q in range(4) if any(row[q] != "-" for row in padded)]
    if len(active) != 2 or not _adjacent(active[0], active[1]):
        return None

    support_quadrant = next((q for q in active if all(row[q] == "S" for row in padded)), None)
    if support_quadrant is None:
        return None
    target_quadrant = next(q for q in active if q != support_quadrant)
    target_pillar = _pillar(padded, target_quadrant)
    if not target_pillar or set(target_pillar) <= {"S"}:
        return None

    try:
        program = compile_corner_ir(target_pillar, cap)
    except ValueError:
        return None
    if not program.replay_ok or program.final_column != target_pillar:
        return None

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    serial = 0

    def node_id(prefix: str) -> str:
        nonlocal serial
        serial += 1
        return f"overview-{prefix}-{serial}"

    def add_edge(source: str, target: str, label: str) -> None:
        edges.append({"id": node_id("edge"), "source": source, "target": target, "label": label})

    primitive_operations = sum(
        node.get("kind") == "operation" and node.get("operation") != "RAW_INPUT"
        for node in primitive_graph.get("nodes", [])
    )
    certificate_id = node_id("certificate")
    nodes.append({
        "id": certificate_id,
        "kind": "certificate",
        "label": "검증된 원시 제작 증명",
        "status": "positive",
        "metadata": {
            "primitiveOperations": primitive_operations,
            "primitiveNodes": len(primitive_graph.get("nodes", [])),
            "replay": str(primitive_graph.get("replayStatus", "passed")),
        },
    })

    seed_operation = node_id("operation")
    seed_shape = node_id("shape")
    nodes.append({
        "id": seed_operation,
        "kind": "operation",
        "label": "지지 Half 준비",
        "operation": "OVERVIEW_SEED",
        "status": "positive",
        "metadata": {"semantic": True, "primitiveDetailAvailable": True},
    })
    seed_code = _state_code("", support_quadrant, target_quadrant, cap)
    nodes.append({"id": seed_shape, "kind": "shape", "label": seed_code, "code": seed_code, "status": "positive"})
    add_edge(certificate_id, seed_operation, "원시 증명")
    add_edge(seed_operation, seed_shape, "출력")

    previous_shape = seed_shape
    for index, step in enumerate(program.steps, start=1):
        operation_id = node_id("operation")
        output_id = node_id("shape")
        label = _RULE_LABELS.get(step.rule, step.rule.value)
        nodes.append({
            "id": operation_id,
            "kind": "operation",
            "label": label,
            "operation": f"CORNER_{step.rule.value.upper()}",
            "status": "positive",
            "metadata": {
                "semantic": True,
                "step": index,
                "rule": step.rule.value,
                "layer": -1 if step.layer is None else step.layer,
                "helper": step.helper,
                "before": step.before,
                "after": step.after,
                "primitiveDetailAvailable": True,
            },
        })
        output_code = _state_code(step.after, support_quadrant, target_quadrant, cap)
        if index == len(program.steps):
            output_code = ":".join(padded).rstrip(":")
        nodes.append({"id": output_id, "kind": "shape", "label": output_code, "code": output_code, "status": "positive"})
        add_edge(previous_shape, operation_id, "입력")
        add_edge(operation_id, output_id, "출력")
        previous_shape = output_id

    operation_count = 1 + len(program.steps)
    return {
        "nodes": nodes,
        "edges": edges,
        "rootId": previous_shape,
        "operationCount": operation_count,
        "uniqueOperationCount": operation_count,
        "expandedOperationCount": operation_count,
        "sharedNodeCount": 0,
        "primitiveComplete": True,
        "omittedReasons": [],
        "replayStatus": "passed",
        "viewKind": "semantic-overview",
        "detailOperationCount": primitive_operations,
    }
