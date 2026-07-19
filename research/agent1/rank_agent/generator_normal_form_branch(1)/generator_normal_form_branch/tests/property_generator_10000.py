from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator_normal_form import (
    GeneratorConstraint,
    NotGeneratorImage,
    canonical_raw_predecessor,
    generator_forward_structural,
    set_cell,
    trim_shape,
)


def random_shape(rng: random.Random, height: int):
    rows = []
    for _ in range(height):
        row = 0
        for q in range(4):
            row = set_cell(row, q, rng.randrange(4))
        rows.append(row)
    # Force the chosen height to be the global height.
    if all(((rows[-1] >> (2 * q)) & 3) == 0 for q in range(4)):
        rows[-1] = set_cell(rows[-1], rng.randrange(4), rng.randrange(1, 4))
    return trim_shape(rows)


def main():
    rng = random.Random(20260717)
    total = 10_000
    productive = 0
    no_op = 0
    failures = []
    max_height = 0
    t0 = time.perf_counter()
    for i in range(total):
        height = rng.randint(1, 128)
        max_height = max(max_height, height)
        predecessor = random_shape(rng, height)
        target = generator_forward_structural(predecessor)
        changed = predecessor != target
        if changed:
            productive += 1
        else:
            no_op += 1
        try:
            constraint = GeneratorConstraint.structural(target, productive_only=changed)
        except NotGeneratorImage as exc:
            failures.append({"index": i, "reason": f"unexpected image rejection: {exc}"})
            continue
        if not constraint.accepts_predecessor(predecessor):
            failures.append({"index": i, "reason": "known predecessor rejected"})
            continue
        # The known-parent membership check runs for all 10,000 cases.
        # Canonical DP replay is sampled because it expands up to 81 row
        # choices per layer and is separately benchmarked at 10,000 layers.
        if i < 500 or i % 100 == 0:
            witness = canonical_raw_predecessor(constraint)
            try:
                witness.certify()
            except Exception as exc:
                failures.append({"index": i, "reason": f"canonical replay: {exc!r}"})
        if len(failures) >= 20:
            break
    elapsed = time.perf_counter() - t0
    report = {
        "seed": 20260717,
        "requested": total,
        "completed": total if not failures else i + 1,
        "productive": productive,
        "no_op": no_op,
        "max_height": max_height,
        "failures": len(failures),
        "failure_samples": failures,
        "seconds": elapsed,
    }
    out = ROOT / "reports" / "PROPERTY_GENERATOR_10000.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
