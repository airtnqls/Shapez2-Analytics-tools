# 전층 Half Stable-Pair 정리

## 1. 정의

quad east half `H=(u,v)`는 q0,q1 두 인접 열만 점유하고 q2,q3은 빈 도형이다. `Stable(H)`는 reference gravity를 다시 적용해도 변하지 않는다는 뜻이다. `Corner(w)`는 전층 Corner DFA가 accept한다는 뜻이다.

## 2. 주정리

**정리 H.** 모든 유한 layer cap `L`과 모든 normalized half `H=(u,v)`에 대해:

```text
BuildableHalf(H)
iff Corner(u) and Corner(v) and Stable(H)
```

즉 cpcp Half Ops 1–6의 최소 고정점 전체는 이 세 조건과 정확히 같다.

## 3. 필요조건

`H`가 buildable이라 하자.

1. `H` 자체가 buildable full shape의 output이므로 u와 v는 각각 buildable shape에서 나타난 열이다. Corner 판정 정리에 의해 `Corner(u)`와 `Corner(v)`다.
2. 모든 structural building output은 안정하다. Gravity가 없는 Generator output도 occupied height 아래가 완전히 채워져 있으므로 안정하다. Swapper recombination은 stable halves의 support derivation을 보존한다. 따라서 `Stable(H)`다.

## 4. 충분조건

`Corner(u)`, `Corner(v)`, `Stable(H)`를 가정한다. `T=S^L`을 solid tower라 하자.

Corner constructor의 solid-neighbor 강화에 의해 다음 두 stable half를 raw inputs에서 만들 수 있다.

```text
Hv = (v,T)
Hu = (T,u)
```

`Hu`를 180도 회전하면 west half `(T,u)`가 된다. 이제 다음 실제 연산을 수행한다.

```text
Hv=(v,T)  +  rotate180(Hu)=(T,u) on west
    --Swapper-->
(v,T,T,u)
    --rotate_cw-->
(u,v,T,T)
    --Cutter, keep east-->
(u,v)=H
```

마지막 cut boundary 양쪽 중 한쪽은 항상 normal tower T이므로 cross-boundary crystal shatter가 없다. Cut 뒤 east half에는 gravity가 적용되지만 가정 `Stable(H)`에 의해 변하지 않는다. 따라서 H는 buildable이다.

이 proof는 cpcp의 구체 HalfSet 나열이나 layer별 BFS를 사용하지 않으며 L에 독립적이다.

## 5. constructor

```python
construct_half(code,L)       # compact stable-pair certificate
replay_half_full(code,L)     # 두 Corner raw proof까지 포함한 실제 연산 재생
```

`replay_half_full()`은:

1. `replay_corner_full(u,L)`과 `replay_corner_full(v,L)`을 호출한다.
2. 각 최종 canonical `[w,T,T,T]`에서 Cutter로 `(w,T)` fixture를 꺼낸다.
3. 위 충분조건의 Swap/Rotate/Cut을 실제 structural kernel로 재생한다.
4. 모든 intermediate stability와 최종 exact code를 확인한다.

## 6. 불가능 certificate

`analyze_half()`은 다음 순서로 즉시 reject 이유를 반환한다.

1. u의 Corner reject certificate
2. v의 Corner reject certificate
3. joint stability failure

세 조건이 모두 통과하면 위 constructor가 존재하므로 별도 `UNKNOWN`이 없다.

## 7. 복잡도

- 두 Corner DFA: `Θ(L)`
- 두-column support BFS: `Θ(L)`
- membership 전체: `Θ(L)` time, `O(L)` parse memory
- witness path: child Corner proof 크기 + 상수 개수 Swap/Rotate/Cut

명시적 L-layer input은 마지막 layer 하나로 답이 달라질 수 있으므로 `Ω(L)`을 읽어야 한다. 따라서 membership은 점근적으로 최적이다.

## 8. 독립 fixed-cap 검증

cpcp 방식으로 생성한 exact Half bitset과 predicted bitset을 key 단위로 비교했다.

| L | Corner columns | Exact Half keys | FP | FN |
|---:|---:|---:|---:|---:|
| 1 | 4 | 16 | 0 | 0 |
| 2 | 14 | 181 | 0 | 0 |
| 3 | 47 | 1,796 | 0 | 0 |
| 4 | 152 | 16,193 | 0 | 0 |
| 5 | 476 | 135,074 | 0 | 0 |
| 6 | 1,450 | 1,058,849 | 0 | 0 |

L=7에서는 4,320 Corner columns의 18,662,400 ordered pair를 전부 안정성 검사해 7,905,398을 얻었고 cpcp published total과 일치했다.

이 검증은 증명을 대신하지 않지만, 조건별 count가 아니라 bitset 전체가 일치한다는 강한 독립 회귀검사다.
