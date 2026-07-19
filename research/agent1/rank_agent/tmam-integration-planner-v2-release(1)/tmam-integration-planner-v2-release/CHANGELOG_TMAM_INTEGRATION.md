# Changelog

## 0.2.0

- Split Planner entry points into `solve_exists`, `solve_min_cost`, and `analyze_all_ops`.
- Added one mode-independent lazy provider spool shared across all three modes.
- Added family-context/progress/provider-revision/registry-generation cache keys and explicit invalidation epochs.
- Added positive and negative subgoal memoization, replay caching, cycle/rank gates, branch-and-bound, and deterministic tie-breaking.
- Added detailed Planner instrumentation and DOT call-graph export.
- Added GoalAnalysis-derived ShapeType mapping, GUI service APIs, and precomputed ProcessTree adapters that do not re-run tracers.
- Added generic state interning, reachable pruning, DFA minimization metrics, representative real Corner adapter tests, and before/after benchmarks.
- Public possibility vocabulary is now `POSSIBLE / IMPOSSIBLE / UNKNOWN`; older names remain aliases only.

## 0.1.0

- Initial tmam-integration branch contract.
- Added proof planner with completeness-aware impossible decisions.
- Added progress-based termination enforcement.
- Added proof DAG, replay validation, cost models, and metrics.
- Added DFA minimization, product algebra, counterexample search, and fixed-point audit.
- Added exact-facts-to-legacy-ShapeType mapping policy.
- Added plugin bootstrap and merge documentation.
