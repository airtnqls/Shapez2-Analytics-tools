# Planner 호출 그래프

## 이전 구조

```text
GUI analyze
  ├─ planner.solve(target)
  │    └─ 모든 provider.inverse
  └─ operation별 분석
       └─ 같은 provider.inverse 재호출

ProcessTree
  └─ ShapeType별 tracer 재실행
```

## 현재 구조

```text
                         ┌─────────────────────────┐
GUI fast check ─────────▶│ solve_exists            │
GUI min path ───────────▶│ solve_min_cost          │
GUI detail/classifier ──▶│ analyze_all_ops         │
                         └────────────┬────────────┘
                                      │
                              Goal evaluation graph
                                      │
                 ┌────────────────────┼─────────────────────┐
                 │                    │                     │
          provider spool       subgoal result cache   replay cache
                 │                    │                     │
        inverse() exactly once    EXISTS/MIN 공유      candidate당 1회

GoalAnalysis
  ├─ ShapeFacts
  ├─ legacy ShapeType mapping
  ├─ GUI reason/operation list
  └─ ProofNode → legacy ProcessTree data
```

실제 계측 DOT는 `reports/planner_call_graph.dot`에 있다.

## 호출 공유 규칙

- 같은 canonical goal/provider/context의 `inverse()`는 한 번만 호출된다.
- EXISTS가 조기 종료해도 iterator와 읽은 candidate는 보존된다.
- MIN_COST가 같은 iterator를 재개한다.
- ALL_OPS는 operation evidence cache를 조회한다.
- 분류와 ProcessTree는 ProofNode/GoalAnalysis를 소비할 뿐 solver를 호출하지 않는다.
