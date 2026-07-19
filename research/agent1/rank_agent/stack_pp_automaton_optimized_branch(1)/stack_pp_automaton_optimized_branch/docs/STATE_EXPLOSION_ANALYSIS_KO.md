# Stack/Family automaton 상태 폭발 분석

## 1. 기준 구현

기준 `LegacyStackClosureAutomaton`의 결정 상태는 다음이었다.

```text
(last target row 전체 signature,
 frozenset[(Stack ownership + support history, bottom-family state)])
```

Universal bottom family는 상태가 하나뿐인데도 전체 256행 알파벳을 탐색하면:

| 정확 층수 | reachable state |
|---:|---:|
| 0 | 1 |
| 1 | 256 |
| 2 | 4,019 |

2층에서만 product pair가 18,914개, subset 최대 크기가 17, transition cache가 65,792개였다. `tracemalloc` peak는 76,049,352바이트였다. 3층 전체 탐색은 별도의 300초 진단 실행에서도 끝나지 않았다. 이것은 불가능 판정이나 state cap이 아니라 기준 구현의 성능 관측이다.

따라서 최초 폭발은 family state 때문이 아니다. 기여 순서는 다음과 같다.

1. 같은 물리 의미를 가진 support history가 여러 tuple로 존재
2. 그 history들이 powerset subset에 동시에 남음
3. full previous row signature를 상태에 보존
4. 상태마다 256개의 dense `(state,row)` cache key 생성
5. `frozenset[tuple]`, dataclass edge, tuple cache key의 Python 객체 비용

## 2. support state 증가

기존 width-four support transducer의 reachable concrete boundary state는 2,011개였다. 이것을 256개 구조행을 알파벳으로 하는 완전 DFA로 보고 미래 suffix acceptance가 같은 상태를 분할 정제로 최소화했다.

```text
2,011 raw support states
→ 131 exact residual-language states
```

감소율은 93.49%다. 이 quotient는 샘플 기반 병합이 아니라 모든 256 전이와 final stability acceptance를 사용한 완전 DFA 최소화다.

## 3. previous-row context 증가

다음 B row의 착지 여부는 직전 target row에서 `occupied`인 열만 읽는다. 직전 crystal/pin/normal 차이는 support residual state와 현재 row 안에서 이미 처리된다.

따라서 deterministic state의 previous-row context는:

```text
(occupied, crystal, pin, ordinary) 256종
```

이 아니라:

```text
previous occupied mask 16종
```

만 필요하다. 이는 93.75%의 context alphabet 감소다.

## 4. subset determinization 증가

Support quotient만 적용하고 subset을 모두 유지하면 Universal family에서:

| 정확 층수 | state | 최대 subset |
|---:|---:|---:|
| 0 | 1 | 1 |
| 1 | 81 | 16 이하 |
| 2 | 1,371 | 25 |
| 3 | 8,111 | 25 |

즉 compact ID만으로는 powerset 폭발이 해결되지 않는다.

## 5. 의미 중복과 antichain

같은 deterministic context 안의 product state `p`, `q`에 대해 다음이면 `p`가 `q`의 모든 미래 accepted suffix를 모사한다.

```text
switched(p) ⊆ switched(q)
q가 과거 B를 가졌다면 p도 과거 B를 가짐
has_A(p) ≥ has_A(q)
support_language(p) ⊇ support_language(q)
family_language(p) ⊇ family_language(q)
```

기본 family에서는 마지막 조건을 equality로만 사용한다. family가 증명된 `state_includes()`를 제공할 때만 더 넓은 포함관계를 사용한다.

이 simulation antichain 적용 결과:

| 정확 층수 | no-subsumption | antichain | 감소 |
|---:|---:|---:|---:|
| 1 | 81 | 81 | 0% |
| 2 | 1,371 | 942 | 31.3% |
| 3 | 8,111 | 2,082 | 74.3% |

subset 최대 크기는 25에서 5로 감소했다.

완전 Universal graph에서 실제 제거된 simulation triple 1,145개에 대해 232,289개의 다음-row transition 의무를 검사했으며 실패는 0이었다. 이는 증명의 대체물이 아니라 구현 회귀검사다.

## 6. row 256종의 구분

입력 행을 구조만 보고 미리 합치는 것은 일반 bottom family가 NORMAL/PIN을 다르게 인식할 수 있으므로 안전하지 않다.

대신 두 exact quotient를 사용한다.

1. **state-local action quotient**: 특정 state에서 256행을 정확히 계산한 뒤 같은 next state를 갖는 행을 256비트 mask 하나로 저장
2. **complete minimized DFA global quotient**: 모든 minimized state에서 action vector가 같은 행만 병합

Universal complete DFA에서는 global row class가 256에서 200으로 줄었다. state-local sparse action group은 raw dense transition 649,472개를 45,995개 group으로 압축했다.

## 7. transition cache 중복

기존 cache는 `(frozenset state, row signature)` 객체를 key로 하고 edge dataclass/tuple을 중복 보존했다.

새 구현은:

- family state interning ID
- product state interning ID
- sorted antichain tuple interning state ID
- packed integer component edge
- packed integer component-cache key
- 완전 state는 row-action mask group
- full build 뒤 `release_build_caches()`로 local edge cache 제거

를 사용한다.

Universal L5 full build의 automaton-owned memory 추정은:

```text
build cache 포함: 32,402,260 B
build cache 해제: 11,036,844 B
complete minimized table: 3,488,257 B
```

이다.

## 8. unreachable/dead state

- dead result는 state 0 하나로 통합한다.
- full compiler는 start에서 BFS로 도달하는 state만 포함한다.
- family advance가 dead인 product는 subset에 들어가기 전에 제거한다.
- antichain에 제거된 product는 deterministic state로 intern하지 않는다.

Universal complete reachable graph는 shortest-depth 기준:

```text
1, 81, 865, 1,140, 415, 30, 4
```

개의 새 state를 만든 뒤 닫혔고 live state 총수는 2,536개였다.

## 9. complete minimization

전체 reachable transition graph가 닫힌 뒤 표준 residual partition refinement를 수행했다.

```text
2,536 reachable live states
→ 962 minimized states (dead block 포함)
```

감소율은 62.07%다. 이는 L=5까지만 맞추는 bounded minimization이 아니라, queue가 비어 모든 reachable transition이 닫힌 complete DFA에 대한 all-suffix 동치다.

## 10. family state 증가

Universal family는 상태가 하나이므로 위 수치에는 family explosion이 없다. 의미 없는 tag를 포함한 4상태 synthetic family에서는 L3 cumulative state가 54,640개였다. 정확한 `canonical_state/state_includes` quotient를 주면 family state는 2개, cumulative Stack state는 24,386개로 감소했다.

이 결과는 다음을 뜻한다.

- family residual state 수는 실제 다음 병목이다.
- Stack branch가 family 의미를 임의로 병합하면 안 된다.
- `corner-half`가 최소화된 exact automaton과 residual inclusion certificate를 제공해야 효과가 크다.

## 11. 최종 성장

Universal base, 256행 전체 탐색:

| 정확 층수 | optimized state |
|---:|---:|
| 0 | 1 |
| 1 | 81 |
| 2 | 942 |
| 3 | 2,082 |
| 4 | 2,497 |
| 5 | 2,527 |
| 6 | 2,531 |
| 7 | 2,531 |

전체 unique live state는 2,536개에서 닫힌다. 하지만 이 포화는 Universal 1-state family에 대한 결과이며, 향후 Half/PP family에도 같은 수치가 유지된다는 주장은 하지 않는다.
