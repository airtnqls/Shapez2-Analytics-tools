# Planner 세 모드의 정확한 의미

## 1. `solve_exists(goal)`

목적은 오직 다음 명제이다.

```text
해당 goal을 만드는 replay-valid proof가 하나라도 존재하는가?
```

동작:

- provider 우선순위 순으로 raw inverse stream을 읽는다.
- 후보의 child들을 `solve_exists`로 확인한다.
- 모든 child가 `POSSIBLE`이고 독립 forward replay가 target과 일치하면 즉시 반환한다.
- 이후 provider, 후보, 비용 비교, ShapeType, GUI 사유 문자열, ProcessTree 변환은 수행하지 않는다.
- proof가 없을 때만 모든 필요한 complete provider를 끝까지 소진한다.

결과:

- `POSSIBLE`: replay-valid proof 하나가 발견됨.
- `IMPOSSIBLE`: 모든 필수 provider가 complete이고 실제로 exhausted되었으며 모든 후보가 실패함.
- `UNKNOWN`: partial/missing provider, timeout, resource limit, replay 불가, 미해결 child가 있음.

`POSSIBLE` 반환 시 탐색 전체가 exhausted될 필요는 없다. 존재 증명은 witness 하나로 끝난다.

## 2. `solve_min_cost(goal)`

목적은 등록된 의미 범위 안에서 최소 비용 proof를 선택하는 것이다.

- 모든 경쟁 operation/provider를 비교한다.
- 각 subgoal의 최소 비용 결과를 memoize한다.
- candidate local cost는 자식 비용이 비음수가므로 admissible lower bound이다.
- provider가 `admissible_lower_bound(goal)`을 제공하면 provider 단위 pruning도 수행한다.
- 현재 best보다 엄격히 비싼 lower bound만 제거한다. 동률 후보는 deterministic tie-break를 위해 비교한다.
- tie-break 순서:
  1. `CostModel.ordering_key(total_cost)`
  2. operation 이름
  3. provider ID
  4. provider stream ordinal
  5. child canonical key

필드:

- `status=POSSIBLE`은 proof의 존재가 확정됐다는 뜻이다.
- `optimal=True`일 때만 전역 최소 비용임이 확정된다.
- partial provider가 경쟁할 수 있으면 proof는 가능하지만 `optimal=False`이다.

## 3. `analyze_all_ops(goal)`

목적은 상세 분석과 기존 ShapeType 계산에 필요한 사실 전체를 만드는 것이다.

출력 `GoalAnalysis`:

```python
GoalAnalysis(
    exists_result=...,
    min_cost_result=...,
    operations={Operation: OperationEvidence, ...},
    provider_results={provider_id: ProviderEvaluation, ...},
    classification_facts=...,  # Runtime에서 한 번 계산
)
```

각 `OperationEvidence`는 다음을 보존한다.

- 해당 operation이 가능한지 `True / False / None`
- operation별 최소 proof
- 그 판정이 complete한지
- operation별 cost가 optimal한지
- 사용한 provider snapshot

`analyze_all_ops`는 `solve_min_cost`에서 이미 만든 operation evidence와 raw provider cache를 재사용한다. provider의 `inverse()`를 다시 실행하지 않는다.

## 모드 승격

캐시는 다음 방향으로 승격된다.

```text
EXISTS에서 일부 candidate 소비
        ↓ 같은 provider iterator 재개
MIN_COST에서 필요한 나머지 소비
        ↓ 같은 operation/proof cache 조회
ALL_OPS에서 facts 조립
```

반대 방향도 가능하다.

- MIN_COST 결과가 이미 있으면 EXISTS는 그 proof/status를 즉시 사용한다.
- ALL_OPS 결과가 있으면 세 모드 모두 cache hit이다.

## 기존 API

```python
planner.solve(goal)   # solve_min_cost 호환 alias
planner.analyze(goal) # analyze_all_ops 호환 alias
```

새 코드에서는 목적을 명확히 드러내는 세 이름을 직접 사용한다.
