from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator_normal_form import (
    GeneratorConstraint,
    canonical_raw_predecessor,
    encode_row,
)


def run(height: int):
    target = (encode_row("cccc"),) * height
    t0 = time.perf_counter()
    constraint = GeneratorConstraint.structural(target)
    t1 = time.perf_counter()
    count = constraint.unconstrained_count()
    t2 = time.perf_counter()
    witness = canonical_raw_predecessor(constraint)
    t3 = time.perf_counter()
    return {
        "height": height,
        "constraint_seconds": t1 - t0,
        "count_seconds": t2 - t1,
        "solve_seconds": t3 - t2,
        "count_decimal_digits": 1 if count == 0 else int(count.bit_length() * math.log10(2)) + 1,
        "witness_crystal_drop": witness.crystal_drop,
        "witness_pins": witness.objective.pins,
    }


def main():
    rows = [run(h) for h in (10, 100, 1000, 5000, 10000)]
    report = {"benchmark": rows}
    out = ROOT / "reports" / "BENCHMARK_GENERATOR.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
