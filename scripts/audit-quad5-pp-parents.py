#!/usr/bin/env python3
"""Audit the exact Quad5 PP parent dump without using SMT.

Run with PYTHONPATH pointing at the bundled/legacy compact physics implementation:
  PYTHONPATH=/path/to/Shapez2-TMAM-Studio-0.8.0 python scripts/audit-quad5-pp-parents.py
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENTS = ROOT / "research" / "quad5" / "quad5_pp_parents_offline.tsv.gz"
BATCH_SUMMARY = ROOT / "research" / "quad5" / "quad5_batches_offline_fixed.txt"
OUT = ROOT / "reports" / "QUAD5_PP_PARENT_AUDIT.json"
CAP = 5


def profile(code: str) -> tuple[int, int, int, int]:
    layers = [(layer + "----")[:4] for layer in code.split(":") if layer]
    layers += ["----"] * (CAP - len(layers))
    values = []
    for q in range(4):
        k = 0
        while k < CAP and layers[k][q] == "P":
            k += 1
        values.append(k)
    return tuple(values)  # type: ignore[return-value]


def canonical_structural(code: str) -> str:
    from shape import Shape
    from data_operations import simplify_shape

    shape = Shape.from_string(code)
    variants: list[str] = []
    for mirrored in (False, True):
        current = shape.copy()
        if mirrored:
            current = current.mirror()
        for _ in range(4):
            variants.append(simplify_shape(repr(current)))
            current = current.rotate(clockwise=True)
    return min(variants)


def main() -> None:
    from shape import Shape
    from data_operations import simplify_shape

    Shape.MAX_LAYERS = CAP
    rows = 0
    batches: Counter[int] = Counter()
    rank_gaps: Counter[int] = Counter()
    strict_failures: list[dict[str, object]] = []
    replay_failures: list[dict[str, object]] = []

    with gzip.open(PARENTS, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            batch_text, target, pre_push = line.rstrip("\n").split("\t")
            batch = int(batch_text)
            rows += 1
            batches[batch] += 1
            sigma_target = sum(profile(target))
            sigma_pre = sum(profile(pre_push))
            rank_gaps[sigma_target - sigma_pre] += 1
            if sigma_target <= sigma_pre and len(strict_failures) < 20:
                strict_failures.append({
                    "batch": batch,
                    "target": target,
                    "pre_push": pre_push,
                    "sigma_target": sigma_target,
                    "sigma_pre_push": sigma_pre,
                })
            pushed = simplify_shape(repr(Shape.from_string(pre_push).push_pin()))
            if canonical_structural(pushed) != canonical_structural(target) and len(replay_failures) < 20:
                replay_failures.append({
                    "batch": batch,
                    "target": target,
                    "pre_push": pre_push,
                    "pushed": pushed,
                })

    report = {
        "cap": CAP,
        "records": rows,
        "parent_batch_counts": {str(k): v for k, v in sorted(batches.items())},
        "receipt_rank_gap_counts": {str(k): v for k, v in sorted(rank_gaps.items())},
        "minimum_receipt_rank_gap": min(rank_gaps) if rank_gaps else None,
        "maximum_receipt_rank_gap": max(rank_gaps) if rank_gaps else None,
        "strict_receipt_rank_failures": strict_failures,
        "pin_push_d4_replay_failures": replay_failures,
        "batch_summary": BATCH_SUMMARY.read_text(encoding="utf-8").splitlines() if BATCH_SUMMARY.exists() else [],
        "result": "PASS" if not strict_failures and not replay_failures else "FAIL",
        "notes": [
            "This validates every retained Quad5 PP parent edge, not an all-layer shared-predecessor parser.",
            "Branch-2/4 absorption observations remain accelerators/evidence unless separately proved for every layer.",
        ],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
