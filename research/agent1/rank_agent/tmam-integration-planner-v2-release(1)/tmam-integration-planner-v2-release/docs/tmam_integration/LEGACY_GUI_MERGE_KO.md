# 레거시 PyQt GUI 실제 병합 지점

이 문서는 기존 `gui.py` 레이아웃/위젯을 유지하고 backend 호출만 교체하는 최소 변경안이다.

## 유지하는 클래스/기능

- `ShapeWidget`, `QuadrantWidget`, 행·열 drag/drop
- brush, Undo/Redo, 동적 A/B/C… 입력
- 정방향 연산 버튼과 출력 영역
- Batch 탭과 regex 검색
- QSettings, i18n, 로그 패널
- `QGraphicsScene/QGraphicsView` 공정트리 renderer
- 테스트 편집기

## 앱 시작 시 한 번만 생성

```python
self.tmam_runtime = build_project_runtime(...)
self.tmam_service = TMAMApplicationService(self.tmam_runtime)
```

버튼·탭별로 새 Planner/Runtime을 만들면 캐시 공유가 사라지므로 금지한다.

## 1. 빠른 가능 여부

기존 `exist` 동작 또는 별도 버튼:

```python
view = self.tmam_service.check_possible(shape, progress)
# POSSIBLE / IMPOSSIBLE / UNKNOWN만 표시
```

여기서는 ShapeType, reason 문자열, 최소비용, ProcessTree를 만들지 않는다.

## 2. 분류 라벨

기존 `_add_classification_widgets()`의 `shape.classifier()` 호출을 다음으로 교체한다.

```python
view = self.tmam_service.detailed_analysis(shape, progress)
classification = view.shape_type
status = view.status
```

같은 target을 다시 표시할 때 Runtime cache에서 동일 GoalAnalysis를 가져온다.

## 3. 공정트리

기존 `process_tree_solver()` 또는 ShapeType별 tracer 재귀를 호출하지 않는다.

```python
view = self.tmam_service.detailed_analysis(shape, progress)
bundle = proof_to_precomputed_process_tree(
    view.proof,
    shape_factory=Shape.from_string,
    root_classification=view.shape_type.value,
)
self.process_tree_solver.nodes_map = dict(bundle.nodes_map)
root = bundle.root
self.render_process_tree(root)
```

렌더러가 `nodes/root_id` dict를 받는 경로라면:

```python
tree_data = self.tmam_service.process_tree_from_analysis(view)
root = self.process_tree_solver.create_tree_from_data(tree_data)
```

## 4. OriginFinderThread 대체

기존 thread가 Physics/PinPush/Generator/Stack/Cut/Swap을 각각 호출하는 구조 대신 목적을 명시한다.

```text
빠른 첫 제작 증명  → solve_exists
최소 제작 증명      → solve_min_cost
가능한 마지막 연산  → analyze_all_ops.operations
```

상세 후보 browser가 필요하면 Runtime의 cached `ProviderEvaluation`을 읽고, provider를 직접 재호출하지 않는다.

## 5. 테스트 편집기

기존 `classifier` 테스트는 `detailed_analysis().shape_type`을 비교한다.

추가 권장 operation:

```text
possible
minimum_proof
all_ops
proof_replay
unknown_reason
```

## 6. thread 취소

Planner가 provider를 강제로 중단시키지는 않는다. 장시간 provider는 상위 provider 계약에서 cancel/resource budget을 확인하고 `ProviderResourceLimit` 또는 partial coverage로 종료해야 한다. 이 결과는 반드시 UNKNOWN이다.

## 병합 후 제거 대상

- GUI에서 `ReverseTracer.inverse_*` 직접 호출
- GUI에서 `shape.classifier()` 반복 호출
- ProcessTree 생성 중 기존 classifier/tracer 재귀
- timeout을 불가능으로 표시하는 코드
- 별도 solve 후 별도 analyze 호출로 provider를 재실행하는 코드
