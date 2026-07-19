# 다른 브랜치와의 병합 계약

## 1. 권장 병합 위치

저장소 루트에 다음을 추가합니다.

```text
src/shapez2_core/
tests/core_kernel/
scripts/validate_core_kernel.py
docs/core_kernel/
```

현재 패키지의 `src/shapez2_core`를 그대로 복사할 수 있습니다. 기존 `shape.py`는 이 브랜치에서 수정하지 않습니다.

## 2. 다른 에이전트가 의존할 것

### Corner/Half 브랜치

```python
CompactShape
ShapeBuilder
CutAxis
cut
rotate
canonical
is_stable
```

### Generator 브랜치

```python
crystal_generator
ForwardCall
Operation.CRYSTAL_GENERATOR
replay
```

### Stack/PP 브랜치

```python
stack
pin_push
support_positions
shatter_crystals
ForwardCall
replay
```

### TMAM 통합 브랜치

```python
CompactShape(bits, cap)
ForwardCall
Operation
replay
SEMANTICS_VERSION
```

## 3. 금지 사항

- 검색 inner loop에서 기존 mutable `Shape`를 생성하지 않기
- `Shape.MAX_LAYERS`를 변경해 상태 의미를 전달하지 않기
- `.bits`만 key로 쓰고 cap을 버리지 않기
- `stack_compact_equivalent()`를 증명 replay의 기본 Stack으로 사용하지 않기
- 색상을 core family state에 섞지 않기
- timeout을 `Impossible`로 변환하지 않기

## 4. Family 상태 key

도형 자체가 key라면 `CompactShape`를 그대로 사용합니다.

```python
seen: set[CompactShape] = set()
```

대량 후보 materialization은 `ShapeBuilder`로 수행하고 `freeze()`한 뒤 cache에 넣습니다.

회전/반사 동치가 필요한 family에서만:

```python
key = canonical(shape)
# 방향 witness도 필요하면 canonical_with_transform(shape)
```

으로 변환합니다. 방향이 제작 witness에 중요하면 canonical shape와 변환 element를 함께 저장하십시오.

## 5. Certificate 형식

각 relation candidate는 적어도 다음 정보를 가져야 합니다.

```python
@dataclass(frozen=True)
class RelationCandidate:
    outputs: tuple[CompactShape, ...]
    call: ForwardCall

assert replay(candidate.call) == candidate.outputs
```

이 계약을 지키면 전체 proof tree checker는 relation 내부 알고리즘을 신뢰할 필요가 없습니다.

## 6. Legacy UI 경계

입력 시 한 번:

```python
compact = from_legacy_shape(shape_obj)
```

최종 표시 시 한 번:

```python
shape_obj = to_legacy_shape(compact)
```

색상/subtype을 보존해야 할 때는 structural proof와 별도의 provenance map을 사용해야 합니다. `to_legacy_shape()`는 대표 색만 생성합니다.

## 7. 병합 후 필수 명령

```bash
python -m pip install -e .
pytest
PYTHONPATH=src python scripts/legacy_differential.py --cases 10000
```

마지막 감사가 통과하기 전에는 기존 `Shape` 메서드를 core delegate로 바꾸지 마십시오.

## 8. 버전 잠금

현재 의미 식별자:

```text
shapez2-quad-structural
cpcp-shape.cpp@0bc7a30b + core-kernel/0.1.0
```

다른 브랜치의 cache/certificate에는 `SEMANTICS_VERSION`을 함께 저장하십시오. 코어 의미가 바뀌면 이전 cache를 재사용하면 안 됩니다.
