# 변경 파일과 병합 영향

## Public API 변경

`stack_pp.StackClosureAutomaton`은 이제 최적화 exact 구현이다.
기존 powerset 구현은 `stack_pp.LegacyStackClosureAutomaton`으로 보존된다.

새 public symbol:

```text
AutomatonMetrics
ExplorationMetrics
SparseTransitionGroup
StackClosureWitness
StackClosureAutomaton
LegacyStackClosureAutomaton
AutomatonBuildLimitExceeded
CompleteBuildMetrics
MinimizedStackClosureDFA
compile_complete_minimized
```

## 새 코드

```text
stack_pp/row_table.py
stack_pp/support_quotient.py
stack_pp/optimized_stack_closure.py
stack_pp/compiled_stack_dfa.py
```

- `row_table.py`: 256개 구조행의 compact id 및 projection/landing table
- `support_quotient.py`: 생성된 131-state exact support residual quotient
- `optimized_stack_closure.py`: lazy exact membership, antichain, witness, metrics
- `compiled_stack_dfa.py`: complete reachable compilation, exact minimization, sparse action table

## 수정 코드

```text
stack_pp/__init__.py
stack_pp/stack_product.py
stack_pp/protocols.py
pyproject.toml
```

- 기존 구현의 의미는 삭제하지 않고 legacy alias로 유지한다.
- family quotient는 optional proof hook이며 hook이 없으면 equality만 사용한다.
- package version은 `0.3.0`이다.

## 새 테스트

```text
tests/test_support_quotient.py
tests/test_optimized_stack_closure.py
```

전체 테스트는 `python run_tests.py`로 실행한다.

## 새 도구

```text
tools/generate_support_quotient.py
tools/validate_product_subsumption.py
tools/benchmark_stack_automata.py
tools/audit_optimized_367.py
tools/benchmark_family_quotient.py
tools/build_optimization_summary.py
```

## Merge 시 필요한 외부 연결

`core-kernel`:

```text
row_reader
materializer
forward Stack replay validator
```

`corner-half`:

```text
LayerFamilyAutomaton
선택적 canonical_state(state)
선택적 state_includes(left, right)
```

두 quotient hook은 residual-language 증명이 있을 때만 활성화한다.

## 호환성 주의

기존 코드가 `StackClosureState` 객체를 직접 조작했다면
`LegacyStackClosureAutomaton`을 명시적으로 사용해야 한다.
일반 membership 코드는 새 integer-state `StackClosureAutomaton`으로 이동한다.

## 비주장 범위

이 변경은 일반 symbolic PP fixed point를 해결하지 않는다.
`PPRankEngine`의 batch/rank/certificate 의미는 유지되며,
Stack family product의 상태 표현만 안정화한다.
