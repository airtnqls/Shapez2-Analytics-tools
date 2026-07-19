# Proof DAG와 비용 모델

## ProofNode

모든 노드는 다음을 가진다.

- canonical shape key/code
- well-founded progress
- 마지막 operation
- ordered child proofs
- replay certificate
- local cost / total cost
- traits / metadata

`ProofValidator`는 다음을 검사한다.

1. cycle 없음
2. child progress 엄격 감소
3. shape key canonical
4. 독립 forward replay가 target과 동일

## 비용

기본 `LexicographicCostModel`은 다음 순서다.

```text
operations
buildings
inputs
pin_pushes
generators
stackers
swappers
cutters
rotators
painters
peak_height
auxiliary_cells
```

프로젝트 목적에 맞게 순서를 교체할 수 있다.

- Tree model: 모든 child 비용 합
- Critical path model: 병렬 child 중 가장 느린 경로
- Unique-shape metrics: 같은 중간 shape 생산라인 재사용을 가정한 참고 비용

비용 정책은 proof correctness와 분리한다. 같은 proof 후보 집합에서 선택 순서만 바뀐다.
