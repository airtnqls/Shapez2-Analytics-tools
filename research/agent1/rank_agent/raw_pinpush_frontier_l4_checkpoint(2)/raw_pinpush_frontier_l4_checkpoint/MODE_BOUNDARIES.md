# 적용 경계 요약

| 논리 | 일반 PP | 진짜 Claw | 최종 UNSAT 근거 | 현재 상태 |
|---|---:|---:|---:|---|
| plain inverse O(L) | 예 | 예 | 해당 분기에서는 예 | 완전 |
| raw frontier O(L^5) | 예 | 예 | 예 | 기준점 |
| eager-column O(L^4) | 후보 | 예 | 아직 아니오 | 전층 증명 미완성 |
| fixed-two-eager O(L^3) | 아니오 | 예 | Claw certificate 아래 예 | Claw 전용 |

일반 PP fixed-point를 연구할 때는 raw frontier를 제거하지 말고,
L4/L3를 각각 feature-flagged accelerator로 유지한다.
