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

from legacy_corner_recipe import Shape, rotate, structural, cell_distance  # noqa: E402
from search_family_macro import build_helper_pool, from_struct, stable, unique_rotations  # noqa: E402

SPECIAL_PREDECESSOR = "-PcS:SPcc:SPcS:cSc-:--c-"
SPECIAL_CORNER_TARGET = "S---:----:S---:----:c---"
SPECIAL_HALF_TARGET = "SS--:-S--:SS--:-S--:cS--"
CAP = 5


@dataclass(frozen=True)
class Decomposition:
    kind: str
    left_name: str
    left_code: str
    left_proof: tuple[dict, ...]
    right_name: str
    right_code: str
    right_proof: tuple[dict, ...]
    order_or_output: str | int
    result: str


def exact_stack_decompositions(target_code: str, helpers) -> list[Decomposition]:
    target = structural(stable(from_struct(target_code, CAP), CAP))
    results = []
    for i, left in enumerate(helpers):
        a = from_struct(left.code, CAP)
        for right in helpers:
            b = from_struct(right.code, CAP)
            for order, output in (("LR", Shape.stack(a, b)), ("RL", Shape.stack(b, a))):
                code = structural(stable(output, CAP))
                if code == target:
                    results.append(
                        Decomposition(
                            kind="STACK",
                            left_name=left.name,
                            left_code=left.code,
                            left_proof=left.proof,
                            right_name=right.name,
                            right_code=right.code,
                            right_proof=right.proof,
                            order_or_output=order,
                            result=code,
                        )
                    )
                    if len(results) >= 20:
                        return results
    return results


def exact_swap_decompositions(target_code: str, helpers) -> list[Decomposition]:
    target = structural(stable(from_struct(target_code, CAP), CAP))
    results = []
    pair_seen = set()
    for left in helpers:
        a0 = from_struct(left.code, CAP)
        for right in helpers:
            pair = tuple(sorted((left.code, right.code)))
            if pair in pair_seen:
                continue
            pair_seen.add(pair)
            b0 = from_struct(right.code, CAP)
            for lt, a in unique_rotations(a0):
                for rt, b in unique_rotations(b0):
                    for index, output in enumerate(Shape.swap(a, b)):
                        for ft, candidate in unique_rotations(output):
                            code = structural(stable(candidate, CAP))
                            if code == target:
                                results.append(
                                    Decomposition(
                                        kind=f"SWAP_R{lt}_R{rt}_F{ft}",
                                        left_name=left.name,
                                        left_code=left.code,
                                        left_proof=left.proof,
                                        right_name=right.name,
                                        right_code=right.code,
                                        right_proof=right.proof,
                                        order_or_output=index,
                                        result=code,
                                    )
                                )
                                if len(results) >= 20:
                                    return results
    return results


def audit(helper_limit: int = 1400) -> dict:
    Shape.MAX_LAYERS = CAP
    predecessor = from_struct(SPECIAL_PREDECESSOR, CAP)
    pushed = predecessor.push_pin()
    pushed_code = structural(pushed)
    corner_target = structural(stable(from_struct(SPECIAL_CORNER_TARGET, CAP), CAP))
    half_target = structural(stable(from_struct(SPECIAL_HALF_TARGET, CAP), CAP))

    helpers = build_helper_pool(CAP, max_depth=2, max_helpers=helper_limit)
    # The hardcoded predecessor is itself allowed as a target of decomposition,
    # never as an input helper.
    stack_predecessor = exact_stack_decompositions(SPECIAL_PREDECESSOR, helpers)

    # If the hardcoded predecessor replays, expose its pushed result as a
    # certified helper and ask whether one Swap with an ordinary/helper shape
    # produces the full two-column event block.
    pushed_helper_type = type(helpers[0]) if helpers else None
    augmented = list(helpers)
    if pushed_helper_type is not None:
        augmented.append(
            pushed_helper_type(
                name="SPECIAL_STACK_PIN_RESULT",
                code=pushed_code,
                proof=(
                    {"op": "SPECIAL_STACK_DECOMPOSITION", "available": bool(stack_predecessor)},
                    {"op": "PIN_PUSH"},
                ),
                depth=3,
            )
        )
    swap_half = exact_swap_decompositions(SPECIAL_HALF_TARGET, augmented)

    return {
        "schema_version": 1,
        "special_pillar": "S-S-c",
        "legacy_predecessor": structural(predecessor),
        "push_result": pushed_code,
        "corner_target": corner_target,
        "push_corner_distance": cell_distance(pushed_code, corner_target),
        "push_corner_exact": pushed_code == corner_target,
        "half_target": half_target,
        "helper_pool": len(helpers),
        "stack_predecessor_decompositions": [asdict(x) for x in stack_predecessor],
        "swap_half_decompositions": [asdict(x) for x in swap_half],
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
