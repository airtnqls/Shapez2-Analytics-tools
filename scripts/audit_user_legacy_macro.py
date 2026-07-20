from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.structural_physics import code, column, parse, push_pin

PILLAR = "SS-S-cS-S-c"
TARGET = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--"
CAP = 11


def rightmost_cluster_left_position(value: str, char: str) -> int:
    for i in range(len(value) - 1, -1, -1):
        if value[i] == char:
            start = i
            while start > 0 and value[start - 1] == char:
                start -= 1
            return start - 1 if start > 0 else 0
    return -1


def drop_info(value: str):
    drop_positions: list[int] = []
    drop_heights: list[int] = []
    drop_targets: list[int] = []
    work = list(value)
    for crystal in [i for i, ch in enumerate(value) if ch == "c"]:
        if crystal <= 0 or work[crystal - 1] != "-":
            continue
        source = next((j for j in range(crystal - 1, -1, -1) if work[j] == "S"), -1)
        if source < 0:
            continue
        drop_positions.append(source)
        gaps = 0
        for j in range(source - 1, -1, -1):
            if work[j] != "-":
                break
            gaps += 1
        if gaps == source:
            gaps -= 1
        drop_heights.append(gaps)
        drop_targets.append(crystal - 1)
        work[source] = "-"
    return drop_positions, drop_heights, drop_targets, work


def shift(values: list[str], fill: str) -> list[str]:
    return values[1:] + [fill]


def format_abdc(a: list[str], b: list[str], c: list[str], d: list[str]) -> str:
    height = max(map(len, (a, b, c, d)))
    rows = []
    for i in range(height):
        av = a[i] if i < len(a) else "-"
        bv = b[i] if i < len(b) else "-"
        cv = c[i] if i < len(c) else "-"
        dv = d[i] if i < len(d) else "-"
        # Legacy GUI string order is A, B, D, C.
        rows.append(av + bv + dv + cv)
    return ":".join(rows)


def build_pinable_shape(value: str, cap: int) -> str:
    length = max(len(value), cap)
    source = value.ljust(length, "-")
    l2 = rightmost_cluster_left_position(source, "c")
    drop_positions, drop_heights, drop_targets, modified = drop_info(source)
    highest = source.rfind("c")

    a = modified.copy()
    if highest >= 0:
        for i in range(min(len(a), highest + 1)):
            if a[i] == "-":
                a[i] = "c"
    for position in drop_targets:
        if 0 <= position < len(a):
            a[position] = "S"
    a = shift(a, "-")
    if source and source[0] in "-S":
        for i, cell in enumerate(a):
            if cell != "c":
                break
            a[i] = "-"

    b = list(source)
    if l2 >= 0:
        for i in range(min(len(b), l2 + 1)):
            if b[i] == "-":
                b[i] = "P"
    b = ["S" if cell == "c" else cell for cell in b]
    if highest >= 0:
        for i in range(highest, len(b)):
            if b[i] == "-":
                b[i] = "S"
    b = shift(b, "-")

    c = ["-"] * length
    if l2 >= 0:
        for i in range(min(len(c), l2 + 1)):
            c[i] = "c"
    for position in [i for i, ch in enumerate(source) if ch in "cS"]:
        if position not in drop_positions and c[position] == "c":
            c[position] = "S"
    for position, height in zip(drop_targets, drop_heights):
        if 0 <= position < len(c):
            c[position] = "S"
        for offset in range(1, height + 1):
            if position - offset >= 0:
                c[position - offset] = "S"
    c = shift(c, "-")

    d = ["c"] * length
    if source and source[0] == "S":
        for i, cell in enumerate(a):
            if cell != "-":
                break
            if i + 1 >= len(a) or a[i + 1] != "-":
                a[i] = "S"
                if i < len(c) and c[i] == "S":
                    c[i] = "c"
                    c[0] = "S"
                break
    return format_abdc(a, b, c, d)


def columns(shape_code: str) -> list[str]:
    rows = parse(shape_code, CAP)
    return [column(rows, q) for q in range(4)]


def main() -> None:
    predecessor = code(parse(build_pinable_shape(PILLAR, CAP), CAP))
    pushed = code(push_pin(parse(predecessor, CAP), CAP))
    report = {
        "pillar": PILLAR,
        "cap": CAP,
        "legacyPredecessorStructural": predecessor,
        "legacyPredecessorPillars": columns(predecessor),
        "pushedStructural": pushed,
        "pushedPillars": columns(pushed),
        "targetStructural": TARGET,
        "targetPillars": columns(TARGET),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
