from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "archive" / "legacy-python-gui-20260719"
sys.path.insert(0, str(LEGACY))

from shape import Shape  # type: ignore
from corner_tracer import build_pinable_shape  # type: ignore

PILLAR = "SS-S-cS-S-c"
TARGET = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--"
CAP = 11


def structural(code: str) -> str:
    shape = Shape.from_string(code)
    rows = []
    for layer in shape.layers:
        row = []
        for q in layer.quadrants:
            if q is None:
                row.append("-")
            elif q.shape == "P":
                row.append("P")
            elif q.shape == "c":
                row.append("c")
            else:
                row.append("S")
        rows.append("".join(row))
    while rows and rows[-1] == "----":
        rows.pop()
    return ":".join(rows)


def pillars(code: str) -> list[str]:
    shape = Shape.from_string(code)
    out = []
    for q in range(4):
        word = []
        for layer in shape.layers:
            cell = layer.quadrants[q]
            if cell is None:
                word.append("-")
            elif cell.shape == "P":
                word.append("P")
            elif cell.shape == "c":
                word.append("c")
            else:
                word.append("S")
        out.append("".join(word).rstrip("-"))
    return out


def main() -> None:
    Shape.MAX_LAYERS = CAP
    predecessor = build_pinable_shape(PILLAR)
    predecessor_shape = Shape.from_string(predecessor)
    pushed = predecessor_shape.push_pin()
    pushed_code = repr(pushed)
    report = {
        "pillar": PILLAR,
        "cap": CAP,
        "legacyPredecessorExact": predecessor,
        "legacyPredecessorStructural": structural(predecessor),
        "legacyPredecessorPillars": pillars(predecessor),
        "pushedExact": pushed_code,
        "pushedStructural": structural(pushed_code),
        "pushedPillars": pillars(pushed_code),
        "targetStructural": TARGET,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
