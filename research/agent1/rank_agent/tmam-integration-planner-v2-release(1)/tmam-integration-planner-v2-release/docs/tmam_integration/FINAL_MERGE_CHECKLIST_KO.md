# 최종 병합 체크리스트

## Planner 공유 그래프

- [x] solve_exists / solve_min_cost / analyze_all_ops 분리
- [x] raw inverse mode-independent cache
- [x] 동일 target/provider inverse 중복 0
- [x] subgoal positive/negative memo
- [x] replay cache
- [x] GoalAnalysis에서 classification/ProcessTree 파생

## 상위 provider 계약

- [ ] cache_token/version 존재
- [ ] candidate 순서 deterministic
- [ ] candidates lazy iterable
- [ ] child progress 엄격 감소
- [ ] family context 정확히 전달
- [ ] certificate independent replay 통과
- [ ] timeout/resource limit가 partial/UNKNOWN 처리
- [ ] complete 선언의 전층 증명 문서 존재

## Provider completeness

- [ ] Basic/Input
- [ ] Rotate/Paint normal form
- [ ] Cut
- [ ] Swap
- [ ] Half family
- [ ] Generator normal form
- [ ] family-constrained Stack
- [ ] PP rank

## GUI

- [ ] 같은 TMAMRuntime 인스턴스를 모든 버튼이 공유
- [ ] 빠른 가능성 → solve_exists
- [ ] 최소 경로 → solve_min_cost
- [ ] 상세/분류 → analyze_all_ops
- [ ] ProcessTree는 ProofNode 변환만 수행
- [ ] 기존 타입별 tracer 재실행 제거
- [ ] UNKNOWN 이유 표시

## 검증

- [x] planner unit/integration 44개
- [x] benchmark 1/10/100 반복
- [x] possible/impossible/shared/multi-op scenario
- [x] 실제 Corner 규칙 adapter
- [x] before/after 의미 동치 45/45
- [ ] 실제 상위 provider 병합 후 benchmark 재실행
- [ ] 작은 층 exact oracle 전수 비교
- [ ] 고층 adversarial corpus

## 출시

- [ ] 전체 required provider manifest complete
- [ ] IMPOSSIBLE gate 활성화 승인
- [ ] cache budget/eviction 정책 결정
- [ ] proof/certificate schema version 고정
