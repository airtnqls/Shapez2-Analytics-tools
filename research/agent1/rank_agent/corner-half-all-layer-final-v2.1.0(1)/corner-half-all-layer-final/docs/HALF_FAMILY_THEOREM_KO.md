# 전층 Half Family 완전 특성화

## 1. 정리

quad mode의 east half를 인접한 두 열 `H=(u,v)`라 하자. 다른 두 열은
비어 있다. 임의의 유한 cap `L`에 대해 다음이 동치이다.

> **Half 정리**
>
> `H`가 제작 가능하다
>
> iff
>
> 1. `u`가 Corner 언어에 속하고,
> 2. `v`가 Corner 언어에 속하고,
> 3. 두 열을 합친 `H`가 물리적으로 안정하다.

중요하게도 이는 `Corner(u) ∧ Corner(v)`만이 아니다. 두 열의 수평 지지와
crystal hanging을 포함한 **공동 안정성**이 필수이다.

`half_family.py`가 이 조건을 그대로 구현한다.

## 2. 필요성

제작 가능한 모든 operation output은 gravity 이후 안정 상태이다. 따라서
Half는 안정하다.

또한 제작 가능한 full/half shape의 각 열은 제작 가능한 shape에 실제로
나타나는 열이다. 전층 Corner 정리에 의해 각 열은 Corner DFA 언어에
속한다. 따라서 세 조건은 모두 필요하다.

## 3. 충분성

`u`, `v`가 Corner 언어에 있고 `H=(u,v)`가 안정하다고 가정한다.
높이 `L`의 solid normal tower를 `T=S^L`라 쓰자.

### 3.1 두 prefab

Corner constructor와 helper exchange lemma로 다음 두 buildable shape를
만든다.

```text
X east half = (v, T)
Y west half = (T, u)
```

두 prefab은 안정하다.

- T는 grounded vertical chain이다.
- target column의 ordinary/crystal float는 T가 수평 지지한다.
- pin은 Corner 규칙 `-P` 부재 때문에 바닥 또는 점유 셀 위에 있어
  수직 지지를 받는다.

반대쪽 half의 내용은 Cut에서 버리므로 임의의 안전 helper여도 된다.

### 3.2 Swap

X와 Y를 Swapper에 넣고 X east + Y west 출력을 선택하면

```text
(v, T, T, u)
```

를 얻는다. 입력의 kept halves는 안정하며 빈 반대쪽과 crystal cut pair를
만들지 않는다. recombination은 gravity를 요구하지 않는다.

### 3.3 Rotate + Cut

한 번 시계방향 회전하면

```text
(u, v, T, T)
```

이다. Cutter로 east `(u,v)`를 남긴다.

cut boundary의 반대편은 `T,T` normal tower이므로 crystal–crystal 경계가
없고 target crystal이 shatter되지 않는다. Cut 후 east half에 gravity가
적용되지만 가정상 H가 안정하므로 변하지 않는다. 결과는 정확히 H이다.

따라서 세 조건은 충분하다.

## 4. cpcp Ops 1–6과의 관계

cpcp HalfSet은 seed, Pin Push, stack-layer, boundary crystal break,
rotation projection, quad crystal-column route, cross-boundary stacking closure로
구성된다. 위 정리는 이 concrete closure 전체의 **동치인 축약 표현**이다.

- cpcp가 생성한 모든 half는 제작 가능하므로 필요성에 의해 정리 조건을
  만족한다.
- 정리 조건을 만족하는 모든 half는 위 직접 constructor로 제작되므로
  cpcp의 완전한 HalfSet에 포함되어야 한다.

즉 전층 구현은 Ops 1–6을 도형 집합으로 미리 나열할 필요가 없다.
19상태 Corner DFA 두 번과 폭2 안정성 BFS 한 번으로 같은 family를 직접
판정한다.

## 5. 판정과 certificate

```python
analysis = analyze_half(code, L)
analysis.buildable

result = HALF_FAMILY.witness(code, L)
certificate.operation == HalfOp.CORNER_PAIR

construction = construct_half(code, L)
construction.replay_ok
```

certificate 부모는 방향을 보존한 `(u,v)`이다. `canonical_code`는 두 열을
교환한 half symmetry까지 고려한 최소 코드이다.

## 6. 복잡도

- 두 Corner DFA: `Θ(L)`
- 폭2 support reachability/stability: `Θ(L)`
- 따라서 membership: `Θ(L)` 시간, `O(L)` 입력 저장 공간
- streaming representation을 사용하면 작업 상태는 `O(1)`로 줄일 수 있다.
- constructor certificate: 두 Corner certificate와 고정된 Swap/Rotate/Cut,
  출력 크기까지 포함해 최소 `Ω(L)`이며 현재 `O(L²)` 이하이다.

명시적 L층 입력은 모든 층을 읽어야 하므로 membership의 `Θ(L)`는
점근적으로 최적이다.

## 7. 검증

cpcp가 공개한 orientation-inclusive HalfSet 정확 개수와 정리의 개수를
비교했다.

| cap | craftable columns | theorem half count | cpcp HalfSet |
|---:|---:|---:|---:|
| 1 | 4 | 16 | 16 |
| 2 | 14 | 181 | 181 |
| 3 | 47 | 1,796 | 1,796 |
| 4 | 152 | 16,193 | 16,193 |
| 5 | 476 | 135,074 | 135,074 |
| 6 | 1,450 | 1,058,849 | 1,058,849 |
| 7 | 4,320 | 7,905,398 | 7,905,398 |

추가 constructor 검증:

- cap4의 16,193개 buildable half 전체 replay 실패 0
- cap5–80 무작위 buildable half 10,000개 replay 실패 0
- 폭2/폭4 structural operation 전수 소형 상태 비교 실패 0

개수 일치는 증명이 아니라 강한 독립 감사이다. 완전성은 §3의 직접
construction으로 성립한다.

## 8. 최소 symbolic recognizer

위 세 조건을 별도 함수로 매번 계산할 필요는 없다. 두 19-state Corner DFA와
6-state stability DFA의 product를 최소화한 210-state DFA가 정확히 같은
언어를 인식한다. 자세한 증명과 minimality certificate는
`HALF_SYMBOLIC_CLOSURE_MINIMALITY_KO.md`에 있다.

runtime `is_buildable_half()`와 `HALF_FAMILY.contains()`는 이 frozen 210-state
DFA를 사용하고, `witness()`만 reject 이유와 constructor parent를 위해 semantic
analysis를 복원한다.

## 9. Cut/Swap inverse

Half 정리는 단순 membership에서 끝나지 않는다.

- 모든 accepted Half는 canonical buildable Cutter parent를 갖는다.
- full target은 두 cutter 축 중 하나에서 양쪽 geometric half가 이 Half
  family에 속할 때 그리고 그때에만 Swapper inverse를 갖는다.

구현과 증명은 `CUT_SWAP_HALF_INVERSE_KO.md`에 있다.
