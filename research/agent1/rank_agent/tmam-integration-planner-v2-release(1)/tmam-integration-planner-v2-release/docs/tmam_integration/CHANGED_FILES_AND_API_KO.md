# Planner v2 변경 파일과 병합 API

## 핵심 신규 파일

- `tmam/cache.py`: canonical goal/provider/candidate cache key와 명시적 무효화.
- `tmam/instrumentation.py`: inverse/subgoal/cache/candidate/replay/cycle/comparison 계측과 DOT.
- `tmam/gui_bridge.py`: GUI가 목적별 Planner API를 호출하는 단일 service.
- `tmam/process_tree_adapter.py`: 이미 생성된 ProofNode를 classifier 재실행 없이 기존 ProcessNode 형식으로 변환.
- `tmam/provider_adapter.py`: 함수형/레거시 provider adapter와 실제 Corner 6규칙 representative adapter.
- `tmam/state_tools.py`: state interning, reachable pruning, automaton metrics.
- `benchmarks/legacy_planner_reference.py`: 최적화 전 planner 동결본.
- `benchmarks/planner_benchmark.py`: 5 scenario × 3 mode × 3 repeat × before/after.

## 핵심 수정 파일

- `tmam/planner.py`: 공유 evaluation graph와 세 모드.
- `tmam/contracts.py`: FamilyContext, partial/resource-limit 계약, provider diagnostics.
- `tmam/runtime.py`: GoalAnalysis/ShapeFacts/ShapeType 단일 계산과 cache epoch 연동.
- `tmam/facts.py`: operation evidence에서 strict Claw/PP rank/Stack depth 파생.
- `tmam/proof.py`: deterministic legacy `nodes/root_id` DAG 변환.
- `tmam/enums.py`: public `POSSIBLE / IMPOSSIBLE / UNKNOWN`.
- `tmam/registry.py`: generation 기반 자동 invalidation.

## 상위 provider가 구현할 최소 계약

```python
class Provider:
    provider_id: str
    operation: Operation
    priority: int
    cache_token: str

    def inverse(self, goal: Goal) -> InverseBatch:
        ...
```

필수 조건:

1. 후보 순서 결정론적.
2. lazy iterable 권장.
3. child Progress 엄격 감소.
4. family 의미는 `goal.family_context`에 포함.
5. complete이면 iterator가 전 관계를 exhaustive하게 열거.
6. timeout/resource limit은 partial 또는 예외로 UNKNOWN 전달.
7. certificate는 독립 ForwardModel로 replay 가능.

## GUI 호출 계약

```python
service.check_possible(...)       # solve_exists
service.minimum_proof(...)        # solve_min_cost
service.detailed_analysis(...)    # analyze_all_ops + ShapeType
service.process_tree_from_analysis(view)  # 기존 tree_data
```

모든 화면은 같은 `TMAMRuntime` 인스턴스를 공유해야 한다.
