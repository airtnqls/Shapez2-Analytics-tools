from __future__ import annotations

"""Generate the exact minimized width-four support DFA used by Stack closure.

The source transducer is the already-validated Claw-Hybrid support behavior in
``stack_product.py``.  We enumerate every reachable concrete boundary support
configuration, deterministically minimize its complete 256-symbol DFA, and
compute the exact residual-language inclusion preorder used by the optimized
existential antichain.
"""

from collections import deque, defaultdict
from itertools import product
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack_pp.rows import RowInfo
from stack_pp.stack_product import (
    _GLOBAL_BEHAVIORS,
    _advance_behavior_id,
    _support_behavior_accepts,
)

OUT = ROOT / "stack_pp" / "support_quotient.py"
REPORT = ROOT / "reports" / "support_quotient_generation.json"


def all_rows() -> tuple[RowInfo, ...]:
    return tuple(RowInfo.from_cells(cells) for cells in product(range(4), repeat=4))


def build_raw(rows: tuple[RowInfo, ...]):
    states: list[tuple[int, int, int]] = []
    ids: dict[tuple[int, int, int], int] = {}
    transitions: list[tuple[int, ...] | None] = []

    def intern(state: tuple[int, int, int]) -> tuple[int, bool]:
        found = ids.get(state)
        if found is not None:
            return found, False
        found = len(states)
        ids[state] = found
        states.append(state)
        transitions.append(None)
        return found, True

    queue: deque[int] = deque()
    start_raw: list[int] = []
    for row in rows:
        behavior = _advance_behavior_id(
            0,
            0,
            0,
            row.occupied,
            row.crystal,
            row.pin,
            True,
        )
        state_id, fresh = intern((row.occupied, row.crystal, behavior))
        start_raw.append(state_id)
        if fresh:
            queue.append(state_id)

    while queue:
        state_id = queue.popleft()
        occupied, crystal, behavior = states[state_id]
        row_targets: list[int] = []
        for row in rows:
            next_behavior = _advance_behavior_id(
                behavior,
                occupied,
                crystal,
                row.occupied,
                row.crystal,
                row.pin,
                False,
            )
            target_id, fresh = intern(
                (row.occupied, row.crystal, next_behavior)
            )
            row_targets.append(target_id)
            if fresh:
                queue.append(target_id)
        transitions[state_id] = tuple(row_targets)

    return states, tuple(t for t in transitions if t is not None), tuple(start_raw)


def minimize(states, transitions, start_raw):
    partition = [
        int(_support_behavior_accepts(_GLOBAL_BEHAVIORS[behavior], occupied))
        for occupied, _crystal, behavior in states
    ]
    iterations = 0
    while True:
        iterations += 1
        signature_to_block: dict[tuple, int] = {}
        refined: list[int] = []
        for state_id in range(len(states)):
            signature = (
                partition[state_id],
                tuple(partition[target] for target in transitions[state_id]),
            )
            refined.append(
                signature_to_block.setdefault(signature, len(signature_to_block))
            )
        if refined == partition:
            break
        partition = refined

    block_count = max(partition) + 1
    representative: list[int | None] = [None] * block_count
    for state_id, block in enumerate(partition):
        if representative[block] is None:
            representative[block] = state_id

    quotient_transitions = tuple(
        bytes(partition[target] for target in transitions[rep])
        for rep in representative
        if rep is not None
    )
    quotient_start = bytes(partition[state_id] for state_id in start_raw)
    accepting = tuple(
        bool(
            _support_behavior_accepts(
                _GLOBAL_BEHAVIORS[states[rep][2]], states[rep][0]
            )
        )
        for rep in representative
        if rep is not None
    )
    return (
        partition,
        tuple(int(rep) for rep in representative if rep is not None),
        quotient_transitions,
        quotient_start,
        accepting,
        iterations,
    )


def language_inclusion(transitions: tuple[bytes, ...], accepting: tuple[bool, ...]):
    """Greatest simulation = exact residual-language inclusion for a DFA.

    ``p`` includes ``q`` iff every suffix accepted from q is accepted from p.
    For a deterministic complete automaton this is the greatest relation R with
    accepting(q) => accepting(p) and (delta(p,a), delta(q,a)) in R for every a.
    """

    n = len(transitions)
    all_bits = (1 << n) - 1
    relation = [all_bits] * n
    rejecting_mask = sum(1 << q for q in range(n) if not accepting[q])
    for p in range(n):
        if not accepting[p]:
            relation[p] = rejecting_mask

    iterations = 0
    while True:
        iterations += 1
        changed = False
        for p in range(n):
            old = relation[p]
            new = old
            candidates = old
            while candidates:
                bit = candidates & -candidates
                q = bit.bit_length() - 1
                candidates -= bit
                for row_id in range(256):
                    p2 = transitions[p][row_id]
                    q2 = transitions[q][row_id]
                    if not (relation[p2] >> q2) & 1:
                        new &= ~bit
                        break
            if new != old:
                relation[p] = new
                changed = True
        if not changed:
            break
    return tuple(relation), iterations


def bytes_literal(value: bytes) -> str:
    return "bytes.fromhex(" + repr(value.hex()) + ")"


def main() -> int:
    rows = all_rows()
    states, raw_transitions, start_raw = build_raw(rows)
    (
        partition,
        representatives,
        transitions,
        start,
        accepting,
        minimize_iterations,
    ) = minimize(states, raw_transitions, start_raw)
    inclusion, inclusion_iterations = language_inclusion(transitions, accepting)

    action_classes: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for row_id in range(256):
        signature = (start[row_id],) + tuple(
            transitions[state][row_id] for state in range(len(transitions))
        )
        action_classes[signature].append(row_id)

    source = [
        '"""Generated exact width-four support-language quotient.\n\n',
        "Do not edit by hand; regenerate with tools/generate_support_quotient.py.\n",
        '"""\n\n',
        f"RAW_SUPPORT_STATES = {len(states)}\n",
        f"SUPPORT_STATE_COUNT = {len(transitions)}\n",
        f"SUPPORT_ROW_ACTION_CLASSES = {len(action_classes)}\n",
        "SUPPORT_START = " + bytes_literal(start) + "\n",
        "SUPPORT_ACCEPTING = " + repr(accepting) + "\n",
        "SUPPORT_TRANSITIONS = (\n",
    ]
    source.extend(f"    {bytes_literal(row)},\n" for row in transitions)
    source.append(")\n")
    source.append("SUPPORT_INCLUDES = (\n")
    source.extend(f"    {mask},\n" for mask in inclusion)
    source.append(")\n")
    OUT.write_text("".join(source), encoding="utf-8")

    report = {
        "raw_reachable_support_states": len(states),
        "minimized_support_states": len(transitions),
        "minimize_iterations": minimize_iterations,
        "language_inclusion_pairs": sum(mask.bit_count() for mask in inclusion),
        "language_inclusion_iterations": inclusion_iterations,
        "support_row_action_classes": len(action_classes),
        "raw_behavior_ids_created": len(_GLOBAL_BEHAVIORS),
        "generated_file": str(OUT.relative_to(ROOT)),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
