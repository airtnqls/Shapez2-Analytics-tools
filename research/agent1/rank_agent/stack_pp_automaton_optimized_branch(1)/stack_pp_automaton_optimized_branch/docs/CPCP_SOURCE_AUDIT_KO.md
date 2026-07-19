# cpcp 소스 감사와 `stack-pp` 대응

기준 commit:

```text
cpcp1998/shapez2-solver
4a53244ce4333dd16bf5f93b14a38793cf8b4a2f
```

## 1. PPParent

cpcp의 `PPParent`는:

```text
낮은 60비트: pre-push shape
높은 4비트: batch
```

이고 raw integer 최소화로:

```text
더 이른 batch
→ 같은 batch이면 더 작은 predecessor
```

를 결정론적으로 선택한다.

이 브랜치의 대응:

```python
PPRankEngine._parent_order_key
PinPushCertificate
```

## 2. batch seed

cpcp:

```text
batch 0: base-half 두 개를 합친 full shape
batch n≥1: 직전 batch의 새 PP shape
```

이 브랜치:

```python
PPRankDomain.seeds_for_batch
```

Half 구현 방식은 domain adapter가 소유하고 rank engine은 seed 의미를 가정하지 않는다.

## 3. Stackable-from-known

cpcp의 base predicate:

```text
is_swappable(base) OR pp_set.contains(base)
```

Stackability는 단순 top 한 층 제거가 아니라 열별 split height vector를 검사하고, stacked zone의 각 NORMAL arc가 anchor에 닿는지 확인한다. Crystal이 stacked zone에 남는 split은 금지된다.

이 브랜치:

```python
PPRankDomain.stack_witness(target, allowed_base)
```

필수 조건:

- 모든 height-vector/layer-piece decomposition에 완전
- `allowed_base`까지 여러 stack layer를 한 번에 벗김
- witness는 base + piece sequence를 보존

## 4. pushed result 분류

cpcp 순서:

```text
empty → skip
swappable → skip
known stackable → skip
else PP set insert
```

known PP target이 다시 발견되면 비싼 분류는 건너뛰지만 parent atomic-min에는 참여한다.

이 브랜치도 같은 batch 안의 중복 target parent를 모두 비교하고 가장 작은 predecessor를 저장한다. 이미 더 이른 batch에 저장된 target은 뒤 batch parent가 이길 수 없으므로 재기록하지 않는다.

## 5. cleanup

cpcp는 batch의 모든 새 target을 PP set에 넣고 한 번 재검사한다. Stack base membership에서 shape를 제거하면 predicate가 약해지므로, 제거 뒤 새로 removable이 되는 survivor는 없다.

Stack base는 target의 proper prefix이므로 visible normal/pin 수가 엄격히 작다. 따라서 same-batch dependency는 이 progress measure에 대해 DAG다.

이 브랜치는 이 사실을 명시적으로 사용해 progress-key 오름차순으로 결정론적 cleanup을 수행한다. 완전한 `stack_witness`가 transitive layer decomposition을 반환한다는 조건에서 cpcp의 한-pass cleanup과 같은 survivor set을 얻는다.

## 6. retained와 true PP

cpcp는 나중 PP가 추가되어 과거 shape가 stackable이 되어도 과거 entry를 지우지 않는다. 후손 build plan이 그 entry를 부모로 사용하기 때문이다. 마지막에 dry-run으로:

```text
parent chain 때문에 남긴 수
true PP 수
```

를 따로 보고한다.

이 브랜치:

```python
PPRankResult.entries                    # retained
PPRankResult.global_redundant
PPRankResult.true_pp
PPRankResult.retained_for_parent_chain
```

## 7. Stack ProofNode

cpcp build plan은 stacked zone을 비어 있지 않은 각 layer의 `InputNode`로 분리한다. 즉 arbitrary top shape를 다시 일반 TMAM으로 재귀 호출하지 않는다.

이 브랜치도 최종 product backend에서:

```text
base A + finite layer-piece sequence
```

형태의 certificate를 내도록 계약을 고정한다. 현재 raw frontier adapter의 bundled B는 호환용이며 `StackCertificate.pieces`로 layer pieces를 제공할 수 있게 확장했다.

## 8. 차이와 의도

| 항목 | cpcp | 이 브랜치 |
|---|---|---|
| 층수 | compile-time fixed cap | all-layer protocol |
| shape set | concrete PP hash set | symbolic family adapter |
| stack closure | concrete DFS | family product frontier 예정 |
| cleanup | concurrent PP set pass | deterministic progress-order pass |
| parent | packed uint64 | typed certificate |
| proof termination | lower batch | strict rank certificate |
| full seen set | 없음 | 없음 |
