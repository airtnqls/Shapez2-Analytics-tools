from __future__ import annotations

from typing import Callable, Hashable, Iterable, Protocol, TypeVar

from .rows import RowInfo

from .model import (
    FamilyWitness,
    PPEntry,
    PPSeed,
    RawStackCandidate,
    StackCertificate,
    StackClosureNode,
)

ShapeT = TypeVar("ShapeT", bound=Hashable)
FamilyStateT = TypeVar("FamilyStateT", bound=Hashable)


class ShapeFamily(Protocol[ShapeT]):
    """Membership interface supplied by Corner/Half/family branches."""

    name: str

    def contains(self, shape: ShapeT) -> bool:
        ...

    def witness(self, shape: ShapeT) -> FamilyWitness[ShapeT] | None:
        ...


class StackKernel(Protocol[ShapeT]):
    """Exact forward Stack semantics and canonical ordering helpers."""

    def stack(self, bottom: ShapeT, top: ShapeT) -> ShapeT:
        ...

    def canonical(self, shape: ShapeT) -> ShapeT:
        ...

    def order_key(self, shape: ShapeT) -> tuple:
        ...


class PinPushKernel(Protocol[ShapeT]):
    def pin_push(self, shape: ShapeT) -> ShapeT:
        ...

    def canonical(self, shape: ShapeT) -> ShapeT:
        ...

    def order_key(self, shape: ShapeT) -> tuple:
        ...


class RawStackInverseBackend(Protocol[ShapeT]):
    """Canonical visible Stack inverse, before family restrictions."""

    def candidates(self, target: ShapeT) -> Iterable[RawStackCandidate[ShapeT]]:
        ...


class PPRankDomain(Protocol[ShapeT]):
    """Dependency-injected domain used by :class:`PPRankEngine`.

    Implementations are provided after ``core-kernel`` and ``corner-half`` are
    merged.  This protocol prevents this branch from importing the classifier,
    GUI, or mutable legacy Shape objects into its proof logic.
    """

    def seeds_for_batch(
        self,
        batch: int,
        previous_batch: tuple[PPEntry[ShapeT], ...],
        retained: dict[ShapeT, PPEntry[ShapeT]],
    ) -> Iterable[PPSeed[ShapeT]]:
        ...

    def stack_closure(self, seed: PPSeed[ShapeT]) -> Iterable[StackClosureNode[ShapeT]]:
        ...

    def pin_push(self, predecessor: ShapeT) -> ShapeT:
        ...

    def canonical(self, shape: ShapeT) -> ShapeT:
        ...

    def is_empty(self, shape: ShapeT) -> bool:
        ...

    def is_swappable(self, shape: ShapeT) -> bool:
        """Rotation-invariant exact Swapper-family membership."""
        ...

    def stack_witness(
        self,
        target: ShapeT,
        allowed_base: Callable[[ShapeT], bool],
    ) -> StackCertificate[ShapeT] | None:
        """Return a complete transitive Stack decomposition to an allowed base.

        This must peel as many layer pieces as necessary.  Returning only one
        immediate Stack parent is insufficient during same-batch cleanup,
        because that intermediate parent may itself be removed as redundant.
        """
        ...

    def progress_key(self, shape: ShapeT) -> tuple:
        """Well-founded key for same-batch Stack cleanup.

        The production implementation must start with the number of visible
        non-crystal cells.  A nontrivial Stack decomposition strictly reduces
        that component when moving from target to bottom/base.
        """
        ...

    def order_key(self, shape: ShapeT) -> tuple:
        ...


class LayerFamilyAutomaton(Protocol[FamilyStateT]):
    """Bottom-to-top deterministic family recognizer used in Stack product.

    ``advance`` is called only for non-empty projected A rows.  Empty rows are
    observational trailing rows on every stable accepted A path and therefore
    leave the family state unchanged.
    """

    name: str

    def start_state(self) -> FamilyStateT:
        ...

    def advance(self, state: FamilyStateT, row_signature: tuple[int, int, int, int]) -> FamilyStateT | None:
        ...

    def accepts(self, state: FamilyStateT) -> bool:
        ...


class QuotientLayerFamilyAutomaton(LayerFamilyAutomaton[FamilyStateT], Protocol[FamilyStateT]):
    """Optional exact residual quotient/inclusion hooks for product pruning.

    ``canonical_state`` must identify states with identical future accepted
    row-suffix languages.  ``state_includes(left, right)`` means every suffix
    accepted from ``right`` is accepted from ``left``.  Implementations must be
    proved exact; omitting the hooks falls back to equality only.
    """

    def canonical_state(self, state: FamilyStateT) -> FamilyStateT:
        ...

    def state_includes(self, left: FamilyStateT, right: FamilyStateT) -> bool:
        ...


class TopPiecePolicy(Protocol):
    """Local policy for each non-empty visible Stack layer piece.

    cpcp-style Stack closure peels the stacked zone into a finite sequence of
    already-buildable one-layer pieces.  The policy is deliberately local: it
    sees one projected B row at a time and never triggers unrestricted
    recursion on an arbitrary bundled top shape.
    """

    name: str

    def accepts(self, row_signature: tuple[int, int, int, int]) -> bool:
        ...


class StackPathMaterializer(Protocol[ShapeT]):
    """Bridge from CompactShape to the representation-independent product DAG."""

    def rows(self, target: ShapeT) -> tuple[RowInfo, ...]:
        ...

    def materialize(
        self, target: ShapeT, ownership_path: tuple[int, ...]
    ) -> RawStackCandidate[ShapeT]:
        ...
