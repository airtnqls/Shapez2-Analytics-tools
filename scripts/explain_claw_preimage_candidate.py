from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import symbolic_frontier_automaton as sfa
from generate_zero_stack_half_pair_candidates import _mask_shape, _rotate_180
from validate_half_pair_ngram_generalization import _abstract_layer


def _layer_at(code: str, index: int) -> str:
    parts = sfa.normalize_code(code).split(":") if sfa.normalize_code(code) else []
    return parts[index] if index < len(parts) else "----"


def _pair_sequence(predecessor: str, layers: int, angle: int) -> tuple[tuple[str, str], ...]:
    rotated = predecessor
    for _ in range(angle):
        rotated = sfa.bitmask_rotate_clockwise(rotated)
    left = _mask_shape(rotated, 0b0011)
    right = _rotate_180(_mask_shape(rotated, 0b1100))
    return tuple((_layer_at(left, index), _layer_at(right, index)) for index in range(layers))


def _abstract_sequence(sequence: tuple[tuple[str, str], ...], mode: str) -> tuple[tuple[str, str], ...]:
    return tuple((_abstract_layer(left, mode), _abstract_layer(right, mode)) for left, right in sequence)


def _zero_stack_trace(code: str, layers: int) -> list[str]:
    trace: list[str] = []
    current = sfa.normalize_code(code)
    seen: set[str] = set()
    while current and current not in seen and sfa.top_single_c_zero_stack_candidate(current):
        seen.add(current)
        trace.append(current)
        parts = current.split(":")
        current = sfa.normalize_code(":".join(parts[1:]))
    if current:
        trace.append(current)
    return trace


def _print_sequence(title: str, sequence: tuple[tuple[str, str], ...]) -> None:
    print(f"{title}:")
    for index, (left, right) in enumerate(sequence):
        print(f"  {index}: left={left} right={right}")


def explain(args: argparse.Namespace) -> int:
    target = sfa.normalize_code(args.target)
    predecessor = sfa.normalize_code(args.predecessor)
    pushed = sfa.bitmask_push_pin(predecessor, args.layers)
    print(f"target={target}")
    print(f"predecessor={predecessor}")
    print(f"layers={args.layers}")
    print(f"pin_push_matches={pushed == target}")
    print(f"pin_push(predecessor)={pushed}")
    print(f"predecessor_subtype={sfa.pp_subtype_candidate(predecessor, args.layers).subtype}")
    print(f"predecessor_stackable={bool(sfa.bitmask_stackability_witnesses(predecessor))}")
    print(f"predecessor_swap={sfa.bitmask_swap_impossibility(predecessor) or 'swappable'}")
    print(f"target_swap={sfa.bitmask_swap_impossibility(target) or 'swappable'}")
    print(f"target_layer_removal={sfa.bitmask_layer_removal_context(target)[:3]}")
    strict, reason = sfa.strict_legacy_verdict_to_symbolic(target)
    print(f"target_strict_legacy={strict}/{reason}")

    for angle in range(2):
        sequence = _pair_sequence(predecessor, args.layers, angle)
        _print_sequence(f"half_pair_sequence_angle_{angle}", sequence)
        _print_sequence(f"abstract_sequence_angle_{angle}_{args.abstract_mode}", _abstract_sequence(sequence, args.abstract_mode))

    print("zero_stack_trace:")
    for index, item in enumerate(_zero_stack_trace(predecessor, args.layers)):
        marker = "seed" if index == len(_zero_stack_trace(predecessor, args.layers)) - 1 else "strip"
        print(f"  {index}:{marker}: {item}")
    seed = sfa.zero_stack_trace_seed(predecessor, args.layers, allow_terminal_crystal=True)
    print(f"zero_stack_trace_seed={seed}")
    if seed is not None:
        current, base = seed
        print("seed_stackability_witnesses:")
        for index, witness in enumerate(sfa.bitmask_stackability_witnesses(current)[: args.max_witnesses]):
            print(
                f"  {index}: base={witness.base} "
                f"delta={witness.stacked_delta} heights={witness.heights}"
            )
        if not sfa.bitmask_stackability_witnesses(current):
            print("  none")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain one claw preimage candidate as half-pair + PP predecessor trace.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--predecessor", required=True)
    parser.add_argument("--layers", type=int, default=6)
    parser.add_argument("--abstract-mode", choices=("classes", "mask_counts", "raw"), default="classes")
    parser.add_argument("--max-witnesses", type=int, default=8)
    return explain(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
