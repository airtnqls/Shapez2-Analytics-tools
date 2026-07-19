# cpcp 구조와 이 브랜치의 대응

| cpcp 개념 | `stack-pp` 대응 |
|---|---|
| HalfSet | `HalfFamily` protocol |
| Swappable test | `PPRankDomain.is_swappable` |
| Stackability height vectors | Stack frontier × family product |
| Stack closure enumeration | `PPRankDomain.stack_closure` |
| PP batch | `PPRankEngine` batch |
| PPParent(bits,batch) | `PinPushCertificate` + `PPEntry` |
| current batch cleanup | same-batch well-founded cleanup |
| earlier leftovers retained | `retained_for_parent_chain` |
| true PP count | `PPRankResult.true_pp` |
| build_plan lower batch condition | `seed_rank < discovery_rank` invariant |

중요한 차이:

- cpcp는 고정 cap의 concrete set을 사용한다.
- 이 브랜치는 all-layer merge를 위해 family/closure를 protocol로 추상화한다.
- concrete oracle은 작은 층 차등검증에만 사용한다.
