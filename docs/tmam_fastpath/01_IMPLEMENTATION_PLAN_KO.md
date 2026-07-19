# 2.1.0 Focused UI + Main4 PP 최적화 구현 계획

## 1. 절대 보존 조건

기준 산출물은 `Shapez2-TMAM-Web-Studio-2.1.0-Focused-UI-Main4-PP.zip`이다.

다음은 그대로 유지한다.

- Focused UI 화면 구조와 도형 편집기
- `fast verdict / analysis / construction` 3모드
- 기존 ShapeType 및 결과 계약
- Main4 PP receipt-chain/overflow-terminal 판정
- 양성 proof의 forward replay gate
- DAG와 Tree의 의미 차이

최적화 때문에 verdict나 실제 공정이 달라지면 안 된다. fast-path가 실패하거나 replay에 실패하면 기존 generic 경로로 안전하게 내려간다.

---

## 2. 목표 파이프라인

```text
normalize once
  -> cheap structural facts once
  -> FastStructuralCompiler registry
       Basic
       Corner
       Half subtypes
       Swappable
       Simple Stack
       no-overflow PP receipt
  -> certified Claw/Hybrid
  -> Main4 general PP
  -> generic planner fallback
```

핵심 원칙은 단순 도형에서 generic planner를 더 빠르게 만드는 것이 아니라 **generic planner를 호출하지 않는 것**이다.

---

## 3. 공통 O(L) Feature Scan

모든 fast constructor가 각자 shape를 다시 파싱하지 않는다. 다음 구조를 한 번 생성한다.

```ts
interface StructuralFeatures {
  normalizedCode: string;
  cap: number;
  layers: readonly CompactLayer[];
  occupiedMaskByLayer: readonly number[];
  shapeMaskByLayer: readonly number[];
  pinMaskByLayer: readonly number[];
  crystalMaskByLayer: readonly number[];
  pillars: readonly PillarWord[];
  halfOrientations: readonly HalfView[];
  receiptPrefixLength: number;
  crystalEvents: readonly CrystalEvent[];
  stableCutMask: number;
  candidateStackBoundaries: readonly number[];
  symmetryClass: number;
}
```

계약:

- 파싱/정규화/기둥 추출을 요청당 1회만 수행
- 배열은 immutable typed array 또는 compact integer mask 사용
- 회전 네 방향 전체 문자열을 만들지 말고 회전 view/index mapping 사용
- feature 계산량과 메모리는 O(L)

---

## 4. FastStructuralCompiler Registry

```ts
interface FastConstructor {
  readonly id: string;
  readonly priority: number;
  match(features: StructuralFeatures): FastMatch | null;
  compile(match: FastMatch, mode: SolveMode): CompactProof | null;
}
```

후보 수는 shape 길이와 무관한 상수여야 한다. 등록된 compiler를 모두 실행해도 `O(KL)=O(L)`이다.

### 4.1 Basic

- 빈 도형, 원시 입력, 단순 회전/색칠/절단
- 즉시 leaf 또는 짧은 proof 반환

### 4.2 Corner

- 기존 19-state DFA 또는 최신 Corner automaton 사용
- membership만 반환하지 말고 transition action을 함께 저장
- accepted path에서 concrete constructor schedule을 직접 합성

### 4.3 Half subtype registry

Half를 단일 generic family로 처리하지 않는다. 내부 subtype은 외부 ShapeType과 독립이다.

최소 시작 subtype:

```text
HALF_DIRECT
HALF_MONOTONE_STACK
HALF_SINGLE_SWAP
HALF_NO_OVERFLOW_PIN
HALF_PERIODIC_PIN_SWAP
HALF_EVENT_SEQUENCE
```

각 subtype은 반드시 다음을 제공한다.

- O(L) recognizer
- canonical sequential program
- replay 가능한 primitive lowering
- 거부 이유
- generic fallback 여부

`HALF_PERIODIC_PIN_SWAP` 첫 검증 target:

```text
SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:
SuSu----:--Su----:SuSu----:--Su----:cwSu----
```

인식 방식:

1. permanent support spine 확인
2. crystal event 위치 수집
3. event gap으로 period 결정
4. suffix를 한 번 선형 검증
5. `SEED + block macro * repeats` 합성

모든 가능한 period를 중첩 반복 검사하면 안 된다. KMP/Z/rolling-state 또는 event-gap 기반으로 최악 O(L)을 유지한다.

### 4.4 Swappable

- 네 방향 cut stability를 feature scan에서 계산
- source halves가 fast constructor로 직접 구성되면 Swap 한 번으로 종료
- 역연산 후보 전체 나열 금지

### 4.5 Simple Stack

- 모든 split height를 재귀 solve하지 않는다
- support ownership/낙하 경계 변화로 구조적으로 유일한 split을 찾는다
- 유일하거나 상수 개 후보일 때만 fast-path
- 모호한 경우 generic Stack closure로 fallback

### 4.6 no-overflow PP receipt

- receipt layer를 하나씩 제거하며 전체 solve를 재호출하지 않는다
- prefix length를 한 번 계산
- core를 한 번 solve
- `PinPush × receiptCount` proof를 선형으로 append

---

## 5. Planner 호출 순서

```ts
function solve(goal, mode) {
  const features = featureCache.getOrCreate(goal);

  const fast = fastRegistry.compileFirstReplayable(features, mode);
  if (fast) return fast;

  const certified = certifiedClawHybrid(goal, mode);
  if (certified) return certified;

  const pp = main4PP(goal, mode);
  if (pp) return pp;

  return genericPlanner(goal, mode);
}
```

주의:

- fast compiler 결과는 forward replay 통과 전까지 채택하지 않는다.
- fast compiler의 음성은 전체 도형 음성이 아니다. 단지 해당 subtype 불일치이다.
- generic fallback 결과와 verdict가 다르면 회귀 실패로 처리한다.

---

## 6. 모드 분리

### FAST_VERDICT

허용:

- normalize
- structural feature scan
- membership/verdict compiler
- 작은 goal index

금지:

- proof node 생성
- 전체 witness table load
- graph layout
- 중간 shape materialization
- min-cost planner

### ANALYSIS

추가 허용:

- subtype, 이유, 마지막 연산 후보
- compact decomposition metadata

금지:

- 전체 proof graph lowering
- Tree clone
- 모든 중간 shape render data

### CONSTRUCTION

추가 허용:

- chosen compact proof lowering
- forward replay
- lazy DAG graph adapter

세 모드가 같은 함수에서 옵션만 바꾸는 형태여도 실제 expensive branch가 실행되지 않았음을 metrics로 검증해야 한다.

---

## 7. Proof IR 최적화

기존처럼 각 node에 전체 shape 문자열을 저장하면 공정 O(L)에서도 저장량 O(L²)이 된다.

권장 IR:

```ts
interface CompactProofNode {
  id: number;
  parentIds: readonly number[];
  op: OperationKind;
  args: CompactOpArgs;
  delta: readonly LayerDelta[];
  resultHash: bigint;
  replayStatus: ReplayStatus;
}
```

원칙:

- 전체 shape는 root/checkpoint에만 저장
- 일반 node는 parent + changed rows/cells만 저장
- 일정 간격 checkpoint로 임의 node materialization 비용 제한
- node 선택/화면 표시 때만 shape reconstruct
- DAG adapter와 Tree adapter는 동일 compact proof를 읽음
- Tree는 UI view에서만 사용 위치별 복제하고 core proof는 복제하지 않음

---

## 8. 캐시

캐시 계층:

```text
ParseCache
FeatureCache
FastMatchCache
ProviderCandidateCache
GoalVerdictCache
CompactProofCache
ReplayCache
MaterializedShapeCache (bounded)
```

키에는 반드시 다음을 포함한다.

- normalized shape
- cap
- solver mode 중 의미에 영향을 주는 부분
- physics version
- provider/compiler version token
- cost model version

Fast verdict 결과가 construction proof로 잘못 재사용되거나, cost 정책 변경 후 과거 proof가 남으면 안 된다.

---

## 9. Generic Planner 최적화

fast-path 밖에서도 다음을 적용한다.

- `solve()`와 `analyze()`가 provider inverse를 중복 호출하지 않게 shared evaluation graph 사용
- positive/negative subgoal memoization
- 같은 target/provider/context inverse iterator 공유
- 존재 판정에서는 첫 replayable witness에서 종료
- min-cost mode에서만 branch-and-bound
- 실패 후보의 negative cache
- symmetry canonicalization은 문자열 4개 생성 대신 compact mask 비교
- candidate iterator는 cheap score 순으로 lazy yield
- 전체 후보 list materialization 금지

---

## 10. UI/DAG materialization

- construction 완료 직후 모든 node preview를 렌더하지 않는다
- viewport에 보이는 node만 shape preview materialize
- minimap은 node bounding box만 사용
- 검색 index에는 shape hash/subtype/op만 우선 저장
- 상세 shape code는 선택 시 생성
- Tree 전환은 전체 deep clone 대신 virtual occurrence id 사용

---

## 11. 완료 기준

최적화 완료라고 말하려면 모두 충족해야 한다.

1. 기존 결정 verdict mismatch 0
2. 모든 positive witness primitive forward replay 통과
3. fast-path와 generic fallback differential mismatch 0
4. 제공 Half target DAG node 50% 이상 감소
5. 제공 Half target materialized cell 45% 이상 감소
6. 반복 family 2~256에서 inspected rows ≤ 2L 또는 명시한 상수배 L
7. fast verdict에서 proof node 생성 0
8. analysis에서 graph lowering 0
9. construction에서 lazy materialization 동작
10. generic fallback 호출률과 provider inverse call 수 보고
11. 메모리/시간 benchmark JSON 저장
12. 실패 사례 최소화 및 regression fixture 추가
