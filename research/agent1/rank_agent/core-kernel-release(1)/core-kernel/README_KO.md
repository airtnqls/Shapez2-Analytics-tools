# Shapez 2 Core Kernel — `core-kernel` 브랜치

전층 TMAM 연구가 공유할 **불변·구조 전용 물리 코어**입니다. 기존 프로젝트의 `shape.py`를 직접 교체하지 않고, 검색·family automaton·proof replay의 내부 표현을 이 패키지로 통일합니다.

## 현재 상태

완료된 범위:

- 셀당 2비트, 층당 1바이트의 `CompactShape`
- Python 정수 기반 임의 유한 cap
- 정확한 Gravity / Crystal shatter
- Rotate / Mirror / Cut / Swap / Stack / Pin Push / Crystal Generator
- 회전·반사 canonicalization
- `ForwardCall` 기반 proof replay 공통 인터페이스
- 기존 mutable `Shape` 객체와의 양방향 adapter
- 독립 list 기반 느린 참조 구현
- 작은 층 전수 차등검사, 고층 속성검사, 사용자 코퍼스 검사

이 브랜치가 해결하지 않는 것:

- Corner/Half/Claw/Hybrid family membership
- 역연산과 제작 가능성 판정
- 색상 및 일반조각 subtype provenance
- 비용 최적화와 전체 TMAM planner

## 설치

```bash
cd core-kernel
python -m pip install -e .
pytest
```

외부 런타임 의존성은 없습니다. 테스트에만 `pytest`가 필요합니다.

## 기본 사용법

```python
from shapez2_core import (
    CompactShape,
    apply_gravity,
    pin_push,
    stack,
)

x = CompactShape.parse("SPc-:-S-P", cap=10)
stable = apply_gravity(x)
pushed = pin_push(stable)
result = stack(stable, pushed)

print(result.to_structural())
print(result.bits, result.cap)
```

대량 witness를 만들 때는 mutable `ShapeBuilder`를 사용하고, 상태 저장 전 `freeze()`하여 `CompactShape`로 바꿉니다. Builder 자체를 set/dict key로 사용하면 안 됩니다.

구조 코드는 아래 네 문자만 사용합니다.

```text
-  empty
S  any ordinary part
P  pin
c  crystal
```

정확한 8문자/층 게임 코드도 읽을 수 있습니다. `C/R/S/W/H/F/G/X/Y`는 모두 구조상 `S`로 접힙니다.

## 다른 브랜치가 사용할 API

```python
from shapez2_core import (
    CompactShape,
    CutAxis,
    ForwardCall,
    Operation,
    apply_gravity,
    canonical,
    crystal_generator,
    cut,
    is_stable,
    pin_push,
    replay,
    rotate,
    stack,
    swap,
)
```

증명 노드는 직접 연산 함수를 호출해도 되지만, 병합 시에는 다음 형식을 권장합니다.

```python
call = ForwardCall(
    operation=Operation.STACK,
    parents=(bottom, top),
    parameters={},
)
assert replay(call) == (target,)
```

## 핵심 계약

1. `CompactShape`는 immutable/hashable입니다.
2. `cap`은 전역변수가 아니라 값의 일부입니다.
3. 모든 공개 연산은 pure function입니다.
4. 구조 비교는 색상과 일반 subtype을 무시합니다.
5. 검색 결과의 최종 certificate는 `replay()`로 재생해야 합니다.
6. 같은 `bits`라도 cap이 다르면 overflow 미래가 다르므로 서로 다른 상태입니다.
7. family 브랜치는 기존 `shape.py` 내부 메서드나 PyQt를 검색 inner loop에서 호출하지 않습니다.

## 검증 실행

빠른 테스트:

```bash
PYTHONPATH=src pytest
```

독립 참조와 장시간 감사:

```bash
PYTHONPATH=src python scripts/validate_kernel.py \
  --medium-cases 5000 \
  --large-differential-cases 50 \
  --high-property-cases 0 \
  --output reports/validation_exact.json
```

실제 `Shapez2-Analytics-tools` 저장소 안에서 adapter까지 검사:

```bash
PYTHONPATH=src python scripts/legacy_differential.py \
  --cases 10000 --max-cap 20
```

현재 실행 환경에는 저장소 전체와 PyQt runtime이 없어서 마지막 스크립트는 제공만 하고 실행하지 않았습니다. 나머지 감사 결과는 `reports/`에 저장되어 있습니다.

## 파일 구성

```text
src/shapez2_core/
├── model.py            immutable packed representation
├── tables.py           256 layer lookup tables
├── kernel.py           optimized exact physics and operations
├── reference.py        independent slow oracle
├── legacy_adapter.py   repository Shape bridge
└── protocol.py         branch integration/replay contract
```

자세한 물리 정의는 `docs/PHYSICS_SPEC_KO.md`, 병합 규칙은 `docs/MERGE_GUIDE_KO.md`를 참고하십시오.
