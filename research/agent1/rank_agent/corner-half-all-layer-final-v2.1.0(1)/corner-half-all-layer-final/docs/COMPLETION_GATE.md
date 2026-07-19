# Completion gate — CLOSED

## G1 Corner language and constructor — PASS

- exact six-rule language
- 19-state minimum DFA
- C1..C7 concrete operation lowering
- raw-input proof DAG
- soundness/completeness/termination

## G2 Half family and constructor — PASS

```text
BuildableHalf(u,v) iff Corner(u) and Corner(v) and Stable(u,v)
```

- direct exchange construction
- raw-input proof DAG
- exact cpcp bitset equality cap1..6

## G3 Non-circular proof dependency — PASS

```text
Direct prefab
 -> Solid Half
 -> Natural Corner
 -> Natural Half
 -> Event Corner
 -> General Half
```

Natural Corner helper graph has no cycle and every Half child is solid with
strictly fewer gaps.

## G4 Minimal symbolic closure — PASS

- 6-state minimum stability DFA
- 552 reachable raw product states
- 210-state minimum Half DFA
- all 21,945 state pairs distinguishable

## G5 Cut/Swap inverse — PASS

- canonical buildable Cutter parent for every Half
- exact Swappable iff two geometric halves are Half-family members
- deterministic raw-input witnesses

## G6 Validation — PASS

Evidence:

- `reports/VALIDATION_ALL_LAYER_COMPLETE.json`
- `reports/half_minimal_dfa.json`
- `reports/natural_corner_dependency_audit.json`
- `reports/half_oracle/*`
- `tests/test_half_automaton.py`
- `tests/test_half_inverse.py`
- `tests/test_proof_forest.py`

## G7 Integration — branch PASS

Shared `core-kernel` merge must rerun differential tests. This is an integration
condition, not an unresolved theorem in this branch.
