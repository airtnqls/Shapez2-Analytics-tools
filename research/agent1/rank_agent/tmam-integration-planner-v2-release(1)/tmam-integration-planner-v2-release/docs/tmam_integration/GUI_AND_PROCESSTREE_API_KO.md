# GUI 및 기존 ProcessTree 연동 API

## 공용 service

```python
service = TMAMApplicationService(runtime)
```

### 빠른 가능 여부

```python
view = service.check_possible(shape, progress)
# 내부: solve_exists
```

표시:

- POSSIBLE / IMPOSSIBLE / UNKNOWN
- 첫 witness가 있으면 간단 미리보기

비용 비교, 분류, reason 문자열, ProcessTree를 생성하지 않는다.

### 최소 비용 제작 경로

```python
view = service.minimum_proof(shape, progress)
# 내부: solve_min_cost
```

표시:

- 최소 proof
- total cost
- `optimal` 여부

### 상세 분석 및 분류

```python
view = service.detailed_analysis(shape, progress)
# 내부: analyze_all_ops
```

표시:

- 기존 ShapeType
- 가능한 마지막 연산
- strict Claw 사실
- PP rank / Stack depth
- partial/missing provider 이유
- 최소 proof

## ProcessTree

```python
tree_data = service.process_tree_from_analysis(view)
```

반환 형식은 기존 `ProcessTreeSolver.create_tree_from_data()`가 읽는 형태이다.

```python
{
    "nodes": {
        "TMAM_<digest>": {
            "shape_code": "...",
            "operation": "stack",
            "input_ids": ["...", "..."],
            "cost": {...},
            "traits": [...],
            "metadata": {...},
        }
    },
    "root_id": "TMAM_<digest>",
}
```

이 변환은 이미 존재하는 ProofNode DAG만 순회한다. Claw/Hybrid tracer나 classifier를 다시 실행하지 않는다.


## 기존 ProcessNode 객체가 필요한 경우

```python
from tmam import proof_to_precomputed_process_tree

bundle = proof_to_precomputed_process_tree(
    view.proof,
    shape_factory=Shape.from_string,
    root_classification=view.shape_type.value,
)
root = bundle.root
nodes_map = bundle.nodes_map
```

`PrecomputedProcessNode`는 `shape_code / operation / node_id / input_ids / shape_obj`를 제공하지만 생성자에서 legacy classifier를 호출하지 않는다. 따라서 기존 QGraphics renderer를 유지하면서 분류·Claw·Hybrid 역산의 재실행을 제거할 수 있다.

## 레거시 GUI 변경 지점

```text
빠른 존재성 버튼       → service.check_possible
최소 제작 경로 버튼    → service.minimum_proof
기존 classifier 표시   → service.detailed_analysis.shape_type
공정 트리 탭           → service.process_tree_from_analysis
```

기존 ShapeWidget, drag/drop, brush, Batch, QSettings, i18n, tree renderer는 유지한다.

## QThread

기존 GUI의 QThread wrapper 안에서 위 service 메서드 하나를 호출한다. 동일 planner/runtime 인스턴스를 재사용해야 캐시가 공유된다. 버튼마다 새 planner를 생성하면 중복 제거 효과가 사라진다.
