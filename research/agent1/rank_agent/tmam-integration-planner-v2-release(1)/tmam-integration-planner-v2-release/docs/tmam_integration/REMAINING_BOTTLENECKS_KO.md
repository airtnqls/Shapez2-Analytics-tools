# 남은 병목과 후속 작업

## 1. Min-cost cold overhead

작은 goal에서는 operation evidence, cache key, instrumentation 비용이 기존 단순 memo보다 크다.

후속 선택지:

- instrumentation off fast path
- provider/operation static lower-bound table
- ProofNode hash-consing
- candidate snapshot의 compact 구조

## 2. 메모리

모드 공유를 위해 raw candidate spool과 proof를 유지한다. 후보가 매우 많은 provider는 메모리를 크게 사용할 수 있다.

후속 선택지:

- provider별 spool budget
- immutable candidate binary encoding
- disk-backed spool
- completed goal graph eviction

단, eviction 후 재계산은 성능 문제일 뿐 POSSIBLE/IMPOSSIBLE/UNKNOWN 의미를 바꾸면 안 된다.

## 3. Provider가 eager한 경우

Planner는 lazy iterable을 전제로 EXISTS 조기 종료 효과를 얻는다. provider가 `inverse()` 안에서 후보 전부를 리스트로 만들면 호출은 한 번이어도 materialization 비용은 남는다.

상위 branch 계약:

```python
return InverseBatch(candidates=generator(), coverage=...)
```

## 4. Lower bound 품질

현재 candidate local cost와 optional provider lower bound를 사용한다. Stack/PP 의미별 강한 lower bound는 4·5 담당 브랜치의 소유이다.

## 5. Concurrent GUI requests

raw provider state 생성은 원자적으로 coalescing되고 iterator는 lock으로 보호되므로 동일 key의 `inverse()` 중복은 제거됐다. 다만 goal 전체 future를 합치는 request coalescing은 아직 없어서 서로 다른 thread가 동일 derived proof 조립을 잠시 중복 수행할 수 있다. 장시간 provider를 GUI에서 병렬 요청할 때는 goal-level future/promise 계층을 추가하는 것이 다음 최적화다.

## 6. 실제 provider 통합 후 재측정

현재 실제 Corner adapter와 representative graph provider로 Planner를 검증했다. 다음 병합 후 반드시 다시 측정한다.

- CompactShape backend
- Half/Cut/Swap
- Generator normal form
- family-constrained Stack
- PP rank

## 7. IMPOSSIBLE 활성화 gate

상위 provider의 complete manifest가 승인되기 전에는 전체 TMAM의 IMPOSSIBLE 정확성을 주장할 수 없다. Planner는 partial/missing을 UNKNOWN으로 유지한다.
