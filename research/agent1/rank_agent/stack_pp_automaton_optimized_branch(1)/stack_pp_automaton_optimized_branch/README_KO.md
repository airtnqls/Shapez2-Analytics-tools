# `stack-pp` 브랜치 — optimized Stack closure / PP rank core

담당 범위:

```text
4. Half 기반 Stack closure
5. 일반 PP-essential rank
```

이번 버전의 중심은 **Stack/Family automaton의 상태 폭발 제어**다. 기존 정확 경로는 `LegacyStackClosureAutomaton`으로 유지하고, public `StackClosureAutomaton`은 residual quotient·antichain·compact ID·lazy sparse transition을 사용한다.

## 설치와 테스트

```bash
python run_tests.py
```

현재 봉인:

```text
unit tests: 36
failures:   0
```

## 가장 짧은 사용법

```python
from stack_pp import StackClosureAutomaton

closure = StackClosureAutomaton(
    base_family=half_family,
    top_policy=top_piece_policy,
)

possible = closure.accepts_rows(target_rows)
witness = closure.witness(target_rows)
assert possible == (witness is not None)
```

한 target만 판정할 때는 full DFA를 만들지 않는다. state ID와 필요한 `(state,row)` transition만 lazy 생성한다.

## 완전 DFA가 필요한 경우

```python
from stack_pp import compile_complete_minimized

compiled = compile_complete_minimized(closure)
possible = compiled.accepts_rows(target_rows)
metrics = compiled.metrics()
```

Universal 1-state base family에서는 complete reachable graph가 2,536 live state에서 닫혔고, all-suffix DFA 최소화 후 962 state가 됐다.

## 주요 최적화

- support concrete state 2,011 → exact residual DFA 131
- previous full row context 256 → occupancy mask 16
- powerset product를 future-language inclusion antichain으로 정규화
- `frozenset[(support,family)]` → interned integer product/subset/state ID
- dead state 0 하나
- local component transition packed cache
- state-local row action grouping
- complete DFA global row alphabet quotient 256 → 200
- complete reachable DFA residual minimization 2,536 → 962
- exists-only와 witness 경로 완전 분리
- optional exact `canonical_state/state_includes` family hook

자세한 수치:

- `docs/STATE_EXPLOSION_ANALYSIS_KO.md`
- `docs/OPTIMIZATION_EFFECTS_KO.md`
- `reports/stack_automaton_benchmark.json`

## Public API

```python
StackClosureAutomaton.accepts_rows(rows)
StackClosureAutomaton.accepts_shape(shape)
StackClosureAutomaton.witness(rows_or_shape)
StackClosureAutomaton.transition(state_id, row_id)
StackClosureAutomaton.transition_groups(state_id)
StackClosureAutomaton.metrics()
StackClosureAutomaton.explore(max_layers)

compile_complete_minimized(closure)
LegacyStackClosureAutomaton
```

병합 계약은 `docs/AUTOMATON_API_KO.md`와 `docs/MERGE_CONTRACT_KO.md`를 따른다.

## 정확성 경계

완료:

- finite deterministic bottom family에 대한 exact Stack closure
- family-constrained ownership/support product
- exact support quotient
- exact existential antichain
- accepts/witness equivalence
- complete reachable graph가 닫힌 경우 exact DFA minimization
- cpcp식 PP batch/rank engine과 rank certificate 의미

아직 전체 전층 PP fixed point로 주장하지 않는 것:

- 일반 `PinPush(F)`의 작은 exact symbolic image
- rank 반복 상태 수 통제
- same-batch essential basis의 symbolic closure
- finite negative/fixed-point certificate

## 중요한 금지사항

- timeout/state guard를 IMPOSSIBLE로 해석하지 않는다.
- family quotient를 테스트만 보고 활성화하지 않는다.
- unrestricted 일반 A/B 재귀 역산을 하지 않는다.
- acceptance와 witness를 다른 의미 관계로 구현하지 않는다.
- fixed-layer 결과를 전층 PP 완전성으로 부르지 않는다.
