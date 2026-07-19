# 다른 브랜치용 Stack automaton API

## 기본 lazy automaton

```python
from stack_pp import StackClosureAutomaton

closure = StackClosureAutomaton(
    base_family=half_family,
    top_policy=top_piece_policy,
    row_reader=compact_materializer.rows,          # optional
    materializer=compact_materializer,             # optional
    replay_validator=forward_stack_validator,      # optional
)
```

### Membership

```python
ok = closure.accepts_rows(rows)
ok = closure.accepts_shape(compact_shape)
```

`accepts_rows`는 parent history를 저장하지 않는다.

### Witness

```python
w = closure.witness(rows_or_shape)
if w is not None:
    path = w.ownership_path
    candidate = w.materialized
```

`materializer`를 제공했다면 후보를 materialize한다. `replay_validator`를 제공했다면 실패는 예외이며 후보로 반환하지 않는다.

### LayerFamilyAutomaton 사용

```python
state = closure.start_state()
state = closure.advance(state, row_signature)
accepted = state is not None and closure.accepts(state)
```

따라서 closure 자체를 다음 Stack product의 bottom family로 넣을 수 있다.

### Transition/metrics

```python
next_id = closure.transition(state_id, row_id)  # dead=0
classes = closure.transition_groups(state_id)
m = closure.metrics()
```

`AutomatonMetrics` 핵심 필드:

```python
reachable_states
transitions
peak_frontier
memory_bytes
build_seconds
```

추가로 product/family/cache/subset 수를 제공한다.

## Complete minimized DFA

전체 reachable graph를 실제로 materialize할 필요가 있을 때만 사용한다.

```python
from stack_pp import compile_complete_minimized

compiled = compile_complete_minimized(closure)
compiled.accepts_rows(rows)
compiled.transition(state_id, row_id)
compiled.metrics()
compiled.witness(rows)  # source lazy automaton으로 위임
```

`max_states`를 사용한 diagnostic guard가 발동하면 `AutomatonBuildLimitExceeded`가 발생한다. 이것을 False/IMPOSSIBLE로 바꾸면 안 된다.

## Bottom-family optional quotient 계약

`corner-half`는 다음 hook을 선택적으로 제공할 수 있다.

```python
class HalfFamilyAutomaton:
    def canonical_state(self, state): ...

    def state_includes(self, left, right) -> bool:
        # FutureLanguage(right) subset FutureLanguage(left)
        ...
```

두 hook은 residual language equality/inclusion이 증명된 경우에만 제공한다. 없으면 Stack branch는 equality만 사용해 완전성을 보존한다.

## PP branch 연결

PP rank에서 권장 사용:

1. 개발/target 한 개: lazy `StackClosureAutomaton`
2. Half family product가 작고 complete graph가 닫힘: `compile_complete_minimized`
3. family state가 커짐: 먼저 `corner-half`의 exact family quotient/minimization
4. 어떤 build limit도 PP rejection으로 해석하지 않음

PP rank의 fixed point 자체는 이 API가 해결했다고 주장하지 않는다.
