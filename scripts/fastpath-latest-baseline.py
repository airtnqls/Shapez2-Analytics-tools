from __future__ import annotations

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
    }


def timed(label: str, fn):
    started = time.perf_counter()
    result = fn()
    elapsed = (time.perf_counter() - started) * 1000.0
    return {"label": label, "wallMs": elapsed, "metrics": metrics(result)}


def main() -> None:
    raw = timed("zip-worker-before-backend-expansion", lambda: worker_client.analyze(TARGET, CAP, "proof"))
    expanded = timed("backend-expanded-and-optimized", lambda: analyze(TARGET, CAP, "proof"))
    report = {
        "schemaVersion": 1,
        "target": TARGET,
        "cap": CAP,
        "runs": [raw, expanded],
    }
    out = Path("reports/FASTPATH_LATEST_BASELINE.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
