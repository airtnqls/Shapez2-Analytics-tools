from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "reports" / "planner_benchmark.json"
data = json.loads(source.read_text(encoding="utf-8"))
comparisons = data["comparisons"]
selected = [
    row
    for row in comparisons
    if (
        (row["scenario"] == "shared_subgoal_goal" and row["repeats"] == 1)
        or (row["mode"] == "all_ops" and row["repeats"] == 100)
    )
]
summary = {
    "semantic_equivalence_checks": len(data["equivalence"]),
    "semantic_equivalence_failures": sum(
        not (
            row["same_status"]
            and row["same_possible_last_operations"]
            and row["same_min_cost_when_required"]
        )
        for row in data["equivalence"]
    ),
    "duplicate_inverse_calls_before_total": sum(
        row["duplicate_inverse_before"] for row in comparisons
    ),
    "duplicate_inverse_calls_after_total": sum(
        row["duplicate_inverse_after"] for row in comparisons
    ),
    "selected_comparisons": selected,
    "caveat": (
        "The optimized planner intentionally retains raw candidates/proofs for cross-mode reuse; "
        "some cold trivial min-cost cases use more memory/time than the minimal legacy memo, while "
        "exists-heavy and repeated all-ops workloads show the intended improvement."
    ),
}
output = ROOT / "reports" / "planner_benchmark_summary.json"
output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(output)
