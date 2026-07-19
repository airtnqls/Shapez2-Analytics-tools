from __future__ import annotations

import gzip
import json
import time
from collections import Counter
from pathlib import Path

from backend.service import analyze
from backend.worker_client import worker_client

TARGET = (
    "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:"
    "SuSu----:--Su----:SuSu----:--Su----:cwSu----"
)
CAP = 11


def selected_operation_chain(proof: dict) -> list[dict]:
    nodes = {str(node.get("id")): node for node in proof.get("nodes", [])}
    incoming: dict[str, list[dict]] = {}
    for edge in proof.get("edges", []):
        incoming.setdefault(str(edge.get("target")), []).append(edge)
    selected: set[str] = set()
    pending = [str(proof.get("rootId") or "")]
    while pending:
        node_id = pending.pop()
        if not node_id or node_id in selected:
            continue
        selected.add(node_id)
        pending.extend(str(edge.get("source")) for edge in incoming.get(node_id, []))
    operations = [node for node_id, node in nodes.items() if node_id in selected and node.get("kind") == "operation"]
    return [
        {
            "id": node.get("id"),
            "operation": node.get("operation"),
            "label": node.get("label"),
            "metadata": node.get("metadata"),
        }
        for node in operations
    ]


def metrics(result: dict) -> dict:
    proof = result.get("proof") or {}
    nodes = proof.get("nodes") or []
    edges = proof.get("edges") or []
    operations = [node for node in nodes if node.get("kind") == "operation"]
    operation_histogram = Counter(str(node.get("operation") or node.get("label") or "UNKNOWN") for node in operations)
    shape_nodes = [node for node in nodes if node.get("kind") == "shape"]
    total_code_chars = sum(len(str(node.get("code") or "")) for node in shape_nodes)
    return {
        "verdict": result.get("verdict"),
        "shapeType": result.get("shapeType"),
        "route": result.get("route"),
        "cap": result.get("cap"),
        "timing": result.get("timing"),
        "diagnostics": result.get("diagnostics"),
        "nodes": len(nodes),
        "edges": len(edges),
        "operationNodesIncludingRaw": len(operations),
        "operationCount": proof.get("operationCount"),
        "uniqueOperationCount": proof.get("uniqueOperationCount"),
        "expandedOperationCount": proof.get("expandedOperationCount"),
        "sharedNodeCount": proof.get("sharedNodeCount"),
        "primitiveComplete": proof.get("primitiveComplete"),
        "replayStatus": proof.get("replayStatus"),
        "shapeNodes": len(shape_nodes),
        "materializedCodeChars": total_code_chars,
        "operationHistogram": dict(sorted(operation_histogram.items())),
        "selectedOperations": selected_operation_chain(proof),
    }


def timed(label: str, fn):
    started = time.perf_counter()
    result = fn()
    elapsed = (time.perf_counter() - started) * 1000.0
    return {"label": label, "wallMs": elapsed, "metrics": metrics(result), "result": result}


def main() -> None:
    raw = timed("zip-worker-before-backend-expansion", lambda: worker_client.analyze(TARGET, CAP, "proof"))
    expanded = timed("backend-expanded-and-optimized", lambda: analyze(TARGET, CAP, "proof"))
    report = {
        "schemaVersion": 2,
        "target": TARGET,
        "cap": CAP,
        "runs": [{key: value for key, value in run.items() if key != "result"} for run in (raw, expanded)],
    }
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "FASTPATH_LATEST_BASELINE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    graph_payload = {
        "target": TARGET,
        "cap": CAP,
        "raw": raw["result"],
        "expanded": expanded["result"],
    }
    (reports / "FASTPATH_LATEST_GRAPHS.json.gz").write_bytes(
        gzip.compress(json.dumps(graph_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), compresslevel=9)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
