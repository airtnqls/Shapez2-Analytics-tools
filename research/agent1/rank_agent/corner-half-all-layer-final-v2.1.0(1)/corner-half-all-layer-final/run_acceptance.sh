#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT:$ROOT/tests${PYTHONPATH:+:$PYTHONPATH}"

run() {
  local name="$1"; shift
  echo "===== $name ====="
  /usr/bin/time -f 'TIME %e RSS %M' "$@"
}

run self_test python self_test.py
run corner_exact python tests/test_corner_exact.py
run component_plans python tests/test_component_plans.py
run corner_natural_plan python tests/test_corner_natural_plan.py
run corner_event_plan python tests/test_corner_event_plan.py
run event_zone_plans python tests/test_event_zone_plans.py
run c7_gadget python tests/test_c7_gadget.py
run c7_exhaustive python tests/test_c7_exhaustive.py
run c7_exhaustive_random python tests/test_c7_exhaustive_random.py
run corner_constructor python tests/test_corner_constructor.py
run corner_constructor_high python tests/test_corner_constructor_high.py
run corner_event_generated python tests/test_corner_event_generated.py
run corner_ir python tests/test_corner_ir.py
run corner_macro_replay python tests/test_corner_macro_replay.py
run corner_full_replay python tests/test_corner_full_replay.py
run primitive_prefabs python tests/test_primitive_prefabs.py
run structural_ops python tests/test_structural_ops.py
run research_physics python tests/test_research_physics.py
run stability_characterization python tests/test_stability_characterization.py
run half_theorem_counts python tests/test_half_theorem_counts.py
run half_automaton python tests/test_half_automaton.py
run half_constructor python tests/test_half_constructor.py
run half_full_replay python tests/test_half_full_replay.py
run half_inverse python tests/test_half_inverse.py
run proof_dag python tests/test_proof_dag.py
run natural_dependency python tests/test_natural_dependency.py
run determinism python tests/test_determinism.py

# Large forests are separate processes so memory is released between them.
run proof_forest_corner7 python tests/test_proof_forest.py --mode corner7
run proof_forest_half4 python tests/test_proof_forest.py --mode half4
run proof_forest_high189 python tests/test_proof_forest.py --mode high189

echo '===== ACCEPTANCE PASS ====='
