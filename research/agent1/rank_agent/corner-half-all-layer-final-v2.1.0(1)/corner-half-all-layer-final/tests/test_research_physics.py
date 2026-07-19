from __future__ import annotations

import itertools

from corner_half.research_physics import (
    ALPHABET,
    StructuralShape,
    apply_gravity,
    cut,
    is_stable,
    pin_push,
)


def main() -> None:
    checked = 0
    for cap in (1, 2):
        for cells in itertools.product(sorted(ALPHABET), repeat=4 * cap):
            rows = [cells[4 * l : 4 * l + 4] for l in range(cap)]
            shape = StructuralShape(tuple(tuple(r) for r in rows), cap)
            stable = apply_gravity(shape)
            assert apply_gravity(stable) == stable
            assert is_stable(stable)
            pushed = pin_push(stable)
            assert apply_gravity(pushed) == pushed
            east, west = cut(stable)
            assert apply_gravity(east) == east
            assert apply_gravity(west) == west
            checked += 1
    print({"checked": checked})


if __name__ == "__main__":
    main()
