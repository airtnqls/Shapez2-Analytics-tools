# 병합 순서

## 1. tmam-integration 단독 병합 가능

이 브랜치는 기존 `shape.py`, `shape_classifier.py`, tracer 파일을 수정하지 않는다. 고유 이름의 `tmam/` 패키지와 `tests/tmam_integration`, `docs/tmam_integration`만 추가하므로 먼저 main에 병합할 수 있다.

## 2. core-kernel

- `ShapeBackend`
- `ForwardModel`
- CompactShape serialization/canonicalization

을 연결한다.

## 3. corner-half + generator

각 plugin을 등록하고 provider별 unit/differential test를 실행한다.

## 4. stack-pp

family-constrained Stack와 PP rank provider를 등록한다. `Progress` 감소 테스트를 반드시 통과해야 한다.

## 5. required relation manifest 확정

모든 구조 연산 provider ID를 `PlannerConfig.required_relation_ids`에 넣는다. 이 시점 전에는 `IMPOSSIBLE`을 제품 UI에 노출하지 않는다.

## 6. legacy adapter 전환

기존 `analyze_shape()` 내부를 한 번에 삭제하지 않는다.

```text
legacy classifier
→ shadow mode로 새 runtime 동시 실행
→ 결과 차이 로그
→ 의도된 차이/legacy bug 분류
→ UI 반환을 새 policy로 전환
```

## 7. ProcessTree 전환

`proof_to_legacy_tree()` payload를 기존 GUI node에 연결한다. 이후 타입별 tracer 호출은 제거하고 proof 자체에서 tree를 만든다.
