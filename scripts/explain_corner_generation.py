from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
CORNER_RULE_DIR = PROJECT_ROOT / "corner_rule_test"
if str(CORNER_RULE_DIR) not in sys.path:
    sys.path.insert(0, str(CORNER_RULE_DIR))

from shape import Shape


def explain(pillar: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        import main as corner_rule_main
    with contextlib.redirect_stdout(io.StringIO()):
        import symbolic_frontier_automaton as sfa
        from data_operations import corner_1q_shape, cornerize_shape, simplify_shape

    engine = corner_rule_main.RuleEngine(corner_rule_main.DEFAULT_RULE_SPECS)
    code = cornerize_shape(pillar)
    layers = len(code.split(":")) if code else 0
    print(f"pillar={pillar}")
    print(f"cornerized={code}")
    print(f"layers={layers}")
    print(f"corner_dfa_valid={engine.is_valid_string(pillar)}")
    print(f"corner_dfa_matched_rules={','.join(engine.matched_rules(pillar)) or '-'}")
    print(f"physics_stable_as_full_shape={sfa.bitmask_physics_stable(code)}")
    print(f"strict_verdict={sfa.strict_legacy_verdict_to_symbolic(code)}")

    shape = Shape.from_string(code)
    pillars = [repr(shape.get_pillar(i)).strip("'\"") for i in range(4)]
    q1_pillar = pillars[0]
    print(f"q1_pillar={q1_pillar}")
    is_no_cut_pattern = re.search(r"-S-+c", q1_pillar) is not None
    is_cg_corner_pattern = re.search(r"-.*c", q1_pillar) is not None
    is_claw_hybrid_corner_pattern = re.search(r"^S*-?S*c(?:.*c)?(?:S-+)+c", q1_pillar) is not None
    physically_unstable = not sfa.bitmask_physics_stable(code)
    has_crystal = "c" in code

    if is_claw_hybrid_corner_pattern:
        corner_classification = "analyzer.shape_types.claw_hybrid_corner"
    elif is_no_cut_pattern:
        corner_classification = "analyzer.shape_types.claw_corner"
    elif is_cg_corner_pattern:
        corner_classification = "analyzer.shape_types.swap_corner"
    elif physically_unstable or has_crystal:
        corner_classification = "analyzer.shape_types.stack_corner"
    else:
        corner_classification = "analyzer.shape_types.simple_corner"

    with contextlib.redirect_stdout(io.StringIO()):
        from corner_tracer import corner_process

        corner, _q2, _q3, _q4 = shape.quad_cutter()
        raw, operation = corner_process(corner, corner_classification)
    predecessor = sfa.normalize_code(simplify_shape(raw))
    if is_no_cut_pattern:
        replay = sfa.normalize_code(simplify_shape(repr(Shape.from_string(raw).push_pin())))
        replay_operation = "push_pin"
    else:
        replay = sfa.normalize_code(simplify_shape(repr(Shape.from_string(raw).destroy_half())))
        replay_operation = "destroy_half"
    print(f"legacy_corner_operation={operation}")
    print(f"legacy_corner_classification={corner_classification}")
    print(f"legacy_predecessor={predecessor}")
    print(f"predecessor_stable={sfa.bitmask_physics_stable(predecessor)}")
    print(f"predecessor_swap={sfa.bitmask_swap_impossibility(predecessor) or 'swappable'}")
    print(f"legacy_replay_operation={replay_operation}")
    print(f"legacy_replay={replay}")
    replay_q1 = corner_1q_shape(replay) if replay else ""
    print(f"legacy_replay_q1={replay_q1}")
    print(f"legacy_replay_q1_match={replay_q1.replace(':', '') == q1_pillar.replace(':', '') if replay else False}")

    matches: list[str] = []
    for alternative_classification in (
        "analyzer.shape_types.simple_corner",
        "analyzer.shape_types.stack_corner",
        "analyzer.shape_types.swap_corner",
        "analyzer.shape_types.claw_corner",
        "analyzer.shape_types.claw_hybrid_corner",
    ):
        with contextlib.redirect_stdout(io.StringIO()):
            alternative_raw, alternative_operation = corner_process(corner, alternative_classification)
        for replay_name, replay_shape in (
            ("push_pin", Shape.from_string(alternative_raw).push_pin()),
            ("destroy_half", Shape.from_string(alternative_raw).destroy_half()),
        ):
            alternative_replay = sfa.normalize_code(simplify_shape(repr(replay_shape)))
            alternative_q1 = corner_1q_shape(alternative_replay) if alternative_replay else ""
            if alternative_q1.replace(":", "") == q1_pillar.replace(":", ""):
                matches.append(
                    f"{alternative_classification}/{alternative_operation}/{replay_name}"
                    f" predecessor={sfa.normalize_code(simplify_shape(alternative_raw))}"
                )
    print("matching_alternatives:")
    for match in matches:
        print(f"  {match}")
    if not matches:
        print("  -")


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain 1D corner-rule and legacy corner-tracer output.")
    parser.add_argument("pillars", nargs="+")
    args = parser.parse_args()
    for index, pillar in enumerate(args.pillars):
        if index:
            print()
        explain(pillar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
