# Generator 브랜치 상태

## 완료

- 모든 유한 층수에 동일한 Generator 정의
- 빈 도형과 global height 의미 고정
- exact color 포함 image 필요충분조건
- 모든 전상의 셀별 필요충분조건
- 생산적/no-op 분리
- crystal-count 엄격 감소 증명
- 안정한 single-pin 정규 전상
- family-constrained O(H|Q|) product DP
- 결정적 family 후보 수 계산
- exact witness materialization과 replay certificate
- 현재 `Shape.py` 의미 수정 패치

## 전체 TMAM 통합 전 남은 외부 의존성

- Core branch의 최종 `CompactShape` row encoding
- Half/Stack/PP branch의 deterministic family automaton
- Planner branch의 공통 `ProofNode`/cost 타입

이 셋은 Generator 수학을 변경하지 않고 adapter 수준에서 결합한다.
