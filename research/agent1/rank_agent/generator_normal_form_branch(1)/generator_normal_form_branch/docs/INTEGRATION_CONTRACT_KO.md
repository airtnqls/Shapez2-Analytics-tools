# Generator 브랜치 통합 계약

## 브랜치 소유 범위

이 브랜치는 다음 파일만 소유한다.

```text
tmam/relations/generator.py
docs/GENERATOR_NORMAL_FORM_PROOF_KO.md
docs/INTEGRATION_CONTRACT_KO.md
tests/test_generator_normal_form.py
tests/benchmark_generator.py
patches/shape_py_crystal_generator.patch
```

`CompactShape`, 전체 physics kernel, family minimizer, planner의 공용 타입은 직접 수정하지
않는다. 통합 시 adapter로 연결한다.

## Public API

```python
GeneratorConstraint.structural(target)
GeneratorConstraint.exact(target, color)
solve_with_family(constraint, family)
solve_exact_with_family(target, family)
count_with_deterministic_family(constraint, family)
generator_forward_structural(parent)
generator_forward_exact(parent, color)
GeneratorWitness.certify()
```

## Core-kernel 브랜치와 합칠 때

현재 모듈은 셀을 `0=-, 1=S, 2=P, 3=c`, 한 층을 8비트 정수로 표현한다.
Core가 같은 표현을 사용하면 타입 alias만 공유한다. 표현이 다르면 다음 네 함수만 adapter로
교체한다.

```text
get_cell
set_cell
row_kind_mask
trim_shape
```

Generator 정리나 DP를 수정할 필요는 없다.

## Family 브랜치가 제공할 것

```python
class DeterministicLayerFamily:
    def initial_state(self): ...
    def transition(self, state, row_word): ...
    def is_accepting(self, state): ...
```

- `transition=None`은 해당 행이 family에서 불가능함을 뜻한다.
- 상태는 hashable이어야 한다.
- count가 필요하면 automaton은 결정적이어야 한다.
- witness만 필요할 경우 결정화 전 NFA를 adapter에서 subset state로 감싸도 된다.

## Planner 브랜치가 제공할 것

Generator proof node는 다음 데이터를 저장한다.

```text
operation: GENERATOR
child: predecessor proof
color: selected generator color
changed_masks: 각 층에서 -/P -> c가 된 셀
certificate: GeneratorWitness
```

기본 정책:

- `productive_only=True`
- no-op Generator 금지
- child family는 현재 target보다 낮은 proof rank
- candidate 최종 선택 후 exact color replay

Generator 간선 자체는 crystal count를 엄격히 감소시키므로, planner의 rank tie-break에
`crystal_count`를 넣을 수 있다.

## Shape.py 호환

통합 전에는 `generator_forward_project()`를 정답 adapter로 사용한다.
`shape.py` 패치 병합 후에는 다음 차등검사를 유지한다.

```python
repr(shape.crystal_generator(color)) == repr(generator_forward_project(shape, color))
```

빈 도형, trailing empty layer, 기존 다른 색 crystal, pin, 내부 gap을 반드시 포함한다.

## Merge gate

다음이 모두 통과해야 main에 합친다.

1. `python tests/test_generator_normal_form.py`
2. 2층 구조 전상 65,536개 완전 대조
3. cpcp Generator 기준 사례 4개 일치
4. exact color replay 전부 일치
5. family trie 무작위 교집합 대조
6. no-op proof edge 생성 0개
7. `Shape.py` adapter 차등검사
8. 공개 API에 GUI/PyQt import 없음
