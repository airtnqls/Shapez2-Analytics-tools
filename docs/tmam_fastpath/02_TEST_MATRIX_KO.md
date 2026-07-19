# 최적화 검증 매트릭스

## A. 정확성 게이트

### A1. 기존 회귀

- 기존 샘플 전체 verdict/ShapeType 동일
- 과거 UNKNOWN 해소 결과 유지
- Claw 40,171 witness replay 실패 0
- Hybrid 367 decomposition replay 실패 0
- Main4 PP L5/L6/L7 감사 결과 보존

### A2. Fast-path differential

각 fast constructor에 대해:

```text
fast.match(target) == success
=> fast proof primitive replay == target
=> generic solver verdict == POSSIBLE
```

fast-path가 match하지 않은 것은 음성 증거로 사용하지 않는다.

### A3. 소층 exhaustive

가능한 cap에서 모든 구조 target을 열거해 다음을 비교한다.

- fast verdict vs exact oracle
- fast witness replay
- generic solver vs exact oracle
- fast subtype 과매칭
- symmetry 회전 4방향 일관성

불일치가 나오면 최소 layer, 최소 occupied cell, 사전순 shape 순으로 최소 반례를 저장한다.

---

## B. 성능 게이트

모든 benchmark는 warm/cold를 분리한다.

### B1. 시간

측정:

- parse/normalize
- feature scan
- 각 fast compiler
- certified table lookup
- Main4 PP
- generic providers별 inverse
- replay
- proof lowering
- graph adapter
- layout
- node preview materialization

p50/p95/max와 호출 횟수를 모두 저장한다.

### B2. 작업량

시간만 보지 않고 결정론적 작업량도 측정한다.

```ts
interface SolverMetrics {
  rowsInspected: number;
  candidatesGenerated: Record<string, number>;
  providerInverseCalls: Record<string, number>;
  goalsSolved: number;
  goalCacheHits: number;
  negativeCacheHits: number;
  replayChecks: number;
  proofNodes: number;
  proofEdges: number;
  materializedShapes: number;
  materializedCells: number;
  graphLayoutNodes: number;
}
```

### B3. 성장률

동일 family를 L=10,20,50,100,200,500에서 측정한다.

- inspected rows / L
- candidates / L
- proof nodes / L
- stored cells / L
- elapsed / L

배율이 계속 증가하면 O(L) fast-path로 인정하지 않는다.

---

## C. 필수 Fixture

### C1. Periodic Half

```text
SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:
SuSu----:--Su----:SuSu----:--Su----:cwSu----
```

기대:

- subtype `HALF_PERIODIC_PIN_SWAP`
- generic planner 호출 0
- 구조 scan ≤2L
- 상위 공정 직선형
- primitive replay 통과
- 기준선 대비 node 50% 이상 감소

### C2. Receipt tower

```text
--PP 반복 + buildable core
```

기대:

- receipt prefix 한 번만 스캔
- core solve 1회
- PinPush append k회
- 중간 core 재분류 0

### C3. Simple Stack

유일 ownership boundary가 있는 family.

기대:

- 모든 split height 후보 생성 금지
- split 후보 상수 개
- bottom/top solve 각 1회

### C4. Swappable

두 half가 직접 constructor로 닫히는 family.

기대:

- swap inverse 전체 열거 0
- source half 두 개 + Swap 1회

### C5. Claw/복잡 PP

fast registry가 잘못 가로채지 않는지 확인한다.

기대:

- fast match 실패
- certified Claw/Hybrid 또는 Main4 PP로 전달
- 기존 proof/replay 유지

---

## D. 과매칭·적대적 테스트

각 accepted fixture에서 다음 mutation을 생성한다.

- 임의 한 cell S/-/P/c 치환
- crystal event 한 층 이동
- support spine 한 칸 제거
- block 길이 한 칸 삽입/삭제
- 첫/마지막 층 변형
- 90/180/270도 회전
- cap 경계 ±1
- 중간 empty layer 삽입

Fast compiler가 거부하거나, 성공 시 primitive replay로 정확히 증명해야 한다. 구조 문자열 재조립만 맞는 것은 충분하지 않다.

---

## E. 모드 분리 테스트

### FAST

- proofNodes == 0
- replayChecks는 verdict에 꼭 필요한 최소치만
- full witness table load == false
- graph adapter/layout 호출 0

### ANALYSIS

- subtype/reason 반환
- compact decomposition metadata 허용
- proof lowering/layout 호출 0

### CONSTRUCTION

- compact proof 생성
- replay 통과
- 최초 응답 시 materializedShapes가 전체 노드 수보다 현저히 작음
- node 선택 후 필요한 shape만 증가

---

## F. 실패 시 정책

- timeout을 IMPOSSIBLE로 해석 금지
- fast compiler 내부 오류는 generic fallback + telemetry
- replay 실패 fast proof는 폐기하고 회귀 fixture로 저장
- verdict mismatch는 배포 차단
- 성능 목표 미달은 정확성 통과와 별도로 명시

---

## G. 보고서 JSON

```json
{
  "schema": 1,
  "revision": "...",
  "fixtures": {},
  "verdict_mismatches": [],
  "replay_failures": [],
  "fastpath": {
    "hit_rate": 0,
    "fallback_rate": 0,
    "by_subtype": {}
  },
  "metrics": {
    "cold": {},
    "warm": {},
    "growth": []
  },
  "ui": {
    "fast_proof_nodes": 0,
    "analysis_graph_lowerings": 0,
    "construction_initial_materialization_ratio": 0
  }
}
```
