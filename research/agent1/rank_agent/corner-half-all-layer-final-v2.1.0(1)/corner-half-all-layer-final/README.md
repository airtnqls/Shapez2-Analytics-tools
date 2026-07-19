# Shapez2 TMAM — `corner-half` all-layer branch

이 패키지는 다음 다섯 항목을 전층에서 해결한다.

1. Corner membership과 concrete constructor
2. Half membership과 concrete constructor
3. Half family soundness/completeness
4. Cut/Swap용 일반 Half inverse
5. Half symbolic closure와 최소 상태 표현

## 주정리

```text
Corner(w)
<=> w avoids the six forbidden column patterns

BuildableHalf(u,v)
<=> Corner(u) and Corner(v) and Stable(u,v)

Swappable(X)
<=> one of the two cutter-axis orientations has
    EastHalf(X) in HalfFamily and WestHalf(X) in HalfFamily
```

## 최소 automata

- Corner: 19-state minimal DFA
- 두 열 공동 안정성: 6-state minimal DFA
- 전층 oriented Half family: **210-state minimal DFA**

Half 원시 product 상한은 `19*19*6=2,166`, 실제 reachable product는 552,
Hopcroft 최소화 결과는 210이다. 210개 상태는 전부 도달 가능하고 서로 다른
21,945개 상태 쌍 모두 distinguishing suffix가 존재한다.

## 복잡도

```text
Corner membership       Theta(L)
Half membership         Theta(L)
Half count up to cap L  Theta(L) big-integer DP
Swappable existence     Theta(L)
compact witness         O(L)
raw operation DAG       실제 출력 proof 크기에 비례
```

고정층 pattern table, concrete Half DB, timeout rejection, `UNKNOWN`은 없다.

## 빠른 사용

```python
from corner_half import (
    HALF_DFA,
    is_craftable_column,
    construct_corner,
    corner_raw_proof,
    is_buildable_half,
    construct_half,
    half_raw_proof,
    canonical_cut_inverse,
    swap_inverse_candidates,
    verify_proof,
)

w = "PcS-S-c"
assert is_craftable_column(w)
assert construct_corner(w, 7).replay_ok
assert verify_proof(corner_raw_proof(w, 7)).replay_ok

half_code = "SS--:cS--"
assert is_buildable_half(half_code, 2)
assert HALF_DFA.accepts(half_code)
assert construct_half(half_code, 2).replay_ok
assert verify_proof(half_raw_proof(half_code, 2)).replay_ok

cut_parent = canonical_cut_inverse(half_code, 2)
assert cut_parent.replay_ok

for inverse in swap_inverse_candidates("SSSS", 1):
    assert inverse.replay_ok
```

raw proof DAG의 유일한 잎은 한 층 `SSSS`이고, 내부 노드는 정확히 다음 중
하나다.

```text
ROTATE CUT SWAP STACK GENERATE PIN_PUSH
```

## 증명 문서

- `docs/CORNER_CONSTRUCTOR_PROOF_KO.md`
- `docs/CORNER_HALF_MUTUAL_INDUCTION_KO.md`
- `docs/C7_STRUCTURAL_COMPILER.md`
- `docs/HALF_FAMILY_THEOREM_KO.md`
- `docs/HALF_SYMBOLIC_CLOSURE_MINIMALITY_KO.md`
- `docs/CUT_SWAP_HALF_INVERSE_KO.md`
- `docs/RAW_OPERATION_PROOF_DAG_KO.md`

## 핵심 검증

```bash
PYTHONPATH=. python tests/test_corner_exact.py
PYTHONPATH=. python tests/test_corner_constructor.py
PYTHONPATH=.:tests python tests/test_corner_full_replay.py
PYTHONPATH=. python tests/test_half_automaton.py
PYTHONPATH=. python tests/test_half_inverse.py
PYTHONPATH=. python tests/test_natural_dependency.py

PYTHONPATH=.:tests python tests/test_proof_forest.py --mode corner7
PYTHONPATH=.:tests python tests/test_proof_forest.py --mode half4
```

전체 수치는 `reports/FINAL_ACCEPTANCE.json`과
`reports/VALIDATION_ALL_LAYER_COMPLETE.json`에 있다. 전체 수락 묶음은:

```bash
./run_acceptance.sh
```

최종 재감사 설명은 `docs/FINAL_REAUDIT_KO.md`를 본다.
