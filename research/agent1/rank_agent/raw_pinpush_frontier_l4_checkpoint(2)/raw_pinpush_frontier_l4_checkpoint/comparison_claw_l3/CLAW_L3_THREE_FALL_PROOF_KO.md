# Shapez 2 전층 Claw 역산의 `O(L^3)` 축약

## Three-Fall Top-Payload 정리와 fixed-two-eager 귀결

## 0. 결과와 적용 범위

이 글은 폭 4, 유한 cap `L`의 Shapez 2 Pin Pusher 역산에서 다음을 증명한다.

> 안정한 Pin-Pusher 전상 `X`가 어떤 Cutter 축에서 두 안정한 2열 half로 분리되고, `Y = PinPush_L(X)`에서 살아남은 일반조각/핀의 낙하가 세 열 이상에서 일어나며 crystal도 하나 이상 살아남는다면, `Y`에는 최고 생존 crystal보다 높은 crystal-free noncrystal payload가 존재한다.

따라서 stable Stacker factorization을 허용하는 프로젝트의 `CLAW/HYBRID` 의미에서는 그러한 `Y`는 순수 Claw가 아니다. 순수 Claw의 유효한 cut-stable 전상에서는 낙하 열이 최대 두 개이고, 나머지 두 열은 모든 source cut에서 고정 eager이다. 그러므로 frontier 상태 수는 `O(L^3)`으로 줄어든다.

주의: “Stacker 가능”을 두 factor의 **완전한 TMAM 제작 가능성**까지 요구하는 더 강한 의미로 정의한다면, 이 글은 top factor의 제작 가능성은 직접 보이지만 bottom factor의 일반 제작 가능성은 별도 lemma로 남긴다. 현재 프로젝트 분류기처럼 stable structural factorization을 사용하는 계약에서는 아래 증명으로 충분하다.

---

## 1. 물리 모델

열은 4개이며 원형으로 인접한다. Cutter 축 하나를 고르면 두 개의 2열 half `H0,H1`로 나뉜다.

지원 집합은 다음 규칙의 최소 고정점이다.

1. 0층의 점유 셀은 지원된다.
2. 지원 셀 바로 위의 점유 셀은 지원된다.
3. 같은 층에서 지원된 비핀 셀에 인접한 비핀 셀은 지원된다.
4. 지원된 crystal 바로 아래의 crystal은 매달려 지원된다.

Pin Pusher는 다음 순서로 동작한다.

1. 모든 기존 셀을 한 층 올린다.
2. 옛 바닥이 점유된 열에 새 바닥 핀을 삽입한다.
3. cap 밖의 최상층을 삭제한다. 삭제된 crystal과 연결된 crystal 성분도 삭제한다.
4. unsupported crystal 성분을 삭제한다.
5. unsupported 일반조각 수평 그룹과 singleton pin을 아래층부터 낙하시킨다.

기존 일반조각과 핀은 열을 바꾸지 않으며, top trim에 직접 잘리지 않는 한 삭제되지 않는다.

---

## 2. 용어

`X`를 한 층 올리고 새 바닥 핀을 넣은 oversized 상태를 `X↑`라 하자.

- `D`: cap 밖 top crystal에서 시작하여 4-neighbor crystal 연결로 삭제되는 직접 파괴 성분.
- `K`: `D` 삭제 뒤에도 살아남는 crystal.
- `h`: 살아남는 crystal의 최고 층.
- active 열: top trim으로 삭제되지 않은 기존 `S/P` 중 하나가 `source+1`보다 낮게 최종 착지한 열.
- eager 열: 모든 source cut에서 target prefix의 `S/P` 소비 수와 source prefix의 `S/P` 수가 같은 열.

한 열이 모든 cut에서 eager인 것과 그 열에서 살아남은 기존 `S/P`가 한 칸도 낙하하지 않는 것은 동치다. 이 동치는 §8에서 증명한다.

---

## 3. 2열 crystal interval lemma

### Lemma 3.1 — top 파괴 성분의 행 구간

2열 half에서 top row에 crystal이 있다면, top crystal들은 하나의 연결 성분 `D`를 이룬다. `D`가 점유하는 행의 집합은 어떤 정수 `m`에 대해 연속 구간 `[m,L]`이다.

#### 증명

한 row의 두 crystal은 수평 인접하므로 같은 성분이다. 연결 경로가 최저 row `m`에서 top row `L`로 갈 때 row 좌표는 한 번에 최대 1만 변하므로 모든 중간 row를 지난다. ∎

### Lemma 3.2 — 다른 crystal은 전부 `m` 아래

`D`와 다른 crystal 성분은 모두 row `< m`에 놓인다.

#### 증명

`D`는 `[m,L]`의 모든 row에 crystal을 적어도 하나 가진다. 다른 crystal이 같은 row에 존재하면 2열 strip에서는 `D`의 crystal과 같은 셀이거나 수평 인접 셀이므로 같은 성분이 된다. 모순이다. ∎

---

## 4. 2열 No-U lemma

### Lemma 4.1

안정한 2열 half에서 top row 전체와 direct top component `D`를 삭제한 뒤, `D`가 아닌 crystal은 unsupported가 되지 않는다. 즉 isolated half에는 두 번째 crystal 파괴군 `U`가 없다.

#### 증명

`D`가 아닌 crystal `k`는 Lemma 3.2에 의해 row `<m`에 있다. 삭제 전 lifted half가 안정하므로 ground에서 `k`까지 지원 derivation path가 있다.

지원 path가 아래 방향으로 움직일 수 있는 유일한 edge는 crystal-above → crystal-below이며, 이 edge는 같은 crystal 성분 안에 있다. 따라서 path가 한 번 `D`에 들어가면 `D` 안에서 row `m`보다 아래로 내려갈 수 없고, noncrystal로 빠져나온 뒤에도 아래로 이동할 수 없다. top-row noncrystal 역시 아래 방향 edge를 주지 못한다. row `<m`의 `k`에 도달하는 path는 top trim 집합이나 `D`를 사용할 수 없다.

그러므로 top row와 `D` 삭제 뒤에도 동일한 path가 남아 `k`를 지원한다. ∎

### Corollary 4.2 — crystal locality

cut-stable full predecessor를 두 half로 나누어 각각 Pin Push한 경우와 full Pin Push한 경우, 살아남는 crystal 집합은 half별 생존 crystal의 합집합과 같다.

#### 증명

cut이 원형을 보존하므로 경계를 가로지르는 crystal-crystal 쌍이 없다. 따라서 direct `D` 성분은 half마다 독립이다. Lemma 4.1에 의해 각 half의 non-`D` crystal은 이미 내부 지원을 가지므로 full 결합에서 추가로 살아나거나 사라지는 crystal이 없다. ∎

---

## 5. 낮은 셀의 지원 보존

### Lemma 5.1

`h`를 highest surviving crystal row라 하자. `D`와 top-trimmed noncrystal을 삭제해도 row `≤h`의 noncrystal은 supported 상태를 잃지 않는다.

#### 증명

Lemma 3.2에서 `h<m`이다. row `≤h`의 noncrystal로 끝나는 지원 path가 삭제 집합을 사용한다고 가정하자.

- top-trimmed noncrystal에 들어간 path는 같은 row의 수평 edge 또는 위 방향 edge만 사용할 수 있으며 아래로 돌아올 수 없다.
- `D`에 들어간 path가 아래로 이동할 수 있는 것은 `D` 내부 crystal edge뿐이고, `D`의 최저 row는 `m>h`이다.

따라서 삭제 집합을 지난 path는 row `≤h`의 noncrystal에 도달할 수 없다. 원래 지원 path는 삭제 집합을 피하며 그대로 남는다. ∎

### Corollary 5.2

`D` 및 unsupported crystal 삭제 후의 모든 unsupported noncrystal은 row `>h`에 있다.

---

## 6. Active-half top-payload lemma

### Theorem 6.1

안정한 2열 half의 isolated overflow Pin Push 결과가

1. crystal을 하나 이상 남기고,
2. 기존 noncrystal을 하나 이상 낙하시킨다면,

결과에는 highest surviving crystal보다 높은 noncrystal이 존재한다.

#### 증명

lifted half는 새 바닥 핀 때문에 trim 직전에도 안정하다. 삭제 집합을 `R = (top row 전체) ∪ D`라 하자. ground에서 `D`로 들어가는 지원 path 하나를 고르고, path가 처음 `R`에 들어가기 직전의 셀을 `a`라 한다.

먼저 `m=L`, 즉 `D`가 top row에만 있다고 하자. top noncrystal은 아래 방향 지원을 주지 못하고, top crystal에서 아래로 가는 crystal edge가 있었다면 그 아래 crystal도 `D`여서 `m<L`이다. 따라서 `m=L`에서 top trim은 lower cell의 지원을 끊지 못하며 active faller가 생길 수 없다. 현재 가정은 active half이므로 `m≤L-1`이다.

첫 `R` 셀이 row `<L`의 `D` cell이면 `a`는 그 바로 아래 또는 같은 row의 수평 인접 셀이다. `a`가 crystal이면 `D`와 같은 성분이므로 `a`는 noncrystal이고 row `≥m-1`이다.

첫 `R` 셀이 top-row noncrystal이면, path가 top row에 처음 들어가는 edge는 row `L-1`에서 올라오는 vertical edge다. 그 직전 셀 `a`가 crystal이면, `m≤L-1`인 `D`가 같은 row의 다른 열에 crystal을 가지므로 두 crystal이 연결되어 `a∈D`가 된다. 따라서 이 경우에도 `a`는 noncrystal이다.

path의 `a`까지의 prefix는 `R`을 사용하지 않으므로 `a`는 trim 뒤에도 supported이며 움직이지 않는다. Lemma 3.2에서 `h<m`이고, `a`의 row는 최소 `m-1`이므로 `row(a)≥h`이다.

- `row(a)>h`이면 `a` 자체가 highest crystal 위의 고정 noncrystal이다.
- `row(a)=h`이면 `a`는 한 열의 noncrystal이고, row `h`의 surviving crystal은 다른 열에 있다. 따라서 두 열 모두 row `h`에 움직이지 않는 supported blocker를 갖는다. Corollary 5.2에 의해 모든 faller는 row `>h`에서 시작한다. 적어도 하나가 실제로 낙하하며 어느 열에서도 row `h` blocker를 통과할 수 없으므로 최종 row는 `≥h+1`이다.

두 경우 모두 highest surviving crystal 위에 noncrystal이 남는다. ∎

### 보충: top crystal이 없는 half

2열 half의 top row에 crystal이 없으면 trim되는 것은 top noncrystal뿐이다. noncrystal은 아래 셀에 지원을 전달하지 않으므로 top trim은 lower cells의 지원을 끊지 못한다. 따라서 isolated half에서는 낙하가 없다.

즉 active half는 반드시 top crystal을 가진다.

---

## 7. Half 추가에 대한 낙하 단조성

### Lemma 7.1 — support monotonicity

한 half를 다른 half와 결합하면 기존 half의 support derivation은 사라지지 않는다. 따라서 isolated에서 supported였던 셀은 full에서도 supported다.

### Lemma 7.2 — horizontal group의 전부-또는-전무

isolated에서 같은 row의 한 unsupported normal component 중 한 셀이 full에서 새로 supported되면, 수평 support가 component 전체로 전파되어 전부 supported된다. 일부만 supported되어 component가 쪼개지는 경우는 없다. Pin은 원래 singleton이다.

### Lemma 7.3 — landing-height monotonicity

half origin의 surviving noncrystal에 대해

`full landing row ≥ isolated landing row`

이다.

#### 증명

source row를 낮은 곳부터 귀납한다. row `r` 미만에서 이미 처리된 모든 origin의 full landing이 isolated landing보다 낮지 않다고 가정한다. 그러면 각 half column에서 row `r` 아래의 최고 blocker 높이도 full 쪽이 isolated보다 낮지 않다.

isolated component가 full에서 supported되면 full landing은 source row `r`이므로 결론이 즉시 성립한다. 계속 unsupported이면 Lemma 7.2에 의해 isolated component 전체가 full component에 포함된다. 한 수평 group의 landing row는 참여 열들의 `highest blocker + 1`의 최댓값이다. full은 blocker가 더 높거나 같고 열 집합이 더 크거나 같으므로 full landing도 더 높거나 같다.

같은 source row의 서로 다른 component는 서로 다른 열 집합을 사용하므로 처리 순서는 이 귀납을 깨지 않는다. ∎

### Corollary 7.4

full Pin Push에서 한 열이 active이면, 그 열이 속한 isolated half도 active이다.

---

## 8. Three-Fall Top-Payload 정리

### Theorem 8.1

안정한 predecessor `X`가 어떤 Cutter 축에서 두 안정한 half `H0,H1`로 분리되고, `Y=PinPush(X)`에서

- crystal이 생존하며,
- 세 열 이상이 active라면,

`Y`의 highest crystal 위에 noncrystal이 존재한다.

#### 증명

세 active 열을 두 2열 half에 나누면 두 half가 모두 적어도 한 active 열을 갖는다. Corollary 7.4에 따라 두 isolated half도 모두 active이다.

Corollary 4.2에 의해 full의 global highest crystal은 그것이 속한 isolated half에서도 같은 높이로 생존한다. 그 half는 active이므로 Theorem 6.1을 적용할 수 있다. isolated result에는 그 crystal보다 높은 noncrystal `u`가 존재한다.

Lemma 7.3에 의해 `u`는 full에서도 isolated보다 낮게 내려가지 않는다. 따라서 full `Y`에도 global highest crystal보다 높은 noncrystal이 존재한다. ∎

---

## 9. Stacker factorization

`h`를 global highest crystal row라 하고, Theorem 8.1에 의해 `h` 위가 비어 있지 않다고 하자.

- `B = Y[0..h]`
- `U = Y[h+1..top]`, row 번호를 0부터 다시 매긴 shape

로 둔다. `U`에는 crystal이 없다.

### Lemma 9.1

`B`는 안정하다.

#### 증명

`B`의 셀이 위쪽 noncrystal에서 아래 방향 지원을 받을 수는 없다. 아래 방향 지원은 crystal-crystal hanging뿐인데 `U`는 crystal-free이다. `Y`의 지원 derivation을 `B`에 제한해도 유지된다. ∎

### Lemma 9.2

`U`는 안정하다.

#### 증명

crystal-free 영역의 support path는 위 또는 같은 row로만 진행한다. `Y`에서 `U`의 셀로 가는 path가 `U`에 처음 들어가는 셀은 row `h+1`에 있다. `U`를 rebase하면 이 셀들이 0층 ground seed가 되고, 이후 path는 그대로 보존된다. ∎

### Lemma 9.3

프로젝트 `Shape.stack(B,U)`의 결합 배열은 정확히 `Y`이며, `U`에는 제거될 crystal이 없고 `Y`가 안정하므로 gravity 뒤에도 `Y`다.

따라서 stable structural preimage 의미에서 `Y`는 Stacker 가능이다.

---

## 10. 진짜 Claw의 active 열 상한

Claw를

- Pin Push preimage가 존재하고,
- Swapper preimage가 없고,
- Stacker preimage가 없는 목표

로 정의하자. Theorem 8.1과 §9에 의해 세 열 이상 active인 cut-stable Pin Push preimage는 Stacker preimage를 제공한다. 모순이다.

따라서 true Claw의 cut-stable Pin Push predecessor에서는

`active columns ≤ 2`.

---

## 11. active와 fixed eager의 동치

열 `q`에서 source row `≤s`의 surviving `S/P` 수를 `C_q(s)`, target row `≤s+1`의 기존 `S/P` token 수를 `E_q(s+1)`라 하자. 새 바닥 receipt pin은 token에서 제외한다.

`δ_q(s)=E_q(s+1)-C_q(s)`.

- 아무 origin도 낙하하지 않으면 source row `r`의 token은 target row `r+1`에 있으므로 모든 cut에서 두 prefix 수가 같다.
- origin `r`의 token이 `t<r+1`로 낙하했다면 `t≤s+1<r+1`인 cut `s`를 하나 선택할 수 있다. 그 cut에서 target prefix는 token을 포함하지만 source prefix는 포함하지 않아 `δ_q(s)>0`이다.

따라서 열 q가 모든 cut에서 eager인 것과 q가 inactive인 것은 동치다.

active 열이 최대 2개이므로 고정 eager 열은 최소 2개다.

---

## 12. `O(L^3)` frontier

고정 eager pair를 6가지 중 하나로 분기한다.

- source row: `O(L)`
- eager pair: 6, 상수
- 나머지 두 열 cursor: `O(L^2)`
- 폭 4 support/crystal partition/Cutter/DFA state: `O(1)`

따라서 상태 수는

`O(L) · 6 · O(L^2) = O(L^3)`.

한 상태의 row transition 수는 폭 4 고정 alphabet에 의해 상수다. 따라서 첫 predecessor 존재 판정과 parent-pointer 복원은 `O(L^3)` 시간 및 메모리 상한을 갖는다.

cap 미만 plain Pin Push inverse는 별도 `O(L)` 라우터로 처리한다.

---

## 13. 검증

증명의 대체물은 아니지만 구현 오류와 반례 탐색을 위해 다음 검사를 수행했다.

- L=2..7 모든 안정 top-crystal 2열 half에서 Theorem 6.1의 두 mechanism 검사: 반례 0.
- L=7 안정 top-crystal 2열 half 20,340,555개: secondary U crystal 반례 0.
- L=6 모든 stable half 중 top crystal이 없는 2,072,277개: active 반례 0.
- L=5 relevant half pair 전체: 3-active + crystal + topmost-crystal 반례 0.
- L=6 relevant half pair 전체 4,428,138개: 3-active + crystal + topmost-crystal 반례 0.
- L=7 relevant random pair 100,000,000회: 같은 반례 0.
- authoritative 5층 Claw 40,171개: fixed eager pair가 없는 predecessor 0.

---

## 14. 남은 범위 경계

이 증명으로 닫히는 것은 다음 계약이다.

1. frontier가 찾는 predecessor는 안정하고 한 Cutter 축에서 두 안정 half로 분리된다.
2. Stacker 가능성을 stable structural factorization으로 판정한다.
3. 입력은 true Claw로 이미 분류되었거나, solver가 Swap/Stack 배타성을 함께 확인한다.

두 factor `B,U`가 원재료부터 각각 제작 가능해야만 Stacker preimage로 인정하는 더 강한 TMAM 정의에서는 `U`는 crystal-free 안정 shape이므로 layer-group stacking으로 직접 제작할 수 있다. 일반 `B`의 독립 제작 가능성은 전체 TMAM 정리와 연결되는 별도 과제다.
