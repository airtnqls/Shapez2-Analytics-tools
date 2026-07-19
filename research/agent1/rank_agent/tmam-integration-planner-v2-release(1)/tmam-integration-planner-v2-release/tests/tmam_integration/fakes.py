from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tmam import (
    Certificate,
    CostVector,
    Coverage,
    Goal,
    InverseBatch,
    InverseCandidate,
    Operation,
    Progress,
    Subgoal,
)


class StringBackend:
    def canonicalize(self, shape: str) -> str:
        return shape.strip()

    def key(self, shape: str) -> str:
        return shape.strip()

    def to_code(self, shape: str) -> str:
        return shape.strip()

    def equal(self, left: str, right: str) -> bool:
        return left.strip() == right.strip()

    def is_empty(self, shape: str) -> bool:
        return not shape.strip()

    def has_crystal(self, shape: str) -> bool:
        return "c" in shape

    def active_columns(self, shape: str) -> tuple[int, ...]:
        if shape.startswith("CORNER:"):
            return (0,)
        return () if not shape else (0, 1, 2, 3)

    def height(self, shape: str) -> int:
        return 0 if not shape else shape.count(":") + 1


class CertificateForwardModel:
    def replay(self, operation, parents, certificate):
        del operation, parents
        return str(certificate.payload["target"])


@dataclass
class TableRelation:
    provider_id: str
    operation: Operation
    table: dict[str, tuple[tuple[tuple[str, tuple[int, ...], str], ...], CostVector, frozenset[str], dict]]
    priority: int = 100
    complete: bool = True

    def inverse(self, goal: Goal[str]) -> InverseBatch[str]:
        rows = self.table.get(goal.shape, ())
        candidates = []
        for child_specs, cost, traits, metadata in rows:
            children = tuple(
                Subgoal(shape, Progress(progress), role)
                for shape, progress, role in child_specs
            )
            candidates.append(
                InverseCandidate(
                    operation=self.operation,
                    target=goal.shape,
                    children=children,
                    certificate=Certificate("test", {"target": goal.shape}),
                    local_cost=cost,
                    traits=traits,
                    metadata=metadata,
                )
            )
        coverage = (
            Coverage.complete_result(token=self.provider_id)
            if self.complete
            else Coverage.partial(reason="test provider intentionally partial", token=self.provider_id)
        )
        return InverseBatch(tuple(candidates), coverage)


def empty_relation(operation: Operation, provider_id: str | None = None) -> TableRelation:
    return TableRelation(provider_id or f"empty.{operation.value}", operation, {})


def standard_relations() -> tuple[TableRelation, ...]:
    input_relation = TableRelation(
        "input.basic",
        Operation.INPUT,
        {
            "A": (((), CostVector(operations=0, inputs=1), frozenset({"basic"}), {}),),
            "B": (((), CostVector(operations=0, inputs=1), frozenset({"basic"}), {}),),
        },
        priority=0,
    )
    stack_relation = TableRelation(
        "stack.rank",
        Operation.STACK,
        {
            "AB": (
                (
                    (("A", (1,), "bottom"), ("B", (1,), "top")),
                    CostVector(operations=1, buildings=1, stackers=1),
                    frozenset({"stack", "canonical_stack", "simple_hybrid"}),
                    {"pp_rank": 0},
                ),
            ),
        },
        priority=20,
    )
    pp_relation = TableRelation(
        "pinpush.rank",
        Operation.PIN_PUSH,
        {
            "PAB": (
                (
                    (("AB", (2,), "predecessor"),),
                    CostVector(operations=1, buildings=1, pin_pushes=1),
                    frozenset({"pp_essential"}),
                    {"pp_rank": 1},
                ),
            ),
        },
        priority=30,
    )
    provided = {Operation.INPUT, Operation.STACK, Operation.PIN_PUSH}
    return (
        input_relation,
        stack_relation,
        pp_relation,
        *(empty_relation(operation) for operation in Operation if operation not in provided),
    )
