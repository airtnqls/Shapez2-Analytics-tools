from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def pct_reduction(before: float, after: float) -> float:
    return 100.0 * (before - after) / before if before else 0.0


def main() -> int:
    benchmark = json.loads(
        (REPORTS / "stack_automaton_benchmark.json").read_text(encoding="utf-8")
    )
    support = json.loads(
        (REPORTS / "support_quotient_generation.json").read_text(encoding="utf-8")
    )
    family = json.loads(
        (REPORTS / "family_quotient_benchmark.json").read_text(encoding="utf-8")
    )
    simulation = json.loads(
        (REPORTS / "product_subsumption_exhaustive.json").read_text(encoding="utf-8")
    )

    legacy = benchmark["full_reachable_build"]["legacy"]["1-2"]
    no_sub = benchmark["full_reachable_build"]["compact_no_subsumption"]
    optimized = benchmark["full_reachable_build"]["optimized"]
    minimized = benchmark["full_reachable_build"]["complete_minimized"]["metrics"]

    effects = [
        {
            "optimization": "support residual DFA minimization",
            "before": support["raw_reachable_support_states"],
            "after": support["minimized_support_states"],
            "reduction_percent": pct_reduction(
                support["raw_reachable_support_states"],
                support["minimized_support_states"],
            ),
            "proof": "complete 256-symbol DFA residual-language minimization",
        },
        {
            "optimization": "previous-row context projection",
            "before": 256,
            "after": 16,
            "reduction_percent": pct_reduction(256, 16),
            "proof": (
                "future B landing reads only previous full occupancy; support "
                "crystal history is internal to the support quotient"
            ),
        },
        {
            "optimization": "product residual inclusion antichain (L3)",
            "before": no_sub["states_per_exact_depth"][3],
            "after": optimized["states_per_exact_depth"][3],
            "reduction_percent": pct_reduction(
                no_sub["states_per_exact_depth"][3],
                optimized["states_per_exact_depth"][3],
            ),
            "proof": "future-language simulation; exhaustive reachable-product check",
        },
        {
            "optimization": "max deterministic subset size",
            "before": no_sub["metrics_before_release"]["max_subset_size"],
            "after": optimized["metrics_before_release"]["max_subset_size"],
            "reduction_percent": pct_reduction(
                no_sub["metrics_before_release"]["max_subset_size"],
                optimized["metrics_before_release"]["max_subset_size"],
            ),
            "proof": "same antichain theorem",
        },
        {
            "optimization": "complete DFA residual minimization",
            "before": minimized["source_states"],
            "after": minimized["minimized_states"],
            "reduction_percent": pct_reduction(
                minimized["source_states"], minimized["minimized_states"]
            ),
            "proof": "partition refinement after the reachable graph closed",
        },
        {
            "optimization": "global exact row action quotient",
            "before": 256,
            "after": minimized["alphabet_classes"],
            "reduction_percent": pct_reduction(256, minimized["alphabet_classes"]),
            "proof": "rows merged iff every minimized state has the same target",
        },
        {
            "optimization": "dense transitions to state-local sparse actions",
            "before": minimized["source_transitions"],
            "after": minimized["minimized_action_groups"],
            "reduction_percent": pct_reduction(
                minimized["source_transitions"],
                minimized["minimized_action_groups"],
            ),
            "proof": "exact grouping by equal next state",
        },
        {
            "optimization": "proved family-state quotient (synthetic L3)",
            "before": family["without_quotient"]["reachable_states"],
            "after": family["with_exact_quotient"]["reachable_states"],
            "reduction_percent": pct_reduction(
                family["without_quotient"]["reachable_states"],
                family["with_exact_quotient"]["reachable_states"],
            ),
            "proof": family["proof_scope"],
        },
    ]

    report = {
        "legacy_growth_cause_breakdown": {
            "family_states_in_universal_benchmark": 1,
            "legacy_states_L1_L2": legacy["states_per_exact_depth"],
            "legacy_product_pairs_L2": legacy["subset_per_depth"][2]["sum"],
            "legacy_max_subset_L2": legacy["subset_per_depth"][2]["max"],
            "legacy_transition_cache_entries_L2": legacy["transition_entries"],
            "legacy_peak_bytes_L2": legacy["tracemalloc_peak_bytes"],
            "conclusion": (
                "The first explosion is caused by support-history variants, "
                "powerset subsets, and per-row cache duplication before a "
                "multi-state family is even introduced."
            ),
        },
        "optimized_growth": {
            "states_per_exact_depth_L0_to_L5": optimized[
                "states_per_exact_depth"
            ],
            "max_subset_size": optimized["metrics_before_release"][
                "max_subset_size"
            ],
            "memory_after_releasing_build_caches": optimized[
                "metrics_after_release"
            ]["memory_bytes"],
            "complete_reachable_states": minimized["source_states"],
            "complete_minimized_states": minimized["minimized_states"],
        },
        "optimization_effects": effects,
        "subsumption_validation": simulation,
        "remaining_growth_sources": [
            "meaningful bottom-family residual states",
            "powerset determinization across inequivalent family residuals",
            "full complete-DFA construction when only one target is needed",
            "PP-rank iteration can create a new family automaton at each rank",
            "witness materialization and forward replay are output-sized",
        ],
    }
    out = REPORTS / "state_explosion_analysis.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
