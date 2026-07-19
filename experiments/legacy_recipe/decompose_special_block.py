from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from legacy_corner_recipe import Shape, structural, cell_distance
from search_family_macro import build_helper_pool, from_struct, stable, unique_rotations

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


def top_skeleton(code: str) -> str:
    """Stack removes every crystal from the top input before physics.

    Helpers with the same post-removal structure are therefore equivalent as
    top operands and must be evaluated once.
    """
    return ":".join("".join("-" if ch == "c" else ch for ch in row) for row in code.split(":"))


def exact_stack_decompositions(target_code: str, helpers) -> tuple[list[Decomposition], dict[str, int]]:
    target = structural(stable(from_struct(target_code, CAP), CAP))
    results: list[Decomposition] = []

    unique_tops = {}
    for helper in helpers:
        unique_tops.setdefault(top_skeleton(helper.code), helper)
    top_helpers = list(unique_tops.values())

    checked = 0
    output_cache = set()
    for bottom in helpers:
        bottom_shape = from_struct(bottom.code, CAP)
        for top in top_helpers:
            checked += 1
            output = Shape.stack(bottom_shape, from_struct(top.code, CAP))
            code = structural(stable(output, CAP))
            cache_key = (bottom.code, top_skeleton(top.code), code)
            if cache_key in output_cache:
                continue
            output_cache.add(cache_key)
            if code == target:
                results.append(
                    Decomposition(
                        kind="STACK",
                        left_name=bottom.name,
                        left_code=bottom.code,
                        left_proof=bottom.proof,
                        right_name=top.name,
                        right_code=top.code,
                        right_proof=top.proof,
                        order_or_output="BOTTOM_TOP",
                        result=code,
                    )
                )
                if len(results) >= 20:
                    return results, {
                        "bottom_helpers": len(helpers),
                        "unique_top_skeletons": len(top_helpers),
                        "checked": checked,
                    }

    # Also check the reverse order explicitly. The outer loop again represents
    # the actual bottom; this is not a symmetric duplicate.
    for bottom in top_helpers:
        bottom_shape = from_struct(bottom.code, CAP)
        for top in helpers:
            checked += 1
            output = Shape.stack(bottom_shape, from_struct(top.code, CAP))
            code = structural(stable(output, CAP))
            cache_key = (bottom.code, top_skeleton(top.code), code)
            if cache_key in output_cache:
                continue
            output_cache.add(cache_key)
            if code == target:
                results.append(
                    Decomposition(
                        kind="STACK",
                        left_name=bottom.name,
                        left_code=bottom.code,
                        left_proof=bottom.proof,
                        right_name=top.name,
                        right_code=top.code,
                        right_proof=top.proof,
                        order_or_output="BOTTOM_TOP",
                        result=code,
                    )
                )
                if len(results) >= 20:
                    break
        if len(results) >= 20:
            break

    return results, {
        "bottom_helpers": len(helpers),
        "unique_top_skeletons": len(top_helpers),
        "checked": checked,
    }


def exact_special_swap_to_half(pushed_code: str, helpers) -> tuple[list[Decomposition], int]:
    """Keep one Swap input fixed to the certified special Push result."""
    target = structural(stable(from_struct(SPECIAL_HALF_TARGET, CAP), CAP))
    special = from_struct(pushed_code, CAP)
    results: list[Decomposition] = []
    checked = 0
    seen_invocations = set()
    seen_outputs = set()

    for helper in helpers:
        helper_shape = from_struct(helper.code, CAP)
        for special_turns, a in unique_rotations(special):
            for helper_turns, b in unique_rotations(helper_shape):
                invocation = (structural(a), structural(b))
                if invocation in seen_invocations:
                    continue
                seen_invocations.add(invocation)
                checked += 1
                for index, output in enumerate(Shape.swap(a, b)):
                    for final_turns, candidate in unique_rotations(output):
                        code = structural(stable(candidate, CAP))
                        if code in seen_outputs:
                            continue
                        seen_outputs.add(code)
                        if code == target:
                            results.append(
                                Decomposition(
                                    kind=f"SWAP_SPECIAL_R{special_turns}_HELPER_R{helper_turns}_F{final_turns}",
                                    left_name="SPECIAL_STACK_PIN_RESULT",
                                    left_code=pushed_code,
                                    left_proof=(
                                        {"op": "SPECIAL_STACK_DECOMPOSITION"},
                                        {"op": "PIN_PUSH"},
                                    ),
                                    right_name=helper.name,
                                    right_code=helper.code,
                                    right_proof=helper.proof,
                                    order_or_output=index,
                                    result=code,
                                )
                            )
                            if len(results) >= 20:
                                return results, checked
    return results, checked


def audit(helper_limit: int = 1400) -> dict:
    Shape.MAX_LAYERS = CAP
    predecessor = from_struct(SPECIAL_PREDECESSOR, CAP)
    pushed = predecessor.push_pin()
    pushed_code = structural(pushed)
    corner_target = structural(stable(from_struct(SPECIAL_CORNER_TARGET, CAP), CAP))
    half_target = structural(stable(from_struct(SPECIAL_HALF_TARGET, CAP), CAP))

    helpers = build_helper_pool(CAP, max_depth=2, max_helpers=helper_limit)
    stack_predecessor, stack_metrics = exact_stack_decompositions(SPECIAL_PREDECESSOR, helpers)
    swap_half, swap_checked = exact_special_swap_to_half(pushed_code, helpers)

    return {
        "schema_version": 2,
        "special_pillar": "S-S-c",
        "legacy_predecessor": structural(predecessor),
        "push_result": pushed_code,
        "corner_target": corner_target,
        "push_corner_distance": cell_distance(pushed_code, corner_target),
        "push_corner_exact": pushed_code == corner_target,
        "half_target": half_target,
        "helper_pool": len(helpers),
        "stack_metrics": stack_metrics,
        "special_swap_checked": swap_checked,
        "stack_predecessor_decompositions": [asdict(x) for x in stack_predecessor],
        "swap_half_decompositions": [asdict(x) for x in swap_half],
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
