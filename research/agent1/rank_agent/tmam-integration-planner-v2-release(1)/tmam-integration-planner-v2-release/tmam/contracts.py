from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Hashable, Iterable, Mapping, Protocol, TypeVar, runtime_checkable

from .cost import CostVector
from .enums import CoverageKind, Operation

ShapeT = TypeVar("ShapeT")
StateT = TypeVar("StateT", bound=Hashable)
SymbolT = TypeVar("SymbolT", bound=Hashable)


@dataclass(frozen=True, order=True)
class Progress:
    """A caller-defined well-founded measure.

    Every recursive child must have a lexicographically smaller tuple.  This is
    the integration layer's termination contract; PP rank, Stack depth, and a
    phase number can all be components.
    """

    components: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError("progress must contain at least one component")
        if any(value < 0 for value in self.components):
            raise ValueError("progress components must be nonnegative")

    def allows(self, child: "Progress") -> bool:
        return len(child.components) == len(self.components) and child.components < self.components


@dataclass(frozen=True)
class FamilyContext:
    """Hashable family/rank context carried through every recursive subgoal.

    Different PP ranks, allowed base families, color/shape abstraction modes,
    or operation policies must use different context keys so cached inverse
    results can never leak across semantic contexts.
    """

    context_id: str = "default"
    parameters: tuple[tuple[str, Hashable], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", tuple(sorted(self.parameters, key=lambda item: item[0])))

    @property
    def cache_key(self) -> tuple[str, tuple[tuple[str, Hashable], ...]]:
        return self.context_id, self.parameters


DEFAULT_FAMILY_CONTEXT = FamilyContext()


@dataclass(frozen=True)
class Goal(Generic[ShapeT]):
    shape: ShapeT
    progress: Progress
    family_context: FamilyContext = DEFAULT_FAMILY_CONTEXT


@dataclass(frozen=True)
class Subgoal(Generic[ShapeT]):
    shape: ShapeT
    progress: Progress
    role: str = "parent"
    family_context: FamilyContext | None = None


@dataclass(frozen=True)
class Coverage:
    kind: CoverageKind
    reason: str = ""
    token: str = ""

    @property
    def complete(self) -> bool:
        return self.kind is CoverageKind.COMPLETE

    @classmethod
    def complete_result(cls, *, reason: str = "", token: str = "") -> "Coverage":
        return cls(CoverageKind.COMPLETE, reason, token)

    @classmethod
    def partial(cls, *, reason: str, token: str = "") -> "Coverage":
        return cls(CoverageKind.PARTIAL, reason, token)


class ProviderIncompleteError(RuntimeError):
    """A provider could not exhaust its relation for a non-logical reason."""


class ProviderResourceLimit(ProviderIncompleteError):
    """Resource budget was reached; the result must remain UNKNOWN."""


@dataclass(frozen=True)
class Certificate:
    """Serializable evidence carried by one inverse candidate."""

    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InverseCandidate(Generic[ShapeT]):
    operation: Operation
    target: ShapeT
    children: tuple[Subgoal[ShapeT], ...]
    certificate: Certificate
    local_cost: CostVector = field(default_factory=CostVector)
    traits: frozenset[str] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InverseBatch(Generic[ShapeT]):
    candidates: Iterable[InverseCandidate[ShapeT]]
    coverage: Coverage
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class ShapeBackend(Protocol[ShapeT]):
    """The only representation-dependent dependency of tmam-integration."""

    def canonicalize(self, shape: ShapeT) -> ShapeT: ...

    def key(self, shape: ShapeT) -> str: ...

    def to_code(self, shape: ShapeT) -> str: ...

    def equal(self, left: ShapeT, right: ShapeT) -> bool: ...

    def is_empty(self, shape: ShapeT) -> bool: ...

    def has_crystal(self, shape: ShapeT) -> bool: ...

    def active_columns(self, shape: ShapeT) -> tuple[int, ...]: ...

    def height(self, shape: ShapeT) -> int: ...


@runtime_checkable
class ForwardModel(Protocol[ShapeT]):
    """Replays one proof node independently of its inverse implementation."""

    def replay(
        self,
        operation: Operation,
        parents: tuple[ShapeT, ...],
        certificate: Certificate,
    ) -> ShapeT: ...


@runtime_checkable
class InverseRelation(Protocol[ShapeT]):
    """One complete or explicitly partial inverse relation provider."""

    provider_id: str
    operation: Operation
    priority: int

    def inverse(self, goal: Goal[ShapeT]) -> InverseBatch[ShapeT]: ...


@runtime_checkable
class ShapeFamily(Protocol[ShapeT]):
    """Symbolic family membership with optional constructor evidence."""

    family_id: str

    def decide(self, goal: Goal[ShapeT]) -> "FamilyDecision[ShapeT]": ...


@dataclass(frozen=True)
class FamilyDecision(Generic[ShapeT]):
    member: bool | None
    coverage: Coverage
    certificate: Certificate | None = None
    local_cost: CostVector = field(default_factory=CostVector)
    traits: frozenset[str] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    version: str
    provides_relations: frozenset[str] = frozenset()
    provides_families: frozenset[str] = frozenset()
    requires_plugins: frozenset[str] = frozenset()
    notes: str = ""
