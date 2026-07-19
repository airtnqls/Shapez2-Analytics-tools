# Solver Coverage Manifest — Main4 PP

| 관계 | 양성 witness | 음성 소진 | 웹 backend |
|---|---:|---:|---|
| Parser/normalization | 예 | 예 | TypeScript |
| Forward physics | 예 | 해당 없음 | TypeScript |
| Basic input | 예 | 예 | exact |
| Corner/Half | 예 | 예 | all-layer implementation |
| Swap | 예 | 예 | exact Half product |
| Stack from Swappable | 예 | 예 | target-guided split-height |
| Generator image fact | predecessor check | diagnostic | TypeScript |
| Claw corpus | 예 | table domain | 40,171 replayed parents |
| Hybrid corpus | 예 | table domain | 367 replayed decompositions |
| Pin Push Cap≤2 | 예 | 예 | exhaustive |
| Main4 General PP | 예 | 예 | receipt compression + Rank0 frontier |

## Verdict 계약

- `POSSIBLE`: 실제 constructor/witness가 있으며 정방향 물리 replay가 목표와 일치한다.
- `IMPOSSIBLE`: 모든 기본 family, Stack 경로, Rank0 frontier와 유일 receipt predecessor chain을 소진했다.
- `UNKNOWN`: 정상 판정 결과로 사용하지 않으며, 외부 중단·호환 데이터 등 비정상 상태를 표현하기 위한 타입 호환값으로만 남긴다.

## PP 실행 경로

1. Bottom Pin Receipt Rank를 계산한다.
2. 역방향이 유일한 no-overflow receipt edge를 최대한 제거한다.
3. 가장 깊은 core부터 Rank0 overflow frontier를 검사한다.
4. predecessor가 단순 Swappable이 아니면 목표 지향 Stack witness를 복원한다.
5. 양성은 predecessor부터 최종 target까지 각 Pin Push를 다시 실행한다.
6. 모든 core 후보가 실패하면 `pp-closure-exhausted`로 닫는다.
