# TMAM Integration 상태

## 이번 버전에서 구현 완료

- `solve_exists / solve_min_cost / analyze_all_ops` 분리
- mode-independent incremental provider result cache
- family context / progress / provider revision / registry generation cache key
- EXISTS lazy early exit
- MIN_COST branch-and-bound와 deterministic tie-break
- operation별 proof/evidence cache
- subgoal positive/negative memo
- independent forward replay gate
- partial/timeout/resource limit → UNKNOWN
- complete+exhausted일 때만 IMPOSSIBLE
- 상세 Planner instrumentation
- call graph DOT export
- generic state interning, reachable pruning, DFA minimization, metrics
- GoalAnalysis → ShapeFacts → 기존 ShapeType mapping
- ProofNode → 기존 ProcessTree `nodes/root_id` 변환
- GUI application service
- legacy `solve/analyze` compatibility aliases
- 실제 6개 Corner 규칙 callback adapter 연결 테스트
- before/after benchmark 및 의미 동치 검사

## 테스트/측정

- 단위·통합 테스트: 44개 통과
- 코드 coverage: 전체 tmam 86%, planner 80%
- benchmark 의미 동치: 45/45
- benchmark 전체 중복 provider inverse: 1,887 → 0

## 아직 상위 브랜치가 제공해야 함

- 실제 CompactShape backend
- 모든 operation의 독립 forward model
- exact Corner/Half provider
- exact Generator provider
- family-constrained Stack provider
- exact PP rank provider
- 전체 completeness manifest

## 완료 판정

이 브랜치는 7–10과 GUI 통합 기반, 그리고 Planner 중복 제거 과제를 구현했다. 실제 전체 TMAM/전층 가능성 언어가 완성됐다는 주장은 하지 않는다.
