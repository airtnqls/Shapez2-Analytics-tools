# Half 기반 Stack closure 이론

## 1. 해결할 관계

일반 역산:

\[
\operatorname{Stack}^{-1}(X)
\]

를 그대로 계산하지 않는다. 브랜치가 계산해야 하는 것은:

\[
\operatorname{Stack}^{-1}(X)
\cap
(F_{\mathrm{bottom}}\times F_{\mathrm{top}})
\]

이다.

TMAM에서 대표적인 선택은:

```text
F_bottom = SwappableFamily ∪ PP(rank < n)
F_top    = Rank0StackPieceFamily
```

Claw-Hybrid는 특수하게:

```text
F_bottom = StrictClawFamily
```

인 경우였다.

## 2. 현재 재사용하는 전층 Stack 불변량

현재 전층 Stack frontier가 증명한 canonical visible relation은 다음이다.

1. X에 보이는 crystal은 전부 bottom A 소유
2. 각 열의 점유 셀 소유권은 `A* B*`
3. B pin은 같은 열의 바로 아래 X 셀이 점유되어야 함
4. 한 층의 B 일반 horizontal component는 구성 열 중 하나 이상에 바로 아래 blocker가 있어야 함
5. A는 안정해야 함
6. B의 비가시 crystal scaffold는 canonical 대표 하나로 정규화 가능

이 관계는 `Θ(L)` Stack frontier로 계산된다.

## 3. TMAM Stack closure에서는 B를 임의 buildable shape로 재귀 풀이하지 않음

최종 ProofNode는 다음처럼 만든다.

```text
STACK
├── base A                  # 이미 알려진 family / 낮은 rank
├── layer piece B0          # rank-0 piece
├── layer piece B1
└── ...
```

즉 canonical B 도형은 실행 편의를 위한 묶음이고, 증명에서는 B의 가시 layer component를 finite top-piece family로 다시 분해한다.

핀은 singleton component이고, 일반 조각은 한 층의 수평 연결 성분 단위다. 각 component의 anchor 조건은 Stack frontier의 착지 조건과 동일하다.

## 4. 건전성 목표

product frontier가 `(A, pieces)`를 수용하면:

1. `A ∈ F_bottom`
2. 모든 `piece_i ∈ F_top`
3. A와 각 piece의 witness가 존재
4. 지정 순서로 Stack replay하면 X
5. 모든 중간 결과가 안정

이어야 한다.

## 5. 완전성 목표

X가 허용된 family의 Stack construction을 가진다고 가정한다.
그 construction을 canonical visible ownership으로 정규화하면:

- 각 열은 A에서 B로 한 번만 전환
- B crystal은 삭제 가능하므로 canonical scaffold로 교체
- B의 가시 material은 layer component sequence로 분해
- A의 행 stream은 HalfFamily automaton의 수용 경로

가 된다. 따라서 product frontier에 수용 경로가 존재해야 한다.

## 6. 복잡도

Half family automaton 상태 수를 `|H|`, Stack-support 상태 수를 `|S|`라 하면:

```text
존재/첫 witness: O(L · |H| · |S|)
rolling memory: O(|H| · |S|)
모든 witness: output-sensitive
```

폭 4에서 `|S|`는 층수와 무관한 유한값이다. 핵심 미해결량은 `|H|`와 rank별 family state 증가다.
