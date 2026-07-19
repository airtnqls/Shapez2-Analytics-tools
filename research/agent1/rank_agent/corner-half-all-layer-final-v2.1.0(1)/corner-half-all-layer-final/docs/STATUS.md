# Status — `corner-half` all-layer branch

## 담당 범위 — COMPLETE

- 전층 Corner concrete constructor
- 전층 Half constructor
- Half family soundness/completeness
- Cut/Swap용 일반 Half inverse
- Half symbolic closure와 최소 상태 표현

## Corner

```text
Corner(w) <=> six forbidden patterns are absent
```

- 19-state minimal DFA
- 최초 reject rule/position certificate
- natural/event semantic factorization
- C1–C6 actual operation lowering
- arbitrary finite C7 duty compiler
- sole-leaf raw proof DAG
- 단계화된 비순환 상호귀납 증명

## Half

```text
BuildableHalf(u,v)
<=> Corner(u) and Corner(v) and Stable(u,v)
```

- 직접 Swap→Rotate→Cut constructor
- compact certificate와 raw operation DAG
- cpcp Half Ops1–6 concrete closure의 동치 축약
- exact bitset cap1..6 FP/FN 0
- cap7 total 7,905,398 일치

## Symbolic closure

- stability language: 6-state minimal DFA
- raw Corner×Corner×Stability reachable product: 552 states
- minimized oriented Half DFA: **210 states**
- 210/210 reachable
- 21,945/21,945 state pairs distinguishable
- max distinguishing suffix: 9 layers
- max reachability representative: 4 layers

## Cut/Swap inverse

```text
H in HalfFamily
<=> canonical buildable Cutter parent exists

Swappable(X)
<=> some cutter-axis orientation has two geometric halves in HalfFamily
```

각 accepted inverse는 raw-input proof와 independent forward replay를 가진다.

## 재감사 수치

- Corner regex/DFA/semantic length0..9: 349,525, mismatch 0
- Corner constructor accepted length0..10: 104,191, failure 0
- cap7 Corner raw proof forest: 4,320 roots, failure 0
- cap4 Half raw proof forest: 16,193 roots, failure 0
- Half normalized words height0..5: 1,048,576, DFA mismatch 0
- Half bitset cap1..6: FP 0 / FN 0
- natural Corner dependency:
  - roots 3,212
  - half-dependent roots 1,139
  - edges 2,438
  - cycles 0
  - every child solid and strict gap decrease
- Cutter inverse cap3: 1,796/1,796 replay
- cap2 full targets: exact Swappable oracle mismatch 0
- Swappable cap2 targets: 35,017
- sampled raw Swap inverses: 2,000 targets / 3,724 roots, failure 0

## 병합 상태

API와 수학적 범위는 완료되어 `core-kernel`, `stack-pp`,
`tmam-integration`이 사용할 수 있다. 병합 후 shared `CompactPhysics`에 대해
동일 differential suite를 재실행해야 한다.

Lean/Coq kernel proof는 아니다. 자족적 손증명, 최소 automaton certificate,
raw-input operation DAG, exact fixed-cap oracle 및 독립 replay를 결합했다.
