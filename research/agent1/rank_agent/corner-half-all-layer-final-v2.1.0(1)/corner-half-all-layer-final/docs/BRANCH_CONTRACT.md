# `corner-half` branch merge contract

## Corner API

```python
is_craftable_column(column: str) -> bool
first_rejection(column: str) -> RejectionCertificate | None
analyze_column(column: str) -> CornerWitness
construct_corner(column: str, cap: int | None = None)
corner_raw_proof(column: str, cap: int | None = None) -> ProofNode
```

## Half API

```python
HALF_DFA.accepts(code) -> bool
HALF_DFA.counts_by_height(cap) -> tuple[int, ...]
HALF_DFA.count_up_to_cap(cap) -> int

audit_minimality() -> MinimalityAudit
analyze_half(code: str, layers: int | None = None) -> HalfAnalysis
is_buildable_half(code: str, layers: int | None = None) -> bool
HALF_FAMILY.contains(code: str, layers: int) -> bool
HALF_FAMILY.witness(code: str, layers: int) -> HalfResult
construct_half(code: str, layers: int)
half_raw_proof(code: str, layers: int) -> ProofNode
```

## Cut/Swap inverse API

```python
canonical_cut_inverse(half_code, layers) -> CutHalfInverse
is_swappable_full(target, layers) -> bool
swap_inverse_candidates(target, layers) -> tuple[SwapFullInverse, ...]
first_swap_inverse(target, layers) -> SwapFullInverse
```

`swap_inverse_candidates`는 두 cutter 축만 검사한다. 각 candidate에는 two
Half operand proof, actual Swapper node, rotation-back node가 포함된다.

## Proof API

```python
verify_proof(root: ProofNode) -> ProofAudit
verify_proof_forest(roots: Sequence[ProofNode]) -> ProofForestAudit
clear_proof_caches() -> None
```

## Input abstraction

```text
- empty
S any ordinary part
P pin
c crystal
```

색상과 `C/R/S/W` provenance는 상위 planner가 구조 proof 뒤에서 복원한다.

## Core dependency

필수 exact operations:

```text
normalize stable rotate cut swap stack generate pin_push
```

이 브랜치는 timeout/error를 rejection으로 해석하지 않고 정상 membership에
`UNKNOWN`을 반환하지 않는다.

## Determinism

- Corner 19-state frozen transition table
- Half 210-state frozen transition table
- fixed natural/event constructor priority
- fixed C7 anchor ordering
- fixed Cut parent tower filler
- Swap inverse axis order 0 then 1
- fixed proof child order
