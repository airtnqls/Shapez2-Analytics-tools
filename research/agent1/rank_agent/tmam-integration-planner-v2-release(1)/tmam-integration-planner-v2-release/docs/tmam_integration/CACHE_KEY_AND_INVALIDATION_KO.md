# Cache key와 invalidation 설계

## Raw provider key

raw inverse 결과는 SearchMode와 무관하게 하나만 저장한다.

```text
ProviderCacheKey(
    GoalCacheKey(
        target_canonical_id,
        progress,
        family_context,
        registry_generation,
    ),
    provider_id,
    provider_revision,
)
```

### 각 항목이 필요한 이유

- `target_canonical_id`: 회전/대칭 등 core canonicalization 이후 동일 목표 공유.
- `progress`: 같은 도형이어도 허용 PP rank/Stack budget이 다르면 역관계가 달라질 수 있음.
- `family_context`: 허용 base family, rank, abstraction policy가 다른 결과를 절대 혼합하지 않음.
- `registry_generation`: provider 등록/해제 후 이전 graph를 자동 폐기.
- `provider_id`: relation별 분리.
- `provider_revision`: provider 구현/정리 변경 시 cache token 증가.

**mode는 raw key에 들어가지 않는다.** EXISTS/MIN_COST/ALL_OPS가 같은 iterator spool을 공유하기 때문이다.

## Incremental spool

provider cache는 단순 tuple 캐시가 아니다.

```text
inverse() 호출 1회
→ lazy iterator 저장
→ 이미 읽은 candidates[] 저장
→ EXISTS가 index 0까지만 읽고 종료 가능
→ MIN_COST가 index 1부터 이어서 읽음
→ exhausted 여부 저장
```

따라서 존재 판정 때문에 모든 witness를 materialize하지 않으면서도, 나중 모드가 provider를 다시 호출하지 않는다.

## Derived caches

- goal EXISTS 결과
- goal MIN_COST 결과
- `(goal, operation)`별 evidence
- complete GoalAnalysis
- candidate EXISTS outcome
- candidate MIN_COST outcome
- candidate contract validation
- forward replay 결과

`IMPOSSIBLE` 결과도 저장하므로 실패 subgoal을 다시 계산하지 않는다.

## Invalidation API

```python
planner.clear_cache()
planner.invalidate_provider("stack.family_constrained")
planner.invalidate_family_context(context)
```

registry에 provider/family/plugin이 추가·삭제되면 `registry.generation`이 증가하며 다음 planner 호출에서 전체 derived graph가 자동 무효화된다. 또한 모든 수동 무효화마다 단조 증가하는 `planner.cache_epoch`이 바뀐다. Runtime/GUI 분석 캐시는 이 epoch를 key에 포함하므로 planner cache만 비운 뒤 낡은 ShapeType/GoalAnalysis가 재사용되지 않는다.

## Provider revision 계약

provider는 의미나 후보 순서가 바뀌면 다음 중 하나를 올려야 한다.

```python
cache_token = "stack-frontier-v3"
# 또는
version = "3"
```

token을 변경하지 않고 provider 내부 설정을 바꾸면 캐시 일관성을 보장할 수 없다.

## 비용 모델

한 planner 인스턴스의 CostModel은 불변으로 취급한다. 비용 정책을 바꿀 때는 새 planner를 만들거나 `clear_cache()`를 호출한다. raw provider cache는 이론상 공유 가능하지만, 현재 공개 API는 잘못된 min proof 재사용을 막기 위해 derived cache와 함께 폐기한다.

## 메모리 정책

현재 캐시는 명시적 무효화형이다. proof 자료를 임의 LRU로 제거하면 GUI의 분석→공정트리 변환 중 재탐색이 발생할 수 있기 때문이다.

향후 장시간 서버 모드에서는 다음을 별도 정책으로 추가할 수 있다.

- goal graph 세대별 eviction
- raw candidates 디스크 spool
- proof node hash-consing
- maximum cached goal budget

이 정책은 논리 의미와 분리하며, eviction은 `UNKNOWN/IMPOSSIBLE` 의미를 바꾸지 않는다.

## 동시 요청

`GenerationalCache.get_or_create()`가 provider evaluation state를 원자적으로 intern한다. 동일 goal/provider/context를 여러 GUI worker가 동시에 요청해도 raw `inverse()`를 시작하는 state는 하나뿐이다. provider iterator 소비는 state별 `RLock`으로 직렬화한다. 48개 동시 `solve_exists` 회귀 테스트에서 actual inverse call은 1회였다.
