# TMAM 전경로 최적화 자료 묶음

이 디렉터리는 `Shapez2-TMAM-Web-Studio-2.1.0-Focused-UI-Main4-PP`에 성능 개선을 적용하기 위한 **구현 지침, 실험 코드, 테스트 계약, GPT 작업 프롬프트**를 모은다.

## 목표

- 단순 비-Claw 도형은 탐색하지 않고 구조를 한 번 읽어 `O(L)`에 판정·공정 합성한다.
- Claw/복잡 PP만 일반 엔진으로 보낸다.
- 빠른 판정, 분석, 전체 제작 과정을 실제 실행 경로와 데이터 로드 수준에서 분리한다.
- 제작 그래프가 정답을 유지하면서 불필요하게 커지지 않도록 proof IR과 materialization을 바꾼다.
- 최적화는 추측이 아니라 replay, 소층 exact differential