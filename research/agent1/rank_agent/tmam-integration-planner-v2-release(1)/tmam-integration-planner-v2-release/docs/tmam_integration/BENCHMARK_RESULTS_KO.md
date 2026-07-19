# Planner 최적화 benchmark

원본 데이터: `reports/planner_benchmark.json`
요약: `reports/planner_benchmark_summary.json`

## 구성

각 scenario에서 동일 goal을 1회, 10회, 100회 반복했다.

모드:

- exists
- min_cost
- all_ops

구현:

- before: 최초 tmam-integration planner를 동결한 `benchmarks/legacy_planner_reference.py`
- after: 공유 evaluation graph planner

scenario:

- possible goal
- impossible goal
- shared-subgoal이 많은 goal
- Stack과 Swap이 모두 가능한 goal
- 실제 6개 Corner 금지 규칙을 호출하는 legacy callback adapter

90개 측정 row, 45개 before/after 의미 동치 검사를 수행했다. 전체 행의 단순 중앙 speedup은 0.769×였으며, 이는 trivial cold goal에서 공용 graph/계측 비용이 더 크기 때문이다. 목표 workload인 shared-subgoal, 반복 상세분석, 비싼 provider에서는 아래와 같이 개선됐다.

## 의미 동치

```text
status 동치                          45/45
min-cost가 필요한 모드의 비용 동치  45/45
all-ops possible operation 동치      45/45
실패                                  0
```

## 중복 inverse

45개 비교 전체 합계:

```text
before duplicate provider inverse calls: 1,887
 after duplicate provider inverse calls:     0
```

대표 100회 all-ops:

| scenario | speedup | inverse 감소 |
|---|---:|---:|
| possible | 3.92× | 400 |
| impossible | 5.63× | 400 |
| shared-subgoal | 173.97× | 400 |
| multiple last ops | 8.75× | 400 |
| 실제 Corner 규칙 adapter | 35.87× | 100 |

shared-subgoal cold run:

| mode | speedup |
|---|---:|
| exists | 21.29× |
| min-cost | 1.56× |
| all-ops | 4.65× |

exists는 80개 Stack 후보를 모두 비교하던 before와 달리 첫 replay-valid 후보에서 종료했다.

## 정직한 단점

- 매우 작은 trivial goal의 cold min-cost에서는 새 cache/계측/dataclass 관리 비용 때문에 구 planner보다 느린 측정도 있다.
- raw candidates와 operation evidence를 보존하므로 일부 min-cost 사례에서 peak memory가 증가한다.
- 이것은 반복 분석, GUI, shared-subgoal, 비싼 provider 호출을 줄이기 위한 의도된 교환이다.

따라서 전체 행의 단순 median speedup보다 다음을 핵심 지표로 본다.

1. duplicate inverse call 0
2. EXISTS 후보 조기 종료
3. ALL_OPS 반복 분석의 큰 감소
4. 45/45 의미 동치
5. 실제 Corner adapter에서도 중복 제거 확인

## 한계

실제 Corner adapter를 연결했지만 Stack/PinPush/Generator 전체 provider는 아직 상위 브랜치 산출물이 아니다. 이 benchmark는 Planner 중복 제거 성능을 검증하며, 전체 TMAM 성능을 주장하지 않는다.
