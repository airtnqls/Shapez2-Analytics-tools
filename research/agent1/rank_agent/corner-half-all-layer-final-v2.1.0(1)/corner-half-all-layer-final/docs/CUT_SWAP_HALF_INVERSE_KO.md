# 전층 Cut/Swap용 일반 Half inverse

구현: `corner_half/half_inverse.py`

## 1. Cutter inverse

제작 가능한 east-half `H=(u,v)`에 대해 높이 `h=max(1,|u|,|v|)`의 solid
normal tower를 `T=S^h`라 하자.

```text
Parent = (u,v,T,T)
```

를 만든다. 반대쪽 두 열은 normal이므로 cut 경계에서 target crystal과
crystal-crystal pair를 만들지 않는다. 따라서:

```text
CutEast(Parent) = H
```

이다.

`canonical_cut_inverse(H)`는:

- `half_raw_proof(H)`
- west `(T,T)` proof
- 두 proof를 합치는 Swapper
- 마지막 Cutter

를 포함한 raw-input DAG를 반환한다. 즉 parent를 임의로 가정하지 않는다.

### 정리

```text
H in HalfFamily
<=> canonical_cut_inverse(H)가 존재한다.
```

좌에서 우는 위 construction, 우에서 좌는 Cutter output이 제작 가능한
Half라는 필요성으로 성립한다.

---

## 2. Swapper inverse

full target `X`를 한 cutter 축에 맞춘 orientation `R(X)`로 본다. 그 기하학적
두 half를 `E`, `W`라 하며 `W^e=rotate180(W)`는 east-normalized 표현이다.

> **Swappable 정리**
>
> `X`가 Swapper로 제작 가능
>
> iff
>
> 두 cutter 축 중 하나에서 `E in HalfFamily`이고 `W^e in HalfFamily`이다.

### 필요성

Swapper output의 east는 첫 입력을 Cutter한 half이고 west는 둘째 입력을
Cutter한 half다. 따라서 둘 다 정확한 Half family에 속한다.

### 충분성

Half constructor로 다음 두 입력을 만든다.

```text
A = east-only E
B = west-only W = rotate180(W^e)
```

빈 반대쪽 때문에 입력 Cutter에서 추가 crystal shatter가 없다.

```text
Swap(A,B)[0] = R(X)
RotateBack(...) = X
```

이므로 X를 정확히 제작한다.

`swap_inverse_candidates(X,L)`는 서로 다른 두 축 `rotation=0,1`을 검사하고,
각 가능한 축에 대해 두 operand proof와 최종 result proof를 반환한다.

---

## 3. 일반 역열거와의 차이

이 API는 사라지는 garbage나 임의의 반대쪽을 전부 열거하지 않는다.
TMAM에 필요한 것은 다음 존재관계와 canonical witness다.

```text
Cut parent exists?
Swapper operands exist?
```

모든 물리적으로 무의미한 parent를 나열하면 후보 수가 지수적으로 커지지만,
위 정리는 exact Half membership 두 번으로 존재 여부를 `Theta(L)`에 판정하고
필요할 때만 proof DAG 하나를 생성한다.

---

## 4. 검증

- cap3의 buildable Half 1,796개 전부: canonical Cutter parent 재생 실패 0
- cap2 full structural target 65,536개:
  - exact Half bitset으로 계산한 Swappable 판정과 불일치 0
  - Swappable target 35,017개
  - 분산 표본 2,000 target / 3,724 raw-input Swap proof root 재생 실패 0
- cap4..40 random Cutter parent 검증 실패 0
