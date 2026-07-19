# Corner/Half 원재료 증명 DAG

## 1. 목적

compact Corner/Half certificate가 단지 “이 helper를 사용할 수 있다”고
참조하는 데 그치지 않고, 모든 helper를 실제 Shapez 2 연산으로 재귀적으로
펼쳐 원재료까지 도달함을 보인다.

완전 전개된 증명 DAG의 유일한 잎은 다음 한 종류이다.

```text
RAW_INPUT = 한 층 SSSS
```

그 밖의 모든 노드는 정확히 다음 연산 중 하나이다.

```text
ROTATE, CUT, SWAP, STACK, GENERATE, PIN_PUSH
```

Painter는 구조 판정에 영향을 주지 않으므로 구조 DAG 뒤의 색상 provenance
단계로 분리한다.

구현은 `corner_half/proof_dag.py`이다.

---

## 2. 원시 prefab의 종료성

### 2.1 한 칸 S

`SSSS`를 동서로 자르고, 회전하여 다시 자르면 단일 S를 얻는다. 네 방향은
회전으로 얻는다. 따라서 단일 S 증명에는 raw input 이외의 잎이 없다.

### 2.2 빈 도형과 임의의 한 층 S 패턴

단일 S의 빈 반쪽을 취하면 빈 도형을 얻는다. 필요한 위치의 단일 S들을
Stack하면 16가지 한 층 S 패턴을 모두 만든다.

### 2.3 임의의 안정한 S-only 도형

아래 prefix가 이미 만들어졌다고 가정하고, 다음 한 층 S 패턴을 Stack한다.
층 수에 대한 귀납법으로 모든 안정한 S-only 도형을 만든다. 구현은 prefix
proof를 memoize하므로 같은 prefix가 여러 helper에서 공유된다.

### 2.4 단일 Pin

Pin은 raw input이 아니므로 별도 유한 recipe가 필요하다.

1. 단일 S를 Pin Push하여 `P/S` 쌍을 만든다.
2. 다른 세 열에 높이 `L-1`의 S pedestal을 쌓고 Generator로 crystal
   pedestal을 만든다.
3. `P/S` 쌍을 위에 Stack하여 P를 cap 바로 아래에 둔다.
4. 서쪽 crystal trigger를 Swap/Cut하여 pedestal crystal component를
   파괴한다.
5. P가 바닥으로 떨어진 뒤 회전·절단으로 P 한 칸만 고립한다.

`one_pin_proof()`는 이 recipe의 모든 중간 상태를 실제 연산으로 저장하며,
`verify_proof()`가 다시 독립 재생한다.

### 2.5 S/P-only 도형

한 층의 각 P는 위 단일-P 증명, 각 S는 단일-S 증명으로 만든 뒤 합친다.
그 한 층들을 아래에서 위로 Stack한다. 따라서 안정한 S/P-only 도형은
raw input으로 끝나는 유한 DAG를 가진다.

### 2.6 한 번의 Generator로 만들 수 있는 S/c 도형

global height 아래의 모든 셀이 S 또는 c이고, c를 generation 전의 빈칸으로
바꾸었을 때 안정한 S-only seed가 되는 경우:

```text
S-only seed -> GENERATE -> target
```

으로 만든다. 조건에 맞지 않으면 이 shortcut을 사용하지 않고 일반 Corner
증명으로 내려간다.

---

## 3. Natural Corner 증명

Corner 정리의 natural route는 C1~C6 schedule을 생성한다.
`replay_corner_full()`은 각 schedule edge를 실제 4열 Stack/Generator/Cut/
PinPush로 재생해 `before -> after`를 기록한다.

`corner_raw_proof()`는 각 edge의 operand에 대해 `shape_raw_proof()`를 호출한다.
operand가 S-only, S/P-only 또는 one-generation S/c이면 §2 shortcut으로
종료하고, 그렇지 않은 안정한 반쪽은 두 natural Corner child의 exchange
구성으로 내려간다.

`natural_only=True`일 때 event-route child를 명시적으로 거부하므로 natural
증명 내부에서 C7로 되돌아가는 순환은 없다.

---

## 4. Event Corner와 C7 증명

C7 compiler는 post-lift A와 분리된 faller duties를 받아 다음 helper를
공식으로 만든다.

- B: 정적 S tower, faller source 옆은 P.
- C: cap overflow를 일으키는 full crystal trigger.
- D: relay crystal, rider, catcher pin pedestal, static anchor.
- A: 자연 경로로 미리 제작된 target-column snapshot.

C7 predecessor의 두 반쪽은 `(B,C)`와 `(D,A)`이다. 네 열 모두 Corner
언어에 속하고 두 반쪽이 안정함을 검사한다. 그 뒤:

```text
prove(B), prove(C) -> stable half (B,C)
prove(D), prove(A) -> stable half (D,A)
SWAP -> (B,C,D,A)
ROTATE -> (A,B,C,D)
PIN_PUSH -> event result
```

로 전개한다.

핵심 비순환성은 다음과 같다.

1. C7 helper A/B/C/D는 모두 natural-route Corner이다.
2. 따라서 helper proof는 §3에서 종료한다.
3. event target 자신을 child로 호출하지 않는다.
4. 최종 C7 PinPush 뒤에는 compact plan의 post-event C4/C5/C6/C1/C2만 남는다.

그러므로 event Corner도 raw input까지 유한하게 내려간다.

---

## 5. Half 증명

Half 정리는 다음이다.

```text
BuildableHalf(u,v)
<=> Corner(u) and Corner(v) and Stable(u,v)
```

충분성의 raw DAG는:

1. `C(u) = (u,T,T,T)`와 `C(v) = (v,T,T,T)`를 각각 Corner raw proof로
   만든다.
2. Cut/Rotate로 `(v,T)`와 서쪽 `(T,u)` fixture를 얻는다.
3. Swap하여 `(v,T,T,u)`를 만든다.
4. Rotate하여 `(u,v,T,T)`를 만든다.
5. Cut east한다. 경계 반대쪽은 normal tower이므로 crystal shatter가 없고,
   가정한 `(u,v)` 안정성 때문에 gravity도 결과를 바꾸지 않는다.

따라서 Half proof도 두 Corner raw proof와 유한한 Swap/Rotate/Cut suffix로
끝난다.

---

## 6. 독립 verifier

`verify_proof()` / `verify_proof_forest()`는 certificate의 `result`를 믿지
않는다. child 결과에서 각 연산을 다시 실행하여 기록된 결과와 비교한다.
또한 모든 non-empty node에 대해 support closure가 전체 점유 셀을 포함하는지
검사한다.

### 안정성 동치

```text
Stable(X) <=> every occupied cell is in the least support closure of X
```

- 우변이면 shatter/fall 대상이 없으므로 gravity가 X를 바꾸지 않는다.
- 좌변인데 unsupported crystal이 있으면 shatter되어 모순이다.
- unsupported non-crystal이 있다면 가장 낮은 unsupported group을 잡는다.
  그 아래의 unsupported group들은 bottom-up sweep에서 이미 이동했고,
  supported blocker가 바로 아래 있었다면 vertical/horizontal support closure가
  원래 group에도 도달했어야 한다. 따라서 그 group은 양의 거리만큼 이동해
  모순이다.

이 동치는 기존 full gravity 비교와 cap2 전체 65,536상태 및 3~30층 무작위
100,000상태에서 불일치 0으로 차등검증했다.

---

## 7. 복잡도

- Corner membership: 19-state DFA, `Theta(L)` time, `Theta(1)` state.
- Half membership: Corner DFA 두 번 + 2열 support BFS, `Theta(L)` time.
- compact constructor certificate: region 수와 층 수에 선형.
- 완전 materialized raw proof DAG: 출력해야 하는 operation node 수에 비례.
  현재 구현은 prefix memoization으로 반복 prefab을 공유하지만 각 node에 full
  shape string을 저장하므로 audit artifact의 메모리는 core-kernel의 compact
  representation보다 크다.
- `verify_proof_forest()`는 공유 child를 한 번만 재생한다.

runtime membership API는 raw proof 전체를 만들 필요가 없다. raw DAG는
ProcessTree 생성, 논문 검증, 회귀감사용 선택적 witness이다.

---

## 8. 기계 감사 결과

`reports/PROOF_DAG_AUDIT.json`:

- cap7 모든 Corner 4,320개: raw proof forest 전체 재생, 실패 0.
- cap4 모든 Half 16,193개: raw proof forest 전체 재생, 실패 0.
- 189층 event Corner: 4,991 unique nodes, raw leaf 1종, 실패 0.

proof assistant의 kernel proof는 아니지만, 수학적 귀납 증명과 원재료까지
완전히 전개되는 독립 forward replay certificate를 함께 제공한다.

## 9. 상호귀납 의존성의 정식 순서

이 문서의 §3–§5는 구현 순서를 설명했지만, 논리적 비순환성은 다음 여섯
단계로 읽어야 한다.

```text
Direct prefab
 -> Solid Half
 -> Natural Corner
 -> Natural Half
 -> Event Corner
 -> General Half
```

특히 Natural Corner의 helper Half는 모두 gap 없는 solid 열로 구성되며
`proof_dag.py`가 이를 assertion으로 강제한다. C7만 Natural Half를 직접
사용하고, General Half는 모든 Corner가 완성된 뒤 마지막에 사용한다.
자세한 감사와 gap-decrease certificate는
`CORNER_HALF_MUTUAL_INDUCTION_KO.md`에 있다.
