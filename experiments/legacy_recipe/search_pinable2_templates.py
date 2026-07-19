from __future__ import annotations

import contextlib
import io
import itertools
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_corner_recipe import TARGET_CODE, TARGET_LEFT_PILLAR, Shape, cell_distance, structural  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    from corner_tracer import build_pinable_shape  # noqa: E402

CAP = len(TARGET_LEFT_PILLAR)


def columns(code: str) -> tuple[str, str, str, str]:
    rows = code.split(":") if code else []
    return tuple("".join(row[q] for row in rows).ljust(CAP, "-")[:CAP] for q in range(4))  # type: ignore[return-value]


def shape_from_columns(a: str, b: str, c: str, d: str) -> Shape:
    # corner_tracer.format_final_result uses output order A,B,D,C.
    rows = [f"{a[i]}{b[i]}{d[i]}{c[i]}" for i in range(CAP)]
    shape = Shape.from_string(":".join(rows))
    shape.max_layers = CAP
    return shape


def shift_left(text: str, fill: str = "-") -> str:
    return text[1:] + fill


def dedupe(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    out = []
    for name, value in items:
        if value not in seen:
            seen.add(value)
            out.append((name, value))
    return out


def build_variants() -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    with contextlib.redirect_stdout(io.StringIO()):
        standard_code = build_pinable_shape(TARGET_LEFT_PILLAR)
    std_a, std_b, std_d, std_c = columns(standard_code)
    target_a, target_b, _, _ = columns(structural(Shape.from_string(TARGET_CODE)))

    low_c = TARGET_LEFT_PILLAR.index("c")
    prefix = TARGET_LEFT_PILLAR[:low_c]
    total_s = prefix.count("S")
    compact_prefix = "-" * (low_c - total_s) + "S" * total_s
    compact_a = compact_prefix + TARGET_LEFT_PILLAR[low_c:]
    target_suffix_a = target_a[1:] + "-"
    target_suffix_b = target_b[1:] + "-"

    a_variants = dedupe(
        [
            ("legacy_A", std_a),
            ("legacy_A_bottom_empty", "-" + std_a[1:]),
            ("unfinished_compact_A", compact_a),
            ("unfinished_compact_A_shift", shift_left(compact_a)),
            ("compact_A_bottom_empty", "-" + compact_a[1:]),
            ("target_suffix_A", target_suffix_a),
            ("target_suffix_A_bottom_empty", "-" + target_suffix_a[1:]),
            ("target_A_bottom_empty", "-" + target_a[1:]),
        ]
    )
    b_variants = dedupe(
        [
            ("legacy_B", std_b),
            ("legacy_B_bottom_empty", "-" + std_b[1:]),
            ("solid_B", "S" * CAP),
            ("solid_B_bottom_empty", "-" + "S" * (CAP - 1)),
            ("target_suffix_B", target_suffix_b),
            ("target_B_bottom_empty", "-" + target_b[1:]),
            ("compact_B", compact_prefix.replace("-", "P") + "S" * (CAP - low_c)),
        ]
    )
    c_variants = dedupe(
        [
            ("legacy_C", std_c),
            ("legacy_C_bottom_S", "S" + std_c[1:]),
            ("legacy_C_bottom_c", "c" + std_c[1:]),
            ("all_c_C", "c" * CAP),
            ("all_S_C", "S" * CAP),
            ("empty_C", "-" * CAP),
            ("event_C", "".join("c" if ch == "c" else "S" if ch == "S" else "-" for ch in TARGET_LEFT_PILLAR)),
        ]
    )
    d_variants = dedupe(
        [
            ("legacy_D", std_d),
            ("legacy_D_bottom_S", "S" + std_d[1:]),
            ("legacy_D_bottom_c", "c" + std_d[1:]),
            ("all_c_D", "c" * CAP),
            ("all_S_D", "S" * CAP),
            ("empty_D", "-" * CAP),
            ("alternating_D", "".join("S" if i % 2 == 0 else "c" for i in range(CAP))),
        ]
    )
    return a_variants, b_variants, c_variants, d_variants


@dataclass(frozen=True)
class Candidate:
    distance: int
    source: str
    output: str
    stable: bool
    variants: dict[str, str]


def search() -> dict:
    Shape.MAX_LAYERS = CAP
    goal_shape = Shape.from_string(TARGET_CODE)
    goal_shape.max_layers = CAP
    goal = structural(goal_shape)
    a_variants, b_variants, c_variants, d_variants = build_variants()

    checked = stable_checked = 0
    best: list[Candidate] = []
    hit = None
    for (an, a), (bn, b), (cn, c), (dn, d) in itertools.product(a_variants, b_variants, c_variants, d_variants):
        checked += 1
        source = shape_from_columns(a, b, c, d)
        stable = source.is_stable()
        if not stable:
            continue
        stable_checked += 1
        output = source.push_pin()
        output_code = structural(output)
        candidate = Candidate(
            distance=cell_distance(output_code, goal),
            source=structural(source),
            output=output_code,
            stable=True,
            variants={"A": an, "B": bn, "C": cn, "D": dn},
        )
        best.append(candidate)
        if output_code == goal:
            hit = candidate
            break

    best.sort(key=lambda x: (x.distance, len(x.source), tuple(x.variants.values()), x.source))
    return {
        "schema_version": 1,
        "pillar": TARGET_LEFT_PILLAR,
        "unfinished_idea": "pack S before first crystal to the upper side while keeping bottom target columns empty",
        "variant_counts": {
            "A": len(a_variants),
            "B": len(b_variants),
            "C": len(c_variants),
            "D": len(d_variants),
        },
        "checked": checked,
        "stable_checked": stable_checked,
        "hit": None if hit is None else asdict(hit),
        "closest": [asdict(x) for x in best[:20]],
    }


if __name__ == "__main__":
    print(json.dumps(search(), ensure_ascii=False, indent=2))
