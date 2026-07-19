from __future__ import annotations

from itertools import product

from corner_half.corner_dfa import is_craftable_column
from corner_half.half_family import is_buildable_half

# Published exact cpcp HalfSet totals (orientations included).
EXPECTED = {
    1: 16,
    2: 181,
    3: 1_796,
    4: 16_193,
    5: 135_074,
}


def columns(cap: int) -> list[str]:
    out = {""}
    for n in range(1, cap + 1):
        for chars in product("-SPc", repeat=n):
            value = "".join(chars).rstrip("-")
            if is_craftable_column(value):
                out.add(value)
    return sorted(out)


def half_code(a: str, b: str, cap: int) -> str:
    rows = []
    for l in range(cap):
        rows.append(
            (a[l] if l < len(a) else "-")
            + (b[l] if l < len(b) else "-")
            + "--"
        )
    return ":".join(rows)


def main() -> None:
    for cap, expected in EXPECTED.items():
        vals = columns(cap)
        actual = sum(
            is_buildable_half(half_code(a, b, cap), cap)
            for a in vals
            for b in vals
        )
        print({"cap": cap, "columns": len(vals), "halves": actual})
        assert actual == expected, (cap, actual, expected)


if __name__ == "__main__":
    main()
