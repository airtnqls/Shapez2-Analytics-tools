from __future__ import annotations

from itertools import product

from corner_half.corner_dfa import is_craftable_column
from corner_half.half_automaton import (
    HALF_DFA, ROW_ALPHABET, audit_frozen_table, audit_minimality,
    audit_stability_minimality,
)
from corner_half.structural_physics import is_stable

EXPECTED = {
    1: 16,
    2: 181,
    3: 1_796,
    4: 16_193,
    5: 135_074,
    6: 1_058_849,
    7: 7_905_398,
}


def theorem(rows: tuple[str, ...]) -> bool:
    left = "".join(row[0] for row in rows).rstrip("-")
    right = "".join(row[1] for row in rows).rstrip("-")
    full = [[row[0], row[1], "-", "-"] for row in rows]
    return (
        is_craftable_column(left)
        and is_craftable_column(right)
        and is_stable(full)
    )


def main() -> None:
    checked = 0
    for height in range(6):
        for rows in product(ROW_ALPHABET, repeat=height):
            if height and rows[-1] == "--":
                continue
            expected = theorem(rows)
            actual = HALF_DFA.accepts_rows(rows)
            assert actual == expected, (rows, expected, actual)
            checked += 1

    counts = {cap: HALF_DFA.count_up_to_cap(cap) for cap in EXPECTED}
    assert counts == EXPECTED, counts
    assert audit_frozen_table()
    stability_minimality = audit_stability_minimality()
    assert stability_minimality.minimal, stability_minimality
    minimality = audit_minimality()
    assert minimality.minimal, minimality
    assert minimality.states == 210
    assert HALF_DFA.raw_reachable_states == 552
    print(
        {
            "normalized_words_height_0_to_5": checked,
            "counts": counts,
            "stability_minimality": stability_minimality,
            "minimality": minimality,
        }
    )


if __name__ == "__main__":
    main()
