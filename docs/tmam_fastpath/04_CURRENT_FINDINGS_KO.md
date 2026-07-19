# 현재 실험 결과와 경계

## 실측 완료

첫 target:

```text
SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:
SuSu----:--Su----:SuSu----:--Su----:cwSu----
```

독립 재구현 기준선과 `HALF_PERIODIC_PIN_SWAP` fast compiler 비교:

| 지표 | 기준선 | fast | 감소 |
|---|---:|---:|---:|
| DAG nodes | 32 | 12 | 62.5% |
| DAG edges | 28 | 11 | 60.7% |
| operation nodes | 28 | 9 | 67.9% |
| materialized row-cells | 112 | 53 | 52.7% |

검증:

- target subtype 인식
- 반복 block 정확 복원
- scan count ≤2L
- 반복 2~256에서 fast DAG 선형 성장
- mutation 200개 과매칭 0
- GitHub Actions 통과

## 전체 경로 모형 실험

`optimizer_suite.py`는 다음 구조적 차이를 계측한다.

### Generic candidate planner

- 모든 split height
- 모든 마지막 연산 종류
- prefix rematerialization
- 후보 수 O(L)
- 총 검사/저장 O(L²)

### Constant fast dispatch

- 공통 feature scan
- 상수 개 compiler
- 후보 수 O(1)
- 검사/저장 O(L)

### Eager proof storage

- operation node마다 전체 L-layer shape 저장
- O(L²) cell 저장

### Delta proof storage

- root/checkpoint + changed row delta
- O(L) cell 저장

이 실험은 구조 최적화가 단순 micro-optimization이 아니라 성장 차수를 바꾼다는 것을 검증하기 위한 것이다.

## 아직 미완료

다음은 실측 완료로 주장하면 안 된다.

1. 제공 사진의 모든 중간 shape를 실제 legacy 코드에서 자동 추출한 것
2. `PIN/SWAP/SWAP/PIN` primitive sequence를 production physics로 전부 replay한 것
3. 기존 Focused UI Main4 PP ZIP에 fast compiler를 실제 통합한 것
4. 전체 Half family subtype을 데이터로 군집화한 것
5. 모든 비-Claw family가 O(L) constructor로 닫힌다는 증명
6. production DAG node 수가 독립 실험과 동일하게 줄어든 것

## 다음 증명 순서

1. 기준 ZIP source audit
2. 제공 target의 production baseline 수치 저장
3. 실제 legacy 중간 shape/operation sequence 추출
4. production primitive replay 가능한 첫 Half compiler 구현
5. fast vs generic differential
6. Half corpus signature 수집/군집화
7. subtype별 recognizer/constructor/replay
8. Stack/Swap/Receipt fast compiler
9. compact proof IR/lazy graph
10. 전체 regression/growth/build ZIP

## 채택 기준

하나의 heuristic은 다음을 모두 만족할 때만 production registry에 들어간다.

- recognizer 최악 O(L) 또는 명시한 경계
- concrete primitive proof 생성
- forward replay PASS
- exact/generic differential mismatch 0
- adversarial mutation 과매칭 0
- 실제 DAG/시간/메모리 중 적어도 하나 유의미 개선
- 실패 시 안전한 fallback
