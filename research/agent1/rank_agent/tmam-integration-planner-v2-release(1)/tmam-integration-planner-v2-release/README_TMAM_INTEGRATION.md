# Shapez2 TMAM Integration Branch

담당 범위:

- family closure / generic minimization infrastructure
- proof tree + cost
- 기존 ShapeType mapping
- 전체 TMAM planner orchestration
- 레거시 GUI / ProcessTree bridge

이번 버전은 Planner를 **공유 evaluation graph**로 재구성했다.

## 세 모드

```python
planner.solve_exists(goal)     # 첫 replay-valid proof에서 즉시 종료
planner.solve_min_cost(goal)   # 최소 비용 proof
planner.analyze_all_ops(goal)  # 가능한 마지막 연산 + 분류 facts
```

세 모드는 같은 provider spool, subgoal memo, replay cache를 공유한다.

기존 API도 유지한다.

```python
planner.solve(goal)   # solve_min_cost alias
planner.analyze(goal) # analyze_all_ops alias
```

## 테스트

```bash
python run_tmam_integration_tests.py
```

## Benchmark

```bash
python benchmarks/planner_benchmark.py
```

결과:

- `reports/planner_benchmark.json`
- `reports/planner_benchmark_summary.json`
- `reports/planner_call_graph.dot`
- `reports/planner_metrics_example.json`
- `reports/coverage.txt`

## GUI

```python
service = TMAMApplicationService(runtime)
service.check_possible(...)       # 빠른 버튼
service.minimum_proof(...)        # 최소 비용 경로
service.detailed_analysis(...)    # 분류/가능 연산
service.process_tree_from_analysis(view)
```

GUI와 ProcessTree는 GoalAnalysis/ProofNode를 소비하며 provider나 tracer를 다시 실행하지 않는다.

## 정직한 범위

Planner, cache, proof, classification, GUI bridge는 구현됐다. 실제 전체 TMAM 완성은 다음 상위 provider 병합을 필요로 한다.

- CompactShape + independent forward replay
- Corner/Half/Cut/Swap
- Generator normal form
- family-constrained Stack
- PP-essential rank

partial/missing provider가 있으면 `UNKNOWN`이며 `IMPOSSIBLE`로 오판하지 않는다.
