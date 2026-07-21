# Half residual 기반 exact StackClosure

## 문제

기존 `findStackWitness()`는 네 열의 split height 후보를 Cartesian product로 열거한다.
높이 `L`에서 각 열이 `O(L)` 후보를 가지므로 후보 수가 최악 `O(L^4)`이고,
각 후보마다 bottom 생성, Swappable 재판정, Stack replay를 다시 수행한다.

이 방식은 다음 정보를 공유하지 못한다.

- 같은 prefix가 만드는 동일한 Stack ownership 상태
- bottom 두 Half의 동일한 미래 residual language
- 동일한 축과 동일한 열 전환 상태
- 실패한 prefix의 negative result

## 교체 구조

생산 판정은 `lib/stack-closure-dp.ts`의
`findSwappableStackWitness()`를 사용한다.

한 층을 아래에서 위로 읽으며 상태를 다음처럼 유지한다.

```text
(axis,
 switchedMask,
 hasBottom,
 firstHalfResidual,
 secondHalfResidual,
 endedBits)
```

- `axis`: cutter 축 2개 중 하나
- `switchedMask`: 이미 top piece 소유로 전환된 4개 열의 단조 4-bit mask
- `firstHalfResidual`, `secondHalfResidual`: 전층 최소 210-state Half DFA 상태
- `endedBits`: 각 Half가 trailing-empty 구간에 들어갔는지 여부
- `hasBottom`: 빈 bottom을 Stack base로 허용하지 않기 위한 비트

각 target row에서 아직 전환되지 않은 non-crystal occupied cell의 부분집합만
새 top 시작점으로 선택한다. 새 top row는 다음 exact landing 조건을 만족해야 한다.

1. crystal을 포함하지 않는다.
2. pin은 바로 아래 target cell의 support를 가진다.
3. ordinary connected component마다 바로 아래 support가 하나 이상 있다.

bottom row는 ownership mask의 여집합이다. 두 cutter half row를 각각 Half DFA에
전이시킨다. 동일 product state는 하나만 남기고 최소 visible-top cost backpointer만
보관한다.

## 정확성

### Soundness

accept state가 나오면:

1. 두 bottom half residual이 모두 Half accepting state다.
2. 따라서 bottom은 `Swappable` family에 속한다.
3. 모든 top row는 crystal-free이며 exact landing 조건을 만족한다.
4. backpointer로 복원한 bottom과 top-piece sequence를 실제 `stackShapes()`로
   정방향 replay한다.
5. replay가 target과 다르면 contract failure를 발생시키고 양성으로 반환하지 않는다.

### Completeness

임의의 유효 Stack decomposition을 아래에서 위로 읽으면 각 열은 bottom 소유에서
top 소유로 최대 한 번만 전환되므로 단조 `switchedMask` 경로가 된다. 각 층의 top
piece는 실제 replay에서 해당 층에 착지하므로 local landing 조건을 만족한다.
bottom의 두 Half는 Swappable 정의에 의해 Half DFA accepting residual로 끝난다.
따라서 모든 유효 decomposition은 product 경로 하나를 만든다.

두 prefix를 합치는 조건은 다음 미래 충분통계가 모두 같은 경우뿐이다.

- cutter axis
- switched columns
- bottom 존재 여부
- 두 Half의 exact residual language
- trailing-empty 종료 여부

고정 target suffix에서 향후 가능한 transition과 acceptance는 이 상태만으로
결정되므로 병합해도 유효 경로가 사라지지 않는다.

## 복잡도

기존:

```text
split candidates: O((L+1)^4)
각 후보마다 Swappable + replay: O(L)
최악 상한: O(L^5)
```

새 target product:

```text
O(L * R * 2^4)
```

여기서 `R`은 해당 target에서 실제 도달한 product state 수다. 폭 4는 고정이고,
Half residual은 유한 210-state이므로 층수에 대해 polynomial target scan이다.
전수 DFA 전체를 미리 powerset determinize하지 않고 target에 필요한 상태만 만든다.

## 검증

`tests/stack-closure-dp.test.ts`는 다음을 수행한다.

1. cap 2 oriented Half 전수 256개에서 기존 theorem predicate와 DFA 일치
2. cap 2 shape deterministic sweep에서 기존 Swappable predicate와 residual product 일치
3. cap 1 전체 256 target에서 독립 ownership brute oracle과 Stack DP 일치
4. cap 2 deterministic 2,115 target에서 독립 ownership brute oracle과 일치
5. 50층 실제 Stack replay target에서 witness 복원 및 state/transition 상한 확인

기존 `findStackWitness()`는 삭제하지 않고 differential oracle로만 남긴다. 생산
`classifyShape()`와 `classifyShapeFast()`는 exact product를 사용해야 한다.
