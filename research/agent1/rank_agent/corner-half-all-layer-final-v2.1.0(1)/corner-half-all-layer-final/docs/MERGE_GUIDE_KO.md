# `corner-half` 병합 가이드

## 1. 병합 단위

다음 디렉터리를 하나의 단위로 병합한다.

```text
corner_half/
tests/
docs/
reports/
```

`shape.py`나 GUI 분류기를 이 브랜치에서 직접 수정하지 않는다.

## 2. core-kernel adapter

현재 `structural_physics.py`와 `structural_ops.py`는 독립 검증용 reference
kernel이다. `core-kernel` 병합 뒤에는 `interfaces.CompactPhysics`를 만족하는
adapter를 추가한다.

필수 semantics:

```python
normalize
stable
rotate
cut
swap
stack
generate
pin_push
```

그 뒤 reference kernel과 compact kernel의 결과를 동일 corpus에서 비교한다.

```text
상태/연산 결과 불일치 1건이라도 있으면 병합 금지
```

## 3. planner가 사용하는 API

빠른 membership:

```python
is_craftable_column(column)
HALF_DFA.accepts(half_code)
is_buildable_half(half_code, layers)
is_swappable_full(full_code, layers)
```

compact parent witness:

```python
construct_corner(column, layers)
construct_half(half_code, layers)
canonical_cut_inverse(half_code, layers)
swap_inverse_candidates(full_code, layers)
```

ProcessTree 또는 논문 감사가 필요한 경우에만:

```python
corner_raw_proof(column, layers)
half_raw_proof(half_code, layers)
verify_proof(root)
```

runtime 분류에서 raw DAG를 항상 만들지 않는다. 판정은 선형 API로 끝내고,
사용자가 제작 과정을 요청할 때만 witness를 확장한다.

## 4. TMAM family 연결

이 브랜치가 제공하는 기저 family:

```text
CornerFamily
HalfFamily
```

다음 `stack-pp` 브랜치는 Half를 cpcp식 concrete DB가 아니라 symbolic
rank-0 family로 사용한다.

```python
half_family.contains(h)
half_family.witness(h)
```

Half witness의 두 parent는 Corner column이다. 이 parent 경계는 변경하지
않는다.

## 5. 기존 ShapeType mapping

이 브랜치는 UI label을 결정하지 않는다. 통합 분류기는 exact facts를 받아:

```text
single active column + Corner -> *_CORNER trait
both cut halves in HalfFamily -> SWAPABLE
```

처럼 기존 `ShapeType`으로 매핑한다. Corner/Half membership 결과를 기존
regex/tracer의 fallback 뒤에 두지 말고, exact fact source로 사용한다.

## 6. 병합 후 필수 명령

```bash
PYTHONPATH=. python tests/test_corner_exact.py
PYTHONPATH=. python tests/test_stability_characterization.py
PYTHONPATH=. python tests/test_corner_constructor.py
PYTHONPATH=. python tests/test_half_constructor.py
PYTHONPATH=. python tests/test_half_automaton.py
PYTHONPATH=. python tests/test_half_inverse.py
PYTHONPATH=. python tests/test_natural_dependency.py
PYTHONPATH=.:tests python tests/test_proof_dag.py
```

대형 raw proof audit는 메모리 반환을 위해 별도 프로세스로:

```bash
PYTHONPATH=.:tests python tests/test_proof_forest.py --mode corner7
PYTHONPATH=.:tests python tests/test_proof_forest.py --mode half4
PYTHONPATH=.:tests python tests/test_proof_forest.py --mode high189
```

## 7. 금지 사항

- `UNKNOWN`을 정상 판정값으로 재도입
- timeout을 불가능으로 해석
- `Corner(left) and Corner(right)`만 보고 Half 안정성 검사를 생략
- raw proof의 synthetic helper를 leaf로 허용
- fixed-layer count 일치를 전층 증명의 대체물로 사용
