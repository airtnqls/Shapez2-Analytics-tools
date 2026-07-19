from __future__ import annotations

import contextlib
import io
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_corner_recipe import (  # noqa: E402
    TARGET_LEFT_PILLAR,
    Shape,
    cell_distance,
    rotate,
    structural,
)

with contextlib.redirect_stdout(io.StringIO()):
    from corner_tracer import corner_process  # noqa: E402


@dataclass(frozen=True)
class Audit:
    pillar: str
    classification: str
    classification_reason: str
    selected_operation: str
    predecessor: str
    direct_candidates_checked: int
    best_distance: int
    best_code: str | None
    best_route: list[dict] | None
    hit: dict | None


def unique_shapes(shapes):
    seen = set()
    result = []
    for label, shape in shapes:
        code = structural(shape)
        if code and code not in seen:
            seen.add(code)
            result.append((label, shape))
    return result


def audit() -> Audit:
    cap = len(TARGET_LEFT_PILLAR)
    Shape.MAX_LAYERS = cap
    target = Shape.from_string(":".join(ch + "---" for ch in TARGET_LEFT_PILLAR))
    target.max_layers = cap
    goal = structural(target)

    with contextlib.redirect_stdout(io.StringIO()):
        classification, reason = target.classifier()
        predecessor_code, operation = corner_process(target, classification)
    predecessor = Shape.from_string(predecessor_code)
    predecessor.max_layers = cap

    candidates = []
    # Unary interpretation.
    candidates.append(("PIN_PUSH", predecessor.push_pin(), [{"op": "PIN_PUSH"}]))
    candidates.append(("GENERATOR", predecessor.crystal_generator("y"), [{"op": "CRYSTAL_GENERATOR"}]))

    # Self-swap and cutter-derived pairings cover the legacy convention where
    # one returned scaffold contains both logical Swap inputs.
    pieces = [("WHOLE", predecessor)]
    for turns in range(4):
        rotated = rotate(predecessor, turns)
        for kind, outputs in (
            ("SC", rotated.simple_cutter()),
            ("HC", rotated.half_cutter()),
            ("QC", rotated.quad_cutter()),
        ):
            for index, output in enumerate(outputs):
                pieces.append((f"R{turns}_{kind}{index}", output))
    pieces = unique_shapes(pieces)

    for i, (name_a, a) in enumerate(pieces):
        for name_b, b in pieces[i:]:
            for ta in range(4):
                ra = rotate(a, ta)
                for tb in range(4):
                    rb = rotate(b, tb)
                    out_a, out_b = Shape.swap(ra, rb)
                    for output_index, output in enumerate((out_a, out_b)):
                        for final_turns in range(4):
                            candidate = rotate(output, final_turns)
                            candidates.append(
                                (
                                    "SWAP",
                                    candidate,
                                    [
                                        {
                                            "op": "SWAP",
                                            "input_a": name_a,
                                            "input_b": name_b,
                                            "turns_a": ta,
                                            "turns_b": tb,
                                            "output": output_index,
                                            "final_turns": final_turns,
                                        }
                                    ],
                                )
                            )

    checked = 0
    best_distance = 10**9
    best_code = None
    best_route = None
    hit = None
    seen = set()
    for kind, candidate, route in candidates:
        code = structural(candidate)
        if not code or code in seen:
            continue
        seen.add(code)
        checked += 1
        d = cell_distance(code, goal)
        if d < best_distance:
            best_distance = d
            best_code = code
            best_route = route
        if code == goal:
            hit = {"kind": kind, "code": code, "route": route}
            break

    return Audit(
        pillar=TARGET_LEFT_PILLAR,
        classification=classification,
        classification_reason=reason,
        selected_operation=operation,
        predecessor=structural(predecessor),
        direct_candidates_checked=checked,
        best_distance=best_distance,
        best_code=best_code,
        best_route=best_route,
        hit=hit,
    )


if __name__ == "__main__":
    print(json.dumps(asdict(audit()), ensure_ascii=False, indent=2))
