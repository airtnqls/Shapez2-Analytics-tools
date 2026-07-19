from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

from .proof import ProofNode, proof_to_legacy_tree

ShapeT = TypeVar("ShapeT")


@dataclass
class PrecomputedProcessNode(Generic[ShapeT]):
    """Renderer-compatible node that never invokes the legacy classifier."""

    shape_code: str
    operation: str
    node_id: str
    input_ids: list[str]
    shape_obj: ShapeT | None = None
    classification: str = ""
    classification_reason: str = ""

    def is_valid(self) -> bool:
        return self.shape_obj is not None or bool(self.shape_code)


@dataclass(frozen=True)
class LegacyProcessTreeBundle(Generic[ShapeT]):
    root: PrecomputedProcessNode[ShapeT]
    nodes_map: Mapping[str, PrecomputedProcessNode[ShapeT]]
    tree_data: Mapping[str, object]


def proof_to_precomputed_process_tree(
    proof: ProofNode[ShapeT],
    *,
    shape_factory: Callable[[str], ShapeT] | None = None,
    root_classification: str = "",
    root_reason: str = "",
) -> LegacyProcessTreeBundle[ShapeT]:
    """Build legacy renderer nodes from an already solved proof.

    Parsing Shape objects is optional.  No Shape.classifier(), inverse relation,
    Claw tracer, or Hybrid tracer is called.
    """

    data = proof_to_legacy_tree(proof)
    raw_nodes = data["nodes"]
    nodes: dict[str, PrecomputedProcessNode[ShapeT]] = {}
    for node_id, row in raw_nodes.items():
        code = str(row["shape_code"])
        shape_obj = shape_factory(code) if shape_factory is not None else None
        nodes[node_id] = PrecomputedProcessNode(
            shape_code=code,
            operation=str(row["operation"]),
            node_id=node_id,
            input_ids=list(row["input_ids"]),
            shape_obj=shape_obj,
        )
    root_id = str(data["root_id"])
    root = nodes[root_id]
    root.classification = root_classification
    root.classification_reason = root_reason
    return LegacyProcessTreeBundle(root, nodes, data)
