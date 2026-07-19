# 전층 Half symbolic closure와 최소 상태 정리

## 1. 결론

정규화된 quad east-half는 각 층의 두 셀을 한 문자로 본 문자열이다.
층 알파벳은 다음 16개이다.

```text
-- -S -P -c S- SS SP Sc P- PS PP Pc c- cS cP cc
```

맨 위의 `--` 층은 제거한다. 이 언어에 대해 다음이 성립한다.

> **Half Automaton 정리**
>
> 제작 가능한 oriented east-half 전체는 정확히 하나의 최소 DFA로
> 인식되며, 그 최소 상태 수는 **210**이다.

판정은 층을 아래에서 위로 한 번 읽으므로 `Theta(L)` 시간, DFA 작업
메모리 `Theta(1)`이다.

구현은 `corner_half/half_automaton.py`, 생성된 표는
`reports/half_minimal_dfa.json`이다.

---

## 2. 안정성의 6상태 DFA

Half 정리에 의해 필요한 세 조건 중 두 Corner 조건은 각각 기존 19상태
최소 DFA가 처리한다. 남는 것은 두 열의 공동 안정성이다.

공동 안정성은 다음 여섯 상태로 충분하고 필요하다.

| 상태 | 수용 | 의미 |
|---|---:|---|
| `G` | 예 | prefix 전체가 지지되고, top 두 열이 모두 점유되었거나 prefix가 비어 있음 |
| `D` | 아니오 | 미래 층으로도 복구할 수 없는 밀봉된 비지지 성분 또는 내부 빈 층 |
| `R` | 예 | prefix 전체가 지지되고 top의 오른쪽 열만 점유 |
| `L` | 예 | `R`의 좌우 대칭 |
| `UL` | 아니오 | top이 `cP`; 오른쪽 P는 지지되고 왼쪽 crystal 사슬만 미래 지지를 기다림 |
| `UR` | 아니오 | `UL`의 좌우 대칭 |

`UL`에서 가능한 생존 전이는 정확히 다음뿐이다.

```text
cP -> UL       crystal 사슬과 pin frontier 연장
cS -> G        오른쪽 S가 아래 P로 지지되고 왼쪽 c를 수평 지지
cc -> G        같은 이유 + crystal hanging
그 밖 -> D
```

`UR`은 좌우 대칭이다. `G`, `R`, `L`의 전이도 같은 지지 규칙에서 직접
나오며 코드의 `STABILITY_TRANSITIONS`에 전부 명시되어 있다.

### 정확성 증명

층 수에 대한 귀납법을 쓴다.

- 새 셀은 바로 아래의 지지 셀로부터 위쪽 지지를 받는다.
- 같은 층의 두 non-pin은 한쪽이 지지되면 다른 쪽도 지지된다.
- 미래가 과거를 지지할 수 있는 유일한 통로는 top에 열린 수직 crystal
  사슬이다.
- top의 한 열이 비었을 때 반대 열의 고립 crystal은 미래와 연결되어도
  지지된 다른 열과 만날 수 없으므로 `D`다.
- 열린 crystal 사슬 옆에 지지된 pin frontier가 있는 경우만 `UL/UR`로
  남고, 위 표의 `cP/Pc` 연장 또는 `cS/Sc/cc` 해소가 전부다.

따라서 여섯 상태는 각 prefix의 모든 미래 안정성 행동을 보존한다.

이 69개 원시 support-behavior 상태를 언어 동치로 최소화하면 정확히
6상태가 된다.

---

## 3. Corner DFA와의 product

Half family의 전층 정리는 다음이다.

```text
BuildableHalf(u,v)
<=> Corner(u) and Corner(v) and Stable(u,v)
```

따라서 층 `xy`의 전이는 동시에:

```text
left_corner  --x--> next_left
right_corner --y--> next_right
stability    --xy-> next_stability
```

를 수행한다.

원시 상한은:

```text
19 x 19 x 6 = 2,166 states
```

이지만 실제 시작 상태에서 도달 가능한 product state는 **552개**뿐이다.
Hopcroft 분할 정제를 적용하면 **210개**가 된다.

---

## 4. 210이 실제 최소임을 보이는 certificate

단순히 Hopcroft 구현의 반환값을 믿지 않는다.
`audit_minimality()`가 다음 두 조건을 독립적으로 검사한다.

1. 210개 상태가 모두 시작 상태에서 도달 가능하다.
2. 서로 다른 모든 상태 쌍에 대해 수용 여부를 갈라놓는 suffix가 있다.

상태 쌍은:

```text
210 * 209 / 2 = 21,945
```

개이며 전부 구별된다. reverse pair-automaton BFS가 만든 가장 긴 구별
suffix는 9층이다. 모든 상태의 도달 representative는 최대 4층이다.

따라서 Myhill–Nerode 정리에 의해 210보다 작은 deterministic automaton은
이 oriented normalized Half 언어를 인식할 수 없다.

---

## 5. cpcp concrete closure와의 동치 감사

DFA가 세는 cap 이하의 Half 수는 다음과 같다.

| cap | 최소 DFA | cpcp exact HalfSet |
|---:|---:|---:|
| 1 | 16 | 16 |
| 2 | 181 | 181 |
| 3 | 1,796 | 1,796 |
| 4 | 16,193 | 16,193 |
| 5 | 135,074 | 135,074 |
| 6 | 1,058,849 | 1,058,849 |
| 7 | 7,905,398 | 7,905,398 |

cap1..6은 count만 비교한 것이 아니라 exact Half bitset 전체에서 FP/FN 0을
확인했다. 추가로 normalized 높이 0..5의 1,048,576개 half word를 모두
검사하여:

```text
210-state DFA
= Corner(left) & Corner(right) & structural stability
```

불일치 0을 확인했다.

---

## 6. TMAM 병합 의미

이전의 cpcp식 HalfSet 사전 나열은 다음으로 대체된다.

```python
state = HALF_DFA.start
for row in half_rows:
    state = HALF_DFA.step(state, row)
return state in HALF_DFA.accepting
```

- concrete Half DB 불필요
- 층수 제한 불필요
- `UNKNOWN` 없음
- 상태 표현은 전층에서 동일
- `stack-pp` 브랜치는 Half membership을 product state 하나로 곱할 수 있음

210은 현재 API가 다루는 **열 순서가 있는 oriented half**의 최소 상태 수다.
전체 half를 좌우 대칭 canonical code로 저장하는 것은 저장 중복을 줄이지만,
입력 문자열을 그대로 읽는 deterministic recognizer의 210상태 최소성은
변하지 않는다.
