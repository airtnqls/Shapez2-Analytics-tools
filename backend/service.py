from __future__ import annotations

from typing import Callable

from .proof_expander import expand_certified_macros
from .proof_optimizer import optimize_proof_graph
from .worker_client import worker_client
from .zip_proof_validator import validate_proof_with_zip


def analyze(
    code: str,
    cap: int,
    mode: str = "proof",
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    layer_count = max(1, len([part for part in code.split(":") if part]))
    requested_cap = max(int(cap), layer_count)
    result = worker_client.analyze(code, requested_cap, mode, on_progress=on_progress)

    # A full-height target can have a valid Pin Push predecessor one layer
    # higher than the final shape.  The historical GUI silently clipped that
    # workspace and therefore disagreed with an unconstrained ZIP run.  Retry
    # exactly one construction headroom layer, but only adopt it when the ZIP
    # worker itself changes the verdict to POSSIBLE.
    if (
        layer_count == requested_cap
        and result.get("verdict") == "IMPOSSIBLE"
        and result.get("route") == "pp-closure-exhausted"
    ):
        retry = worker_client.analyze(code, requested_cap + 1, mode, on_progress=on_progress)
        if retry.get("verdict") == "POSSIBLE":
            result = retry
            result.setdefault("diagnostics", {}).setdefault("warnings", []).append(
                f"최종 도형은 {layer_count}층이지만 Pin Push 전구체 재생에 작업층 1개가 필요하여 Cap {requested_cap + 1}을 사용했습니다."
            )

    effective_cap = int(result.get("cap", requested_cap))
    if mode == "proof" and result.get("proof"):
        result["proof"] = expand_certified_macros(result["proof"], effective_cap)
        optimization = optimize_proof_graph(result["proof"])
        checked = validate_proof_with_zip(result["proof"], effective_cap, worker_client)
        # The ZIP worker's recipe was generated before macro expansion.  The
        # canonical proof graph is authoritative for both frontends.
        result.pop("processRecipe", None)
        result.setdefault("diagnostics", {}).setdefault("warnings", [])
        result["diagnostics"]["warnings"] = [
            warning for warning in result["diagnostics"]["warnings"]
            if "constructor" not in warning.lower() and "macro" not in warning.lower()
        ]
        result["diagnostics"]["tablesLoaded"].append(f"ZIP proof operation replay {checked} nodes")
        result["diagnostics"]["tablesLoaded"].append(
            f"DAG optimization removed {optimization.removed_operations} no-op operations / {optimization.removed_nodes} nodes"
        )
    return result


def operate(
    operation: str,
    input_a: str,
    input_b: str = "",
    cap: int = 5,
    paint_color: str = "u",
    crystal_color: str = "u",
) -> dict:
    layer_count = max(
        1,
        len([part for part in input_a.split(":") if part]),
        len([part for part in input_b.split(":") if part]) if input_b else 0,
    )
    cap = max(int(cap), layer_count)
    return worker_client.operate(
        operation, input_a, input_b, cap,
        paint_color=paint_color, crystal_color=crystal_color,
        input_b_present=operation in {"stack", "swap"},
    )
