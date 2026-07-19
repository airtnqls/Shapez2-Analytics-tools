# `stack-pp` 최종 인수 상태 — automaton optimization revision

## 담당 범위

```text
4. Half 기반 Stack closure
5. 일반 PP-essential rank
```

## 4번 Stack closure

### 완료

- legacy exact implementation 보존
- optimized exact lazy automaton 구현
- support residual DFA 2,011 → 131
- product inclusion antichain
- integer interning/canonicalization
- previous context 최소화
- dead/unreachable 제거
- lazy transition 및 sparse row action group
- exists-only와 witness 분리
- full reachable compilation
- exact complete DFA minimization
- global row action quotient
- optional exact family-state quotient/inclusion hook
- merge-facing metrics/API

### Universal benchmark

```text
legacy:    L0 1, L1 256, L2 4,019
optimized: L0 1, L1 81, L2 942, L3 2,082, L4 2,497, L5 2,527
complete live states: 2,536
minimized states:       962
```

### 정확성 봉인

- unit tests 36/36
- L2 전체 target 65,536 legacy/optimized mismatch 0
- support two-row 65,536 mismatch 0
- random multilayer legacy/optimized/direct 12,960 mismatch 0
- witness path 1,750 mismatch 0
- complete minimized random 5,800 mismatch 0
- product simulation transition obligations 232,289 failure 0
- 제공된 5층 Hybrid 367, canonical path 2,139, mismatch 0

## 5번 PP rank

### 유지되는 완료 범위

- cpcp식 batch 0 / batch n
- lower-rank parent contract
- Stack closure 뒤 Pin Push
- empty/Swappable/Stackable 제외
- same-batch progress cleanup
- deterministic smallest parent
- retained parent chain과 true PP 구분
- max_batches 중단과 fixed point 구분

### 이번 최적화가 제공한 것

- PP family product에서 사용할 안정된 `LayerFamilyAutomaton` API
- target 한 개용 lazy membership
- complete graph가 닫힐 때 compact minimized DFA
- exact family quotient hook
- build guard가 semantic False로 오염되지 않는 예외 계약

### 여전히 열린 전층 명제

- symbolic `PinPush(F)` image
- rank family fixed point
- same-batch symbolic essential basis
- negative certificate

따라서 일반 PP rank 전체가 완성됐다고 주장하지 않는다.

## 병합 준비 상태

다른 브랜치는 public API만 사용한다.

```python
StackClosureAutomaton
compile_complete_minimized
FamilyConstrainedStackRelation
PPRankEngine
```

private support/product intern table을 import하지 않는다.
