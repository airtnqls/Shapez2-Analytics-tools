# Stack closure 최적화의 의미 보존 증명

## 1. 대상 언어

고정된 deterministic bottom family automaton `F`와 local top-piece policy `T`에 대해, 목표 row stream `X`가 수용된다는 것은 다음 ownership path가 존재한다는 뜻이다.

- 각 열은 A에서 B로 최대 한 번 전환한다.
- X에 보이는 crystal은 A 소유다.
- 각 B row piece는 바로 아래 target occupancy에 정확히 착지한다.
- A row stream은 `F`가 수용한다.
- A 전체는 안정하다.
- A와 B 모두 한 조각 이상 기여한다.

Legacy와 optimized 구현은 같은 local transition relation을 사용한다.

## 2. support residual quotient

Concrete support configuration `h`의 residual language를:

```text
L(h) = 앞으로 붙일 A-row suffix 중 마지막에 A가 안정해지는 suffix 집합
```

으로 정의한다.

2,011개 reachable concrete configuration에 대해 완전 256-symbol DFA를 만들고, 다음 relation으로 최소화한다.

```text
h1 ≡ h2  iff  L(h1) = L(h2)
```

DFA 최소화 정리에 의해:

1. `≡`는 모든 row transition에 대한 right congruence다.
2. final stability acceptance가 보존된다.
3. concrete history를 quotient ID로 바꿔도 모든 미래 suffix의 acceptance가 같다.

따라서 131-state support quotient 사용은 soundness와 completeness를 모두 보존한다.

## 3. previous-row projection

다음 Stack transition에서 직전 target row로부터 읽는 값은 B 착지용 `occupied`뿐이다. A의 직전 crystal/지지 정보는 support quotient state 안에 존재한다. 그러므로 full row 대신 previous occupied mask를 저장해도 local transition이 동일하다.

## 4. product simulation preorder

Product state를 다음으로 쓴다.

```text
p = (S_p, H_p, A_p, F_p)
```

- `S`: 이미 B로 전환된 열 mask
- `H`: support residual state
- `A`: 과거에 A 가시 조각이 있었는가
- `F`: bottom-family residual state

다음 조건에서 `p ⪰ q`라 정의한다.

1. `S_p ⊆ S_q`
2. `S_q != 0`이면 `S_p != 0`
3. `A_q`이면 `A_p`
4. `L_support(H_q) ⊆ L_support(H_p)`
5. `L_family(F_q) ⊆ L_family(F_p)`

family inclusion hook이 없으면 5번은 equality만 허용한다.

### 전이 모사 보조정리

임의의 다음 target row `r`와 q의 ownership 선택 `U_q`를 생각한다. p는 다음을 선택한다.

```text
U_p = U_q ∪ ((S_q - S_p) ∩ visible_noncrystal(r))
```

- q에서 이미 B인 열이 p에서는 아직 A라면, 그 열의 다음 가시 non-crystal에서 바로 전환한다.
- 해당 열이 비어 있으면 전환을 미뤄도 현재 A/B projection은 같다.
- 해당 열이 crystal이면 q 자체가 전이 불가다.

따라서 q 전이가 존재할 때 p에서도:

- 현재 B mask가 동일
- 현재 A projected row가 동일
- landing/top-policy 결과 동일
- family transition은 포함관계를 보존
- support transition은 residual inclusion을 보존
- 다음 switched mask도 subset relation을 보존

하는 전이가 존재한다.

### terminal 보존

조건 2와 3은 q가 과거 A/B를 가졌을 때 p도 이를 갖게 한다. support/family language inclusion은 q terminal acceptance이면 p terminal acceptance임을 보장한다.

따라서:

```text
p ⪰ q  =>  FutureLanguage(q) ⊆ FutureLanguage(p)
```

이다.

## 5. antichain 정규화

Determinization subset에서 다른 product가 포함하는 product q를 제거한다. 원래 subset의 accepted language는 각 product language의 union이다.

```text
L(P) = union_{p in P} L(p)
```

`L(q) ⊆ L(p)`이면 q를 제거해도 union은 바뀌지 않는다. 따라서 antichain 정규화는 존재 판정의 soundness/completeness를 보존한다.

Witness에서는 제거되지 않은 simulator p의 실제 predecessor path를 유지한다. 위 전이 모사 정리에 의해 accepted suffix는 p의 path에서도 실제 ownership sequence로 재생 가능하다.

## 6. state/family interning

동일한 immutable tuple을 integer ID로 치환하는 것은 표현만 바꾸며 transition/acceptance를 바꾸지 않는다.

Family의 `canonical_state()`와 `state_includes()`는 선택적이다. 두 hook은 bottom-family 구현이 residual-language equality/inclusion을 증명한 경우에만 사용해야 한다. hook이 없으면 equality 외 병합을 하지 않는다.

## 7. row action quotient

특정 deterministic state s에서 두 row a,b가:

```text
delta(s,a) = delta(s,b)
```

이면 그 state의 transition table에서 같은 row mask group으로 저장한다. 이는 transition을 모두 정확히 계산한 뒤 결과 ID가 같은 경우만 합치는 것이므로 의미를 바꾸지 않는다.

Complete minimized DFA의 global row quotient는 더 강하게:

```text
forall s: delta(s,a) = delta(s,b)
```

일 때만 병합한다.

## 8. complete DFA minimization

Start에서 BFS로 모든 reachable state를 탐색하고 queue가 빌 때까지 256 전이를 모두 닫는다. 그 뒤:

```text
s ≡ t iff 모든 유한 row suffix z에 대해
          accept(delta*(s,z)) = accept(delta*(t,z))
```

인 표준 DFA residual equivalence를 partition refinement로 계산한다. complete graph가 닫히기 전에 이 quotient를 solver에 사용하지 않는다.

따라서 minimized 962-state DFA는 원래 2,536-state reachable DFA와 모든 유한 suffix에서 정확히 동치다.

## 9. accepts/witness 분리

`accepts_rows()`는 integer state ID만 이동시키며 parent history를 저장하지 않는다.

`witness()`는 같은 NFA transition을 target 한 개에 대해서만 다시 실행하고, 각 층의 surviving product마다 predecessor product와 ownership mask 하나를 저장한다. 최종 accepting product에서 역추적한다.

두 경로가 같은 local relation과 antichain theorem을 사용하므로:

```text
accepts(X) iff witness(X) is not None
```

이다. 실제 Shape 후보를 만드는 adapter에서는 materialize 후 forward `Stack(A,B)==X` replay가 다시 통과해야 한다.

## 10. 전체 결론

위 최적화는:

- raw Stack relation
- A 안정성
- bottom-family membership
- top-piece policy
- accepted ownership witness

를 바꾸지 않는다.

테스트는 구현 검증이고, 전층 의미 보존 주장은 이 문서의 residual quotient 및 simulation 정리에 의존한다.
