# 기존 ShapeType mapping 정책

내부 solver는 단일 ShapeType을 직접 만들지 않는다. 먼저 다음 사실을 계산한다.

- buildable / impossible / incomplete
- 가능한 마지막 연산 집합
- strict Claw 여부
- PP rank
- Stack depth
- active column 수
- proof traits

그 뒤 `ClassificationPolicy`가 기존 UI enum으로 접는다.

## 기본 precedence

```text
EMPTY
BASIC
Corner variants
(crystal-free legacy compatibility) SIMPLE
strict CLAW
CLAW_HYBRID / CLAW_COMPLEX_HYBRID
HYBRID / COMPLEX_HYBRID
SWAPABLE
SIMPLE
IMPOSSIBLE / UNKNOWN
```

`LEGACY_COMPAT` 모드에서는 기존 classifier처럼 crystal-free buildable shape를 먼저 SIMPLE로 표시한다. `PROOF_FIRST` 모드에서는 proof 구조를 우선할 수 있다.

## Hybrid 구분

권장 정의:

- `HYBRID`: root가 canonical Stack이고 Stack depth 1
- `COMPLEX_HYBRID`: Stack depth 2 이상 또는 non-canonical Stack
- `CLAW_HYBRID`: 위 조건 + bottom family가 strict Claw
- `CLAW_COMPLEX_HYBRID`: Claw base + complex Stack

이는 예전 “어느 rescue 함수가 성공했는가”보다 재현 가능하고 전층 독립적이다.

## Corner

Corner는 독립 제작 타입이 아니라 `active_columns == 1`이라는 trait이다. 본 제작 proof와 조합해 기존 corner enum을 선택한다.
