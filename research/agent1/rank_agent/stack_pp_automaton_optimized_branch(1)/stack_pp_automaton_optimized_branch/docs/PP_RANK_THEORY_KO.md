# 일반 PP-essential rank

## 1. 왜 rank가 필요한가

다음 재귀는 허용하지 않는다.

```text
X → 임의 PinPush predecessor P → solve(P)
```

P가 X보다 단순하다는 보장이 없고 Stack/Rotate와 순환할 수 있기 때문이다.

허용되는 구조는:

```text
rank n PP target
→ PinPush predecessor
→ Stack closure of bases with rank < n
```

이다.

## 2. discovery rank

batch `n`에서 처음 발견되는 PP target X는:

1. lower-rank seed의 Stack closure에서 predecessor P가 존재
2. `PinPush(P)=X`
3. X가 Swappable이 아님
4. X가 lower-rank base로 Stackable이 아님
5. 같은 batch의 더 작은 accepted base로도 Stackable이 아님

을 만족한다.

이때 X의 `discovery_rank=n`을 저장한다.

## 3. 같은 batch cleanup

같은 batch target들 사이에:

```text
X = Stack(Y, top)
```

가 있고 Y가 더 작은 progress key를 가지면 X는 PP-essential로 저장할 필요가 없다.

progress key의 첫 성분은 visible non-crystal 수여야 한다. 비자명 Stack에서는 bottom Y가 target X보다 이 수가 엄격히 작으므로 same-batch dependency graph는 DAG다.

## 4. 후기 redundancy와 부모 보존

나중 rank에서 발견된 Y 때문에 과거 X가 Stackable이 될 수 있다.

하지만 Y의 제작 과정이 X를 사용할 수 있으므로 X를 저장소에서 삭제하면 parent chain이 끊긴다.

그래서 두 집합을 구분한다.

```text
retained entries     # 최초 발견 parent chain 보존
true PP entries      # 최종 알려진 family에서 Stack-redundant가 아닌 것
```

`PPRankResult.entries`는 retained set이고, `true_pp`는 global cleanup 결과다.

## 5. 종료성

각 PP parent의 seed rank는 자식 rank보다 엄격히 작다.

```text
n > n-1 > ... > 0 > -1(swappable/base)
```

따라서 저장된 parent certificate를 따라가면 무한 순환이 없다.

## 6. 상대적 완전성

`PPRankEngine`의 완전성은 다음 domain callback이 완전하다는 조건부다.

- batch seed 생성
- 해당 seed의 Stack closure
- Pin Push forward semantics
- Swappable membership
- family-constrained Stack witness

이 callback들을 전층 symbolic automaton으로 제공하는 것이 `core-kernel`, `corner-half`, 그리고 이 브랜치의 product-backend 통합 작업이다.

## 7. 아직 열린 전층 명제

rank를 무한히 올렸을 때 family state가:

- 유한 고정점에 도달하는지
- rank에 따라 계속 성장하지만 쿼리별로 유한한지
- 비정규 family가 되어 pushdown/tree 문법이 필요한지

는 아직 증명되지 않았다. 테스트에서 고정 rank를 멈춘 것을 전체 fixed point라고 부르면 안 된다.
