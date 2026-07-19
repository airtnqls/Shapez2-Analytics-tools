# tmam-integration 브랜치 책임 범위

이 브랜치는 다음 네 항목을 소유한다.

- 7. family closure / automaton 최소화 도구
- 8. 제작 증명 DAG, certificate, 비용 모델
- 9. 정확한 내부 사실을 기존 `ShapeType`으로 변환하는 정책
- 10. 전체 TMAM orchestration과 plugin 통합

## 소유하지 않는 것

다음 알고리즘의 물리적 정답 자체는 이 브랜치에서 구현하거나 수정하지 않는다.

- Compact physics kernel
- Corner / Half membership와 constructor
- Generator normal form
- Stack closure
- Pin Push inverse와 PP rank

이들은 각 상위 브랜치가 제공한다. 이 브랜치는 공통 계약을 강제하고, 결합된 결과가 sound/complete인지 판정하며, 최소 제작 증명과 UI 분류를 만든다.

## 절대 규칙

1. timeout은 `IMPOSSIBLE`의 근거가 아니다.
2. 누락된 provider가 하나라도 있으면 부정 판정은 `UNKNOWN`이다.
3. 모든 재귀 child는 `Progress`가 엄격히 감소해야 한다.
4. 최종 proof는 독립 forward replay를 통과해야 한다.
5. 기존 `ShapeType`은 연구 정의가 아니라 UI 호환 라벨이다.
6. 물리 branch와 integration branch가 같은 파일을 동시에 소유하지 않는다.
