# PP parent chain 종료 정리: Bottom Pin Receipt Rank

## 1. 목적

Shapez 2 quad mode, layer cap `L`에서 PP-essential parent chain이 숨은 `max_batch`, timeout, SMT 없이 반드시 종료함을 증명한다.

이 문서가 다루는 재귀는 다음 normal form의 PP 부분이다.

```text
Swappable
StackClosure(Swappable 또는 더 낮은 PP base)
PinPush(pre_push)
```

## 2. 정의

구조 shape `X`의 열 `q`에 대해

`r_q(X)` = layer 0에서 시작하는 연속 PIN(`P`)의 길이.

즉,

```text
X[0,q] = ... = X[r_q(X)-1,q] = P
```

이고 `r_q(X)=L`이거나 다음 셀은 P가 아니다.

**Bottom Pin Receipt Rank**를

\[
\sigma(X)=\sum_{q=0}^{3} r_q(X)
\]

로 정의한다.

명백히

\[
0\le \sigma(X)\le 4L.
\]

## 3. 대칭 불변성

### Lemma 1

회전 및 mirror에 대해 `sigma`는 불변이다.

### Proof

회전/mirror는 네 열을 순열할 뿐 각 열 내부의 bottom-to-top 셀 순서는 바꾸지 않는다. 따라서 `r_q`들의 multiset과 합이 보존된다. QED.

## 4. Stack 단조성

### Lemma 2

안정한 bottom `B`와 임의의 buildable top `U`에 대해

\[
\sigma(Stack(B,U))\ge \sigma(B).
\]

### Proof

Stack은 bottom과 top 사이에 빈 층을 둔 workspace를 만든 뒤 gravity를 적용한다. `B`는 실제 operation output이므로 안정하다. 따라서 `B`의 모든 셀은 이미 supported이며 gravity에서 이동하거나 shatter되지 않는다. Top의 crystal은 제거될 수 있고 나머지는 B 위 또는 빈 열의 바닥으로 떨어질 수 있지만, B에 이미 존재하는 bottom P-prefix는 수정하지 못한다. 그러므로 각 기존 `r_q(B)`가 결과에 그대로 남으며 합은 감소하지 않는다. QED.

## 5. Pin Push 증가량

### 정의: 퇴화 pin tower

`X`의 각 열이 다음 둘 중 하나이면 `X`를 pure full-pin-column shape라 한다.

1. 열 전체가 empty
2. layer `0..L-1` 전체가 P

### Lemma 3

안정하고 비어 있지 않은 shape `X`가 pure full-pin-column shape가 아니면

\[
\sigma(PinPush(X))\ge \sigma(X)+1.
\]

### Proof

열 `q`의 기존 bottom P-run 길이를 `k=r_q(X)`라 하자.

- `k<L`이고 bottom이 occupied이면 Pin Push는 새 layer 0에 P를 삽입하고 기존 P-run을 layer `1..k`로 올린다.
- overflow shatter는 crystal만 제거하므로 이 P들은 제거되지 않는다.
- 새 layer-0 P는 ground-supported이고, 위의 기존 P들은 하나씩 수직 지지된다. 따라서 gravity에서 움직이지 않는다.

그러므로 이 열은

\[
r_q(PinPush(X))\ge k+1
\]

을 만족한다.

`k=L`인 열은 cap 때문에 `L`에서 포화되지만 감소하지 않는다.

이제 occupied bottom을 가진 모든 열이 `k=L`이라고 가정하자. 그러면 그런 열은 전체가 P이다. Bottom-empty 열에 다른 material이 존재한다고 가정하면, 그 material의 support derivation은 ground로 가기 위해 어느 시점에 full-P 열과 수평 연결되어야 한다. 그러나 pin은 수평 support를 주거나 받지 않고, pin 아래로 crystal이 hang할 수도 없다. 따라서 bottom-empty 열의 material은 supported일 수 없어 안정성에 모순이다. 그러므로 shape는 empty/full-P 열만 가진 pure full-pin-column shape여야 한다.

가정상 `X`는 퇴화 shape가 아니므로 적어도 하나의 occupied-bottom 열에서 `k<L`이며, 그 열의 run이 엄격히 1 이상 증가한다. 다른 열의 run은 감소하지 않는다. 따라서 합이 최소 1 증가한다. QED.

### Lemma 4

pure full-pin-column shape의 Pin Push 결과는 자기 자신이며 Swappable이다.

### Proof

각 occupied 열은 이미 cap 전체가 P이다. Shift에서 top P 하나가 잘리고 새 bottom P가 들어와 동일한 열이 된다. Crystal이 없고 각 selected-column single-layer S input을 만든 뒤 L회 Pin Push하면 해당 열들은 cap 전체가 P가 된다. 절단한 두 half도 같은 방식으로 독립 제작 가능하므로 Swappable이다. QED.

### Corollary 5

PP searcher에 실제로 등록되는 모든 PP parent edge `pre -> target`은

\[
\sigma(target)>\sigma(pre)
\]

를 만족한다.

PP searcher는 pushed target이 Swappable이면 PP set에 넣지 않는다. 따라서 Lemma 4의 유일한 비엄격 경우는 PP edge가 될 수 없다.

## 6. 재귀 PP base 감소 정리

### Theorem 6 (Strict parent decrease)

PP target `T`의 recorded pre-push shape를 `A`라 하자. `A`가 그 자체로 더 낮은 PP target이면 `B=A`로 두고, 그렇지 않고 canonical Stack decomposition이 PP base를 사용하면 그 base를 `B`라 하자. 그러면

\[
\boxed{\sigma(B)<\sigma(T)}.
\]

### Proof

대칭 정규화는 Lemma 1로 sigma를 보존한다.

`B=A`인 경우는 등호가 자명하다. Stack decomposition인 경우 `A = Stack(B,U)`이므로 Lemma 2에서

\[
\sigma(A)\ge \sigma(B).
\]

`T`는 `PinPush(A)`의 회전/mirror orbit에 있고 실제 PP edge이므로 Corollary 5에서

\[
\sigma(T)\ge \sigma(A)+1.
\]

따라서

\[
\sigma(T)\ge \sigma(A)+1\ge \sigma(B)+1,
\]

즉 `sigma(B)<sigma(T)`이다. QED.

## 7. 종료성

### Theorem 7 (PP parent chain termination)

어떤 PP decomposition chain도 길이가 `4L`을 넘지 않는다.

### Proof

Theorem 6에 의해 재귀적으로 선택되는 다음 PP base마다 sigma가 자연수에서 엄격히 감소한다. sigma의 범위는 `0..4L`이다. 따라서 chain 길이는 최대 `sigma(T)<=4L`이며 무한 chain은 존재하지 않는다. QED.

## 8. Batch 상한

### Theorem 8

cpcp Algorithm B의 batch `b`에서 처음 생성된 PP shape `T`는

\[
\sigma(T)\ge b+1.
\]

따라서

\[
\boxed{b\le 4L-1}.
\]

### Proof

Batch 0 target은 비퇴화 pre-push의 Pin Push 결과이므로 sigma가 최소 1이다.

Batch `b>=1`의 pre-push는 batch `b-1` seed의 Stack derivative이다. Lemma 2로 seed sigma가 보존되고 Corollary 5로 Pin Push가 1 이상 증가한다. Batch에 대한 induction으로 결론이 성립한다. QED.

## 9. 구현 결과

하드코딩된 `PPParent::kMaxBatch = 15`는 수학적 상한이 아니다. 전층 구현은 다음 중 하나를 사용해야 한다.

1. target-directed recursion: `sigma(next_pp_base) < sigma(current_target)`를 직접 검사
2. forward batch oracle: `batch <= 4*L-1`

첫 방식이 더 강하다. `decompose(target, rank_limit)`는 PP branch를 `sigma(target) < rank_limit`일 때만 허용하고, 그 pre-push를 `rank_limit=sigma(target)`로 재귀 호출한다. Stack branch의 PP base도 `sigma(base)<rank_limit`일 때만 허용한다. 따라서 Batch tag 없이도 termination certificate가 된다.

## 10. Certificate

각 PP recursion edge는 다음을 기록한다.

```json
{
  "target": "...",
  "pre_push": "...",
  "recursive_pp_base": "...",
  "sigma_target": 7,
  "sigma_pre_push": 6,
  "sigma_base": 5,
  "pin_push_replay": true,
  "stack_replay": true
}
```

독립 verifier는 다음만 검사한다.

- `target`이 `PinPush(pre_push)`의 D4 orbit에 있음
- `pre_push = Stack(base, top)` 또는 `base=pre_push`
- `sigma(base) < sigma(target)`

solver의 batch 정보나 SMT 결과는 필요 없다.

## 11. 검증

독립 compact physics kernel에서 다음을 검사했다.

- Pin Push 증가 정리: cap 1 전체, cap 2 전체, cap 3 random 200,000
- Stack 단조성: cap 1 모든 pair, cap 2/3 random stable pairs
- D4 불변성: cap 1/2 전체, cap 3 random 100,000
- 반례 0

검증 원자료: `PIN_RECEIPT_RANK_VALIDATION.json`.

## 12. 범위

이 증명은 **PP rank/batch 종료성**을 완전히 닫는다.

전체 TMAM completeness에는 별도로 다음 정리가 필요하다.

- 모든 buildable pre-push가 Swappable 또는 lower-PP base의 StackClosure로 정규화된다는 normal-form completeness
- Raw Pin Push frontier soundness/completeness

이 두 정리가 주어지면 PP fixed point의 무한 반복 문제는 본 정리로 유한 `O(L)` depth로 닫힌다.


## 13. Ranking 계산 비용

`sigma(X)`는 네 열을 바닥부터 한 번 읽으므로 `O(L)` 시간, `O(1)` 추가 메모리다. PP chain 길이는 `O(L)`이므로 매 edge에서 다시 계산하는 단순 구현의 ranking 오버헤드는 `O(L^2)`이다. Frontier가 bottom-run 길이를 상태에 유지하면 edge당 `O(1)`, 전체 `O(L)`로 낮출 수 있다. 어느 경우에도 Raw Pin Push frontier의 목표 복잡도보다 낮다.
