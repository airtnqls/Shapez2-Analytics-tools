from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Generic, Iterable, Mapping, TypeVar

from .contracts import Certificate, ForwardModel, Progress, ShapeBackend
from .cost import CostVector
from .enums import Operation

ShapeT = TypeVar("ShapeT")


@dataclass(frozen=True)
class ProofNode(Generic[ShapeT]):
    shape: ShapeT
    shape_key: str
    shape_code: str
    progress: Progress
    operation: Operation
    children: tuple["ProofNode[ShapeT]", ...]
    certificate: Certificate
    local_cost: CostVector
    total_cost: CostVector
    traits: frozenset[str] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def stack_depth(self) -> int:
        child_depth = max((child.stack_depth for child in self.children), default=0)
        return child_depth + int(self.operation is Operation.STACK)

    @property
    def pin_push_depth(self) -> int:
        child_depth = max((child.pin_push_depth for child in self.children), default=0)
        return child_depth + int(self.operation is Operation.PIN_PUSH)

    def walk(self) -> Iterable["ProofNode[ShapeT]"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def stable_digest(self) -> str:
        payload = {
            "shape": self.shape_key,
            "progress": self.progress.components,
            "operation": self.operation.value,
            "children": [child.stable_digest() for child in self.children],
            "certificate": {
                "kind": self.certificate.kind,
                "payload": dict(self.certificate.payload),
            },
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape_key": self.shape_key,
            "shape_code": self.shape_code,
            "progress": list(self.progress.components),
            "operation": self.operation.value,
            "children": [child.to_dict() for child in self.children],
            "certificate": {
                "kind": self.certificate.kind,
                "payload": dict(self.certificate.payload),
            },
            "local_cost": asdict(self.local_cost),
            "total_cost": asdict(self.total_cost),
            "traits": sorted(self.traits),
            "metadata": dict(self.metadata),
            "digest": self.stable_digest(),
        }


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    shape_key: str


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...]
    node_count: int
    unique_shape_count: int


class ProofValidator(Generic[ShapeT]):
    def __init__(self, backend: ShapeBackend[ShapeT], forward: ForwardModel[ShapeT]):
        self.backend = backend
        self.forward = forward

    def validate(self, root: ProofNode[ShapeT]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        active: set[int] = set()
        visited: set[int] = set()
        shape_keys: set[str] = set()

        def visit(node: ProofNode[ShapeT]) -> None:
            identity = id(node)
            if identity in active:
                issues.append(ValidationIssue("cycle", "proof graph contains a cycle", node.shape_key))
                return
            if identity in visited:
                return
            visited.add(identity)
            active.add(identity)
            shape_keys.add(node.shape_key)

            if self.backend.key(self.backend.canonicalize(node.shape)) != node.shape_key:
                issues.append(ValidationIssue("shape_key", "stored shape key is not canonical", node.shape_key))

            for child in node.children:
                if not node.progress.allows(child.progress):
                    issues.append(
                        ValidationIssue(
                            "progress",
                            f"child progress {child.progress.components} is not below {node.progress.components}",
                            node.shape_key,
                        )
                    )
                visit(child)

            try:
                replayed = self.forward.replay(
                    node.operation,
                    tuple(child.shape for child in node.children),
                    node.certificate,
                )
                if not self.backend.equal(replayed, node.shape):
                    issues.append(ValidationIssue("replay", "forward replay does not equal target", node.shape_key))
            except Exception as exc:  # pragma: no cover - defensive integration boundary
                issues.append(ValidationIssue("replay_exception", str(exc), node.shape_key))

            active.remove(identity)

        visit(root)
        return ValidationReport(not issues, tuple(issues), len(visited), len(shape_keys))


def proof_to_legacy_tree(node: ProofNode[Any]) -> dict[str, Any]:
    """Convert an existing proof DAG to the legacy ``nodes/root_id`` schema.

    No classifier or inverse provider is invoked.  Stable proof digests are
    used as deterministic node IDs, and shared subproofs remain shared.
    Extra cost/trait/metadata fields are ignored by the old GUI but available
    to a newer renderer.
    """

    nodes: dict[str, dict[str, Any]] = {}
    digest_to_id: dict[str, str] = {}

    def visit(current: ProofNode[Any]) -> str:
        digest = current.stable_digest()
        existing = digest_to_id.get(digest)
        if existing is not None:
            return existing
        base = f"TMAM_{digest[:16]}"
        node_id = base
        suffix = 1
        while node_id in nodes:
            suffix += 1
            node_id = f"{base}_{suffix}"
        digest_to_id[digest] = node_id
        input_ids = [visit(child) for child in current.children]
        nodes[node_id] = {
            "shape_code": current.shape_code,
            "operation": current.operation.value,
            "input_ids": input_ids,
            "cost": asdict(current.total_cost),
            "traits": sorted(current.traits),
            "metadata": dict(current.metadata),
            "proof_digest": digest,
        }
        return node_id

    root_id = visit(node)
    return {"nodes": nodes, "root_id": root_id}
