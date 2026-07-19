# 상위 브랜치 병합 계약

각 브랜치는 다음 entry point를 제공한다.

```python
def register_tmam_plugin(registry):
    registry.register_relation(...)
    registry.register_family(...)
    registry.register_plugin(...)
```

## core-kernel

```python
backend: ShapeBackend[CompactShape]
forward: ForwardModel[CompactShape]
```

forward replay는 inverse 구현과 독립이어야 한다. Planner의 POSSIBLE은 replay 통과 없이는 나오지 않는다.

## Provider

필수:

```text
provider_id
operation
priority
cache_token 또는 version
inverse(goal) -> InverseBatch
```

권장:

```python
admissible_lower_bound(goal) -> CostVector
```

`inverse()`는 lazy iterable을 반환해야 EXISTS 조기 종료가 실제 계산 절약으로 이어진다.

## Goal family context

rank/base family/abstraction이 달라지면 별도 context를 사용한다.

```python
Goal(shape, progress, FamilyContext(
    "pp-rank",
    (("rank", 3), ("base_family", "half-stack-2")),
))
```

context가 다른 결과를 같은 cache에 섞으면 안 된다.

## Candidate

- target
- operation
- ordered children
- 엄격히 작은 child progress
- 필요하면 child-specific family context
- independent replay certificate
- local cost
- traits/metadata

## Coverage

`Coverage.complete`는 현재 goal/progress/context에서 담당 역관계를 빠짐없이 열거한다는 수학적 계약이다. 표본 통과나 timeout 미발생은 complete 근거가 아니다.

상세 cache/stream 규칙은 `UPSTREAM_PROVIDER_CACHE_CONTRACT.md`를 따른다.
