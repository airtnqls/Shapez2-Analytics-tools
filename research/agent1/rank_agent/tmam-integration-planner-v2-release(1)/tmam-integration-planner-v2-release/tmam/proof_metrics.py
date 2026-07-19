from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Generic, TypeVar

from .cost import CostVector
from .proof import ProofNode

ShapeT = TypeVar("ShapeT")


@dataclass(frozen=True)
class ProofMetrics:
    tree_nodes: int
    unique_nodes: int
    unique_shapes: int
    max_depth: int
    stack_depth: int
    pin_push_depth: int
    operation_counts: dict[str, int]
    unique_shape_cost: CostVector


def collect_proof_metrics(root: ProofNode[ShapeT]) -> ProofMetrics:
    tree_nodes = 0
    max_depth = 0
    operations: Counter[str] = Counter()
    node_digests: set[str] = set()
    shape_keys: set[str] = set()
    unique_cost = CostVector()
    charged_shapes: set[str] = set()

    def visit(node: ProofNode[ShapeT], depth: int) -> None:
        nonlocal tree_nodes, max_depth, unique_cost
        tree_nodes += 1
        max_depth = max(max_depth, depth)
        operations[node.operation.value] += 1
        node_digests.add(node.stable_digest())
        shape_keys.add(node.shape_key)
        if node.shape_key not in charged_shapes:
            charged_shapes.add(node.shape_key)
            unique_cost = unique_cost + node.local_cost
        for child in node.children:
            visit(child, depth + 1)

    visit(root, 1)
    return ProofMetrics(
        tree_nodes=tree_nodes,
        unique_nodes=len(node_digests),
        unique_shapes=len(shape_keys),
        max_depth=max_depth,
        stack_depth=root.stack_depth,
        pin_push_depth=root.pin_push_depth,
        operation_counts=dict(sorted(operations.items())),
        unique_shape_cost=unique_cost,
    )
