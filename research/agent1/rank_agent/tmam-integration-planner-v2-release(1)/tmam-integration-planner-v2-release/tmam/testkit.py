from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Generic, TypeVar

from .contracts import ForwardModel, Goal, InverseRelation, ShapeBackend

ShapeT = TypeVar("ShapeT")


@dataclass(frozen=True)
class ContractIssue:
    code: str
    message: str
    provider_id: str
    candidate_index: int | None = None


@dataclass(frozen=True)
class RelationAuditReport:
    provider_id: str
    candidate_count: int
    complete: bool
    issues: tuple[ContractIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def audit_relation(
    relation: InverseRelation[ShapeT],
    goal: Goal[ShapeT],
    *,
    backend: ShapeBackend[ShapeT],
    forward: ForwardModel[ShapeT],
    replay: bool = True,
) -> RelationAuditReport:
    """Reusable acceptance test for an upstream inverse provider."""

    issues: list[ContractIssue] = []
    batch = relation.inverse(goal)
    count = 0
    for index, candidate in enumerate(batch.candidates):
        count += 1
        if candidate.operation is not relation.operation:
            issues.append(
                ContractIssue(
                    "operation",
                    f"candidate operation {candidate.operation} differs from provider {relation.operation}",
                    relation.provider_id,
                    index,
                )
            )
        if not backend.equal(backend.canonicalize(candidate.target), backend.canonicalize(goal.shape)):
            issues.append(
                ContractIssue(
                    "target",
                    "candidate target differs from audited goal",
                    relation.provider_id,
                    index,
                )
            )
        for child in candidate.children:
            if not goal.progress.allows(child.progress):
                issues.append(
                    ContractIssue(
                        "progress",
                        f"child progress {child.progress.components} is not below {goal.progress.components}",
                        relation.provider_id,
                        index,
                    )
                )
        try:
            json.dumps(
                {
                    "certificate": {
                        "kind": candidate.certificate.kind,
                        "payload": dict(candidate.certificate.payload),
                    },
                    "metadata": dict(candidate.metadata),
                    "traits": sorted(candidate.traits),
                },
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            issues.append(
                ContractIssue(
                    "serialization",
                    f"certificate/metadata are not JSON-serializable: {exc}",
                    relation.provider_id,
                    index,
                )
            )
        if replay:
            try:
                output = forward.replay(
                    candidate.operation,
                    tuple(child.shape for child in candidate.children),
                    candidate.certificate,
                )
                if not backend.equal(output, goal.shape):
                    issues.append(
                        ContractIssue(
                            "replay",
                            "forward replay differs from target",
                            relation.provider_id,
                            index,
                        )
                    )
            except Exception as exc:  # pragma: no cover - integration boundary
                issues.append(
                    ContractIssue(
                        "replay_exception",
                        str(exc),
                        relation.provider_id,
                        index,
                    )
                )
    return RelationAuditReport(relation.provider_id, count, batch.coverage.complete, tuple(issues))
