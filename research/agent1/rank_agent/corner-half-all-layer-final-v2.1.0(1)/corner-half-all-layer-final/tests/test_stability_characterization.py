from __future__ import annotations

from itertools import product
import random

from corner_half.structural_physics import is_stable, is_stable_by_replay


def main() -> None:
    checked = 0
    for cells in product('-SPc', repeat=8):
        rows = [list(cells[:4]), list(cells[4:])]
        assert is_stable(rows) == is_stable_by_replay(rows), ''.join(cells)
        checked += 1

    rng = random.Random(20260717)
    random_checked = 100_000
    for _ in range(random_checked):
        height = rng.randint(0, 30)
        rows = [[rng.choice('-SPc') for _ in range(4)] for _ in range(height)]
        assert is_stable(rows) == is_stable_by_replay(rows), rows

    print({'exhaustive_cap2': checked, 'random': random_checked, 'mismatch': 0})


if __name__ == '__main__':
    main()
