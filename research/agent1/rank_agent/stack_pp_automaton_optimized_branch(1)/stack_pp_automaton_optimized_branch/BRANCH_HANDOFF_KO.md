# stack-pp handoff

## 병합 순서

1. `core-kernel`의 row reader/materializer/forward Stack validator 연결
2. `corner-half`의 minimized HalfFamily automaton 연결
3. `StackClosureAutomaton(half_family, top_policy)` 차등검증
4. 필요할 때만 `compile_complete_minimized`
5. PP rank domain에 lower-rank family로 주입
6. fixed-cap cpcp rank 0/1/2 대조

## 선택 기준

- target 한 개: lazy `StackClosureAutomaton`
- 대량 membership + complete graph가 작음: minimized DFA
- witness 필요: `witness()` 또는 target-specific `StackFamilyProductDAG`
- family state가 큼: `corner-half`에서 먼저 exact quotient

## merge blockers

- forward replay callback 누락
- family quotient의 proof contract 누락
- diagnostic build guard를 False로 변환
- PP fixed point 미해결을 전체 TMAM 완료로 표기
