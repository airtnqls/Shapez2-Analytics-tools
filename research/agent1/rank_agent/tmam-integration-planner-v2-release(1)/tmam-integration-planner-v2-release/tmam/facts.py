from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Mapping, TypeVar

from .contracts import ShapeBackend
from .enums import Decision, Operation, ProofStatus
from .planner import GoalAnalysis
from .proof import ProofNode

ShapeT = TypeVar("ShapeT")


@dataclass(frozen=True)
class ShapeFacts(Generic[ShapeT]):
    shape: ShapeT
    shape_key: str
    empty: bool
    has_crystal: bool
    active_columns: tuple[int, ...]
    buildable: Decision
    analysis_complete: bool
    possible_last_operations: frozenset[Operation]
    operation_decisions: Mapping[Operation, Decision]
    minimum_proof: ProofNode[ShapeT] | None
    strict_claw: Decision
    is_corner: bool
    operation_proofs: Mapping[Operation, ProofNode[ShapeT] | None] = field(default_factory=dict)
    minimum_pp_rank: int | None = None
    stack_depth: int | None = None
    traits: frozenset[str] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=dict)


def facts_from_analysis(
    backend: ShapeBackend[ShapeT],
    shape: ShapeT,
    analysis: GoalAnalysis[ShapeT],
) -> ShapeFacts[ShapeT]:
    solve = analysis.min_cost_result
    buildable = {
        ProofStatus.POSSIBLE: Decision.YES,
        ProofStatus.IMPOSSIBLE: Decision.NO,
        ProofStatus.UNKNOWN: Decision.UNKNOWN,
    }[solve.status]
    op_decisions = {
        operation: (
            Decision.YES
            if evidence.possible is True
            else Decision.NO
            if evidence.possible is False
            else Decision.UNKNOWN
        )
        for operation, evidence in analysis.operations.items()
    }
    strict_claw = Decision.UNKNOWN
    required = (Operation.PIN_PUSH, Operation.SWAP, Operation.STACK)
    if all(op_decisions[op] is not Decision.UNKNOWN for op in required):
        strict_claw = (
            Decision.YES
            if op_decisions[Operation.PIN_PUSH] is Decision.YES
            and op_decisions[Operation.SWAP] is Decision.NO
            and op_decisions[Operation.STACK] is Decision.NO
            else Decision.NO
        )

    minimum_proof = solve.proof
    operation_proofs = {
        operation: evidence.proof for operation, evidence in analysis.operations.items()
    }
    all_proofs = [proof for proof in operation_proofs.values() if proof is not None]
    traits = frozenset(
        trait for proof in all_proofs for trait in proof.traits
    )
    metadata: dict[str, Any] = {}
    if minimum_proof is not None:
        metadata.update(dict(minimum_proof.metadata))
    metadata["operation_metadata"] = {
        operation.value: dict(proof.metadata)
        for operation, proof in operation_proofs.items()
        if proof is not None
    }

    pp_proof = operation_proofs.get(Operation.PIN_PUSH)
    pp_rank = pp_proof.metadata.get("pp_rank") if pp_proof is not None else None
    if pp_rank is None and minimum_proof is not None:
        pp_rank = minimum_proof.metadata.get("pp_rank")
    if pp_rank is not None:
        pp_rank = int(pp_rank)

    stack_proof = operation_proofs.get(Operation.STACK)
    stack_depth = stack_proof.stack_depth if stack_proof is not None else (
        minimum_proof.stack_depth if minimum_proof is not None else None
    )

    return ShapeFacts(
        shape=shape,
        shape_key=backend.key(backend.canonicalize(shape)),
        empty=backend.is_empty(shape),
        has_crystal=backend.has_crystal(shape),
        active_columns=backend.active_columns(shape),
        buildable=buildable,
        analysis_complete=analysis.operation_analysis_complete,
        possible_last_operations=analysis.possible_last_operations,
        operation_decisions=op_decisions,
        minimum_proof=minimum_proof,
        strict_claw=strict_claw,
        is_corner=len(backend.active_columns(shape)) == 1,
        operation_proofs=operation_proofs,
        minimum_pp_rank=pp_rank,
        stack_depth=stack_depth,
        traits=traits,
        metadata=metadata,
    )
