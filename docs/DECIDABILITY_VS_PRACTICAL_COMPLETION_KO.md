# Main4 PP 판정 경로와 현실적 실행

이 릴리스는 전체 물리 상태를 무차별 열거하지 않는다. PP 입력은 receipt rank 구조를 이용해 유일 역방향 chain을 먼저 제거하고, 실제 분기가 필요한 Rank0 core에서만 frontier를 탐색한다.

## 실행 상한을 줄이는 구조

- no-overflow receipt 구간: 층수에 비례하는 선형 chain 처리
- Rank0 core: row frontier와 실패 상태 memoization
- predecessor 제작성: Swappable 즉시 판정 또는 목표 지향 Stack split
- Proof: 계산된 receipt target 목록을 재사용해 각 edge를 정방향 검증

따라서 빠른 판정, 유형 분석, 제작 과정은 같은 PP 결과를 공유하면서도 필요한 데이터 로딩과 Proof materialization만 분리한다.

## 실패 처리

정상 입력의 PP core와 receipt 후보를 전부 검사했는데 witness가 없으면 `IMPOSSIBLE / pp-closure-exhausted`를 반환한다. timeout, 취소, 파싱 오류는 이 음성 경로로 변환하지 않고 Worker 오류 또는 취소로 분리한다.
