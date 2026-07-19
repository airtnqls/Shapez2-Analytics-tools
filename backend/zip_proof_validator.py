from __future__ import annotations

from typing import Any

from .worker_client import WorkerClient


class ZipProofValidationError(RuntimeError):
    pass


def _turn_operation(metadata: dict[str, Any]) -> str | None:
    raw = metadata.get("turns", metadata.get("parameter", 0))
    try:
        turns = int(raw) % 4
    except (TypeError, ValueError):
        turns = 0
    return {0: None, 1: "rotate_cw", 2: "rotate_180", 3: "rotate_ccw"}[turns]


def validate_proof_with_zip(graph: dict[str, Any], cap: int, worker: WorkerClient) -> int:
    """Replay every displayed operation with the supplied ZIP worker.

    The Python constructor may only propose visualization nodes.  A node is
    accepted into either GUI when the ZIP physics kernel independently returns
    its displayed output.  This keeps solver and operation semantics singular.
    """
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    by_id = {str(node.get("id")): node for node in nodes}
    incoming: dict[str, list[dict[str, Any]]] = {}
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        incoming.setdefault(str(edge.get("target")), []).append(edge)
        outgoing.setdefault(str(edge.get("source")), []).append(edge)

    operation_map = {
        "CUT": "half_cutter",
        "SWAP": "swap",
        "STACK": "stack",
        "GENERATE": "crystal_generator",
        "PIN_PUSH": "push_pin",
    }
    checked = 0
    for node in nodes:
        if node.get("kind") != "operation":
            continue
        operation_id = str(node.get("id"))
        operation = str(node.get("operation") or "")
        input_codes = [
            str(by_id.get(str(edge.get("source")), {}).get("code") or "")
            for edge in incoming.get(operation_id, [])
            if by_id.get(str(edge.get("source")), {}).get("kind") == "shape"
        ]
        output_codes = [
            str(by_id.get(str(edge.get("target")), {}).get("code") or "")
            for edge in outgoing.get(operation_id, [])
            if by_id.get(str(edge.get("target")), {}).get("kind") == "shape"
        ]
        if operation == "RAW_INPUT":
            if any(code != "SSSS" for code in output_codes):
                raise ZipProofValidationError(f"RAW_INPUT mismatch at {operation_id}: {output_codes}")
            checked += 1
            continue
        if operation == "CERTIFIED_MACRO":
            raise ZipProofValidationError(f"unexpanded CERTIFIED_MACRO at {operation_id}")
        if not input_codes or not output_codes:
            raise ZipProofValidationError(f"disconnected {operation} at {operation_id}")

        worker_operation = _turn_operation(dict(node.get("metadata") or {})) if operation == "ROTATE" else operation_map.get(operation)
        if worker_operation is None:
            actual_outputs = [input_codes[0]]
        elif worker_operation:
            response = worker.operate(
                worker_operation,
                input_codes[0],
                input_codes[1] if len(input_codes) > 1 else "",
                cap,
                input_b_present=len(input_codes) > 1,
            )
            actual_outputs = [str(value) for value in response.get("outputs", [])]
        else:
            raise ZipProofValidationError(f"unsupported proof operation {operation!r}")
        missing = [code for code in output_codes if code not in actual_outputs]
        if missing:
            raise ZipProofValidationError(
                f"ZIP replay mismatch {operation} at {operation_id}: expected {missing}, got {actual_outputs}"
            )
        checked += 1
    return checked
