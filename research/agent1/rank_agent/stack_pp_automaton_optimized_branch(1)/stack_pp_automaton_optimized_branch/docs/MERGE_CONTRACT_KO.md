# 병합 계약

## 1. `core-kernel`에서 받아야 하는 API

```python
class CompactShape(Hashable):
    ...

class ShapeKernel:
    def stack(self, bottom: CompactShape, top: CompactShape) -> CompactShape: ...
    def pin_push(self, shape: CompactShape) -> CompactShape: ...
    def canonical(self, shape: CompactShape) -> CompactShape: ...
    def order_key(self, shape: CompactShape) -> tuple: ...
    def visible_noncrystal_count(self, shape: CompactShape) -> int: ...
```

필수 의미:

- `stack`과 `pin_push`는 기존 `Shape.py`와 구조적으로 정확히 동일
- `canonical`은 저장 키용이며 forward replay의 방향을 바꾸지 않음
- `visible_noncrystal_count`는 비자명한 Stack에서 bottom으로 갈 때 엄격히 감소
- `CompactShape`는 immutable/hashable

## 2. `corner-half`에서 받아야 하는 API

```python
class HalfFamily:
    name = "half-buildable"
    def contains(self, shape: CompactShape) -> bool: ...
    def witness(self, shape: CompactShape) -> FamilyWitness | None: ...

class SwappableFamily:
    name = "swappable"
    ...

class TopPieceFamily:
    name = "rank0-stack-piece"
    ...
```

추가로 product frontier를 위해 다음이 필요하다.

```python
class LayerFamilyAutomaton:
    name: str
    def start_state(self): ...
    def advance(self, state, projected_a_row_signature): ...
    def accepts(self, state) -> bool: ...

class TopPiecePolicy:
    name: str
    def accepts(self, visible_b_row_signature) -> bool: ...
```

## 3. Stack closure 병합 순서

### 임시 호환 모드

```text
raw all-layer Stack frontier
→ A/B materialize
→ HalfFamily.contains(A)
→ TopPiecePolicy on every non-empty visible B row
```

정확하지만 family 거부 후보를 materialize하므로 최종형보다 느리다.

### 최종 product 모드

```text
상태 = StackOwnershipState × A-SupportState × HalfFamilyState
```

한 층의 ownership 선택과 동시에 A로 투영되는 행을 Half automaton에 전달한다.

```python
family_state2 = half.advance(family_state, projected_a_row)
if family_state2 is None:
    prune()
```

수용 조건:

```text
Stack 착지 조건 수용
AND A 안정성 수용
AND HalfFamily 수용
AND top piece sequence 수용
```

이렇게 해야 `Stack^{-1}(X)`의 일반 후보를 먼저 만들지 않고, 필요한 family와의 교집합을 직접 계산한다.

## 4. PP rank 병합 계약

`PPRankDomain` 구현은 다음을 보장해야 한다.

1. `seeds_for_batch(n)`의 모든 PP seed rank는 `< n`
2. `stack_closure(seed)`의 trace는 실제 Stack sequence로 replay 가능
3. `pin_push(predecessor)`는 exact forward semantics
4. `stack_witness(target, allowed_base)`는:
   - witness가 있으면 반드시 replay 가능
   - witness가 없다는 결론은 backend의 완전성 범위 안에서만 사용
5. 같은 batch cleanup에서 bottom base의 progress key는 target보다 엄격히 작음

## 5. `tmam-integration`에 제공하는 안정 API

```python
FamilyConstrainedStackRelation.candidates(...)
FamilyConstrainedStackRelation.first(...)
FamilyConstrainedStackRelation.exists(...)

PPRankEngine.run(...)
PPRankResult.entries
PPRankResult.batches
PPRankResult.true_pp
PPRankResult.retained_for_parent_chain
PPRankResult.fixed_point_proved
```

통합 브랜치는 내부 frontier 상태나 private 함수를 import하면 안 된다.

## 6. `stack_witness`의 중요한 완전성 조건

`stack_witness(X, allowed_base)`는 X의 바로 아래 한 단계 base만 검사하면 안 된다.
Stack layer sequence 전체를 한 번에 벗겨서 **어떤 허용 base까지 내려가는 모든 decomposition**을 판정해야 한다.

예를 들어:

```text
C = Stack(B, p2)
B = Stack(A, p1)
```

이면 B가 cleanup에서 제거되더라도 `allowed_base(A)=True`일 때 C의 witness는
`A + [p1,p2]`로 발견되어야 한다. 이 transitive Stack closure 완전성이 있어야 cpcp식 한 번의 cleanup과 결정론적 progress-order cleanup이 동치가 된다.

## 7. StackClosure automaton 재사용

`corner-half`가 finite `LayerFamilyAutomaton`을 주면:

```python
closure = StackClosureAutomaton(half_family, top_piece_policy)
```

로 얻은 closure 자체가 다시 `LayerFamilyAutomaton`이므로 다음 Stack product의
bottom family로 직접 사용할 수 있다. 상태 최소화는 `family-minimization`과
통합하되, 이 브랜치의 transition 의미를 변경하면 안 된다.

## 8. Optimized automaton contract (0.3.0)

기존 `StackClosureState(frozenset)` 표현은 differential oracle로만 유지한다.
통합 브랜치는 다음 public API를 사용한다.

```python
closure = StackClosureAutomaton(
    half_family,
    top_piece_policy,
    row_reader=compact_rows,
    materializer=stack_materializer,
    replay_validator=stack_replay,
)

ok = closure.accepts_shape(target)
witness = closure.witness(target)
metrics = closure.metrics()
```

대량 membership가 필요하고 reachable graph가 실제로 닫히는 경우:

```python
compiled = compile_complete_minimized(closure)
```

### Family quotient hook

`corner-half`가 다음을 구현하면 Stack product가 exact quotient를 사용한다.

```python
def canonical_state(state): ...
def state_includes(left, right): ...
```

의미:

```text
FutureLanguage(right) subset FutureLanguage(left)
```

증명되지 않은 inclusion을 반환하면 안 된다. hook이 없으면 equality만 사용한다.

### Build guard

`compile_complete_minimized(..., max_states=N)`이
`AutomatonBuildLimitExceeded`를 발생시켜도 target은 False/IMPOSSIBLE이 아니다.
통합 브랜치는 이 예외를 resource diagnostic으로만 전달한다.

### Witness/replay

- `accepts`는 parent history를 저장하지 않는다.
- `witness`는 target 한 개에 대해 path를 재실행한다.
- materialized candidate는 supplied `replay_validator`를 통과해야 한다.
- `FamilyConstrainedStackRelation`의 forward replay certificate는 계속 필수다.
