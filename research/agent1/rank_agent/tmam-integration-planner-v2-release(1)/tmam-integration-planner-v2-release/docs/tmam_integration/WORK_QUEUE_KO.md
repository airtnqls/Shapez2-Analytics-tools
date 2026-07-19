# tmam-integration 작업 큐

## 7. Family closure / minimization

- [x] DFA 최소화
- [x] product union/intersection/difference
- [x] 최단 구별 suffix
- [x] explicit fixed-point audit
- [x] rank family stabilization 기록
- [ ] upstream Half/Stack/PP automaton 실제 상태에 적용
- [ ] rank별 상태 증가 실측
- [ ] residual congruence 증명 템플릿 완성

## 8. Proof tree + cost

- [x] immutable ProofNode
- [x] progress 감소 검증
- [x] forward replay validator
- [x] JSON/dict 직렬화
- [x] tree / critical-path cost
- [x] unique-shape metrics
- [ ] 실제 GUI ProcessTree node adapter 연결
- [ ] in-game building footprint cost profile 확정
- [ ] color/provenance certificate 통합

## 9. 기존 ShapeType mapping

- [x] stable legacy enum key
- [x] strict Claw 정의 기반 mapping
- [x] Corner trait 조합
- [x] Hybrid/Complex를 proof depth로 정의
- [x] incomplete와 impossible 분리
- [ ] legacy classifier 전체 회귀 corpus shadow 비교
- [ ] 의도된 동작 변경 목록 승인
- [ ] i18n reason text 최종 연결

## 10. 전체 TMAM

- [x] plugin registry
- [x] completeness manifest
- [x] memoized AND/OR planner
- [x] possible-last-operation 분석
- [x] runtime/bootstrap
- [x] provider acceptance testkit
- [ ] core-kernel plugin 연결
- [ ] corner-half plugin 연결
- [ ] generator plugin 연결
- [ ] stack-pp plugin 연결
- [ ] 전체 required relation set 완전성 확정
- [ ] end-to-end proof replay corpus
- [ ] 기존 GUI/API shadow rollout
