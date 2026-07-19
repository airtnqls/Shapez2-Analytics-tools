# Half research resolution

초기 가설은 two-column frontier에 Corner residual, support behavior, crystal
partition, external-anchor obligation을 모두 저장하는 것이었다. fixed-cap
HalfSet과 대조한 결과 더 강한 단순화가 발견되었다.

```text
BuildableHalf(u,v)
↔ Corner(u) ∧ Corner(v) ∧ Stable(u,v)
```

따라서 별도 Half automaton이나 cpcp Ops1–6 symbolic fixed point가 필요하지
않다. Corner DFA 두 개와 폭2 안정성 도달성만이 최소 의미 상태다.

## 발견 과정의 검증

cap1..7에서 정리의 orientation-inclusive 개수는 cpcp의 공개 HalfSet
개수와 정확히 일치했다.

```text
16, 181, 1,796, 16,193, 135,074, 1,058,849, 7,905,398
```

## 완전성의 실제 근거

개수 일치가 아니라 `HALF_FAMILY_THEOREM_KO.md`의 직접 constructor가
근거다.

```text
Corner(v)+tower east prefab
Corner(u)+tower west prefab
→ Swap
→ RotateCW
→ CutEast
→ stable target half
```

이 결과는 이후 `stack-pp` 브랜치가 사용할 exact rank-0 Half family이다.
