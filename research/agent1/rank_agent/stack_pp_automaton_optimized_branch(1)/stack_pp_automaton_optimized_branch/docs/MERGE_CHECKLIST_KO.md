# 병합 체크리스트

## `core-kernel` 병합 직후

- [ ] `LegacyShapeKernel` 대신 `CompactShapeKernel` adapter 추가
- [ ] `stack` 1–3층 전체 차등검증
- [ ] `pin_push` 1–3층 전체 차등검증
- [ ] 7층 이상 random 100,000건 forward 대조
- [ ] canonicalization이 replay 방향을 바꾸지 않는지 확인
- [ ] progress key 첫 성분이 visible non-crystal 수인지 확인

## `corner-half` 병합 직후

- [ ] `HalfFamily` / `SwappableFamily` adapter 작성
- [ ] `TopPieceFamily` 정의 고정
- [ ] late-filter Stack adapter로 작은 층 정확성 확인
- [x] generic product frontier 구현
- [ ] 실제 HalfFamily automaton 주입
- [ ] late-filter와 product candidate 집합 비교
- [x] family reject가 frontier 중간에 prune됨을 random 500건 대조
- [ ] 실제 HalfFamily에서 pruning benchmark

## Stack closure 완료 게이트

- [ ] 모든 반환 witness forward replay
- [ ] 모든 child family witness 존재
- [ ] arbitrary top recursion 없음
- [x] L1 전체 ownership path 대조
- [x] StackClosure membership L2 전체 65,536 target 대조
- [ ] 실제 HalfFamily의 2층 전체 candidate-set 대조
- [ ] 3–5층 cpcp oracle 대조
- [ ] 7층 이상 생성 witness 대조
- [ ] soundness/completeness 증명 문서 갱신

## PP rank 완료 게이트

- [ ] rank 0 concrete oracle 대조
- [ ] rank 1,2 fixed-cap cpcp 결과 대조
- [ ] same-batch cleanup 결과 대조
- [ ] retained count / true PP count 분리 대조
- [ ] 모든 PinPush parent replay
- [ ] 모든 Stack trace replay
- [ ] seed rank strict decrease 검사
- [ ] discovery order shuffle 결정성 검사
- [ ] timeout/UNKNOWN 미사용

## `tmam-integration`에 넘기기 전

- [ ] public API 이외 private import 없음
- [ ] classifier/i18n/PyQt import 없음
- [ ] `STATUS_KO.md`의 blocker 전부 해소 또는 명시
- [ ] benchmark JSON 생성
- [ ] manifest SHA-256 생성

## Automaton optimization merge checks

- [ ] `LegacyStackClosureAutomaton`과 optimized L2 전체 65,536 target 일치
- [ ] actual HalfFamily로 lazy membership/witness 일치
- [ ] `canonical_state/state_includes`의 수학적 계약 문서 존재
- [ ] `AutomatonBuildLimitExceeded`가 IMPOSSIBLE로 변환되지 않음
- [ ] `accepts(X) == (witness(X) is not None)` property test
- [ ] materialized witness forward `Stack(A,B)==X` 재생
- [ ] complete compiler 사용 전 reachable graph closure 확인
- [ ] compile 후 source build cache 해제 여부 선택
- [ ] metrics를 benchmark artifact에 기록
- [ ] PP rank fixed point 미해결 경계를 릴리스 문서에 유지
