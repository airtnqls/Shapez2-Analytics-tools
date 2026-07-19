# Generator 브랜치 handoff

## 권장 브랜치명

```text
feature/generator-normal-form
```

## 커밋 순서

### Commit 1 — relation + proof + tests

```text
add all-layer generator relation and constrained inverse
```

포함:

```text
tmam/relations/generator.py
generator_normal_form.py
tests/test_generator_normal_form.py
tests/test_generator_laws.py
tests/property_generator_10000.py
tests/benchmark_generator.py
docs/*
reports/*
```

### Commit 2 — Shape facade 의미 수정

```text
fix crystal generator global-height semantics
```

`patches/shape_py_crystal_generator.patch`만 적용한다. Core-kernel 브랜치가 먼저 `shape.py`를
바꿨다면 직접 cherry-pick하지 말고 새 facade가 아래 세 조건을 만족하는지만 검사한다.

```text
empty -> empty
trailing empty layers ignored
no gravity after full fill
```

### Commit 3 — 외부 family adapter

Half/Stack/PP 브랜치의 최종 family 타입이 정해진 뒤 작은 adapter만 추가한다.
Generator 본문의 DP와 증명은 건드리지 않는다.

## 충돌 가능 파일

```text
shape.py                         core-kernel과 충돌 가능
planner/proof.py                 이 브랜치가 수정하면 안 됨
core/compact_shape.py            이 브랜치가 수정하면 안 됨
classification/shape_types.py    이 브랜치가 수정하면 안 됨
```

## 통합 책임자에게 전달할 핵심

1. Generator는 `ShapeType`이 아니라 proof operation이다.
2. 목표가 full/pin-free가 아니면 Generator last-op branch를 즉시 닫는다.
3. 일반 전상 열거를 금지한다.
4. `GeneratorConstraint`를 lower-rank family DFA와 product한다.
5. `productive_only=True`를 기본으로 no-op 순환을 차단한다.
6. witness의 `changed_masks`는 color provenance와 blueprint parameter로 재사용한다.
7. 모든 최종 후보는 exact forward replay한다.

## 다른 브랜치가 재사용할 정리

- 마지막 Generator 직후에는 높이 아래에 빈칸과 핀이 없다.
- 마지막 Generator 뒤에 보이는 핀은 반드시 그 이후 연산에서 생겼다.
- 마지막 Generator 뒤에 보이는 내부 gap은 반드시 그 이후 crystal 파괴/낙하로 생겼다.
- Generator는 높이를 보존한다.
- Generator는 회전·반사와 교환한다.
- 연속 Generator는 두 번째 이후가 no-op이므로 최소 증명에서 하나만 남는다.
- 생산적 역간선은 crystal count를 엄격히 감소시킨다.
