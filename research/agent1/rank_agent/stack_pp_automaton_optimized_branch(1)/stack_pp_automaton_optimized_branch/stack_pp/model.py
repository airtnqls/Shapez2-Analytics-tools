from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Hashable, Mapping, TypeVar

ShapeT = TypeVar("ShapeT", bound=Hashable)


@dataclass(frozen=True)
class FamilyWitness(Generic[ShapeT]):
    """Evidence that ``shape`` belongs to a symbolic family."""

    family: str
    shape: ShapeT
    payload: object | None = None


@dataclass(frozen=True)
class RawStackCandidate(Generic[ShapeT]):
    """Unfiltered exact/canonical Stack inverse emitted by a backend.

    ``top`` is the bundled executable Stack input used for forward replay.
    ``top_pieces`` is an optional proof decomposition into already-buildable
    layer/input pieces.  Keeping both prevents the TMAM branch from having to
    recursively solve an arbitrary bundled top shape again.
    """

    bottom: ShapeT
    top: ShapeT
    payload: object | None = None
    top_pieces: tuple[ShapeT, ...] = ()


@dataclass(frozen=True)
class StackCertificate(Generic[ShapeT]):
    """Executable certificate for one family-constrained Stack decomposition."""

    target: ShapeT
    bottom: ShapeT
    top: ShapeT
    bottom_family: str
    top_family: str
    bottom_witness: FamilyWitness[ShapeT]
    top_witness: FamilyWitness[ShapeT]
    backend_payload: object | None = None
    top_pieces: tuple[ShapeT, ...] = ()
    top_piece_witnesses: tuple[FamilyWitness[ShapeT], ...] = ()

    @property
    def pieces(self) -> tuple[ShapeT, ...]:
        """Layer-piece proof inputs; falls back to the canonical bundled top."""

        return self.top_pieces or (self.top,)


@dataclass(frozen=True)
class StackClosureNode(Generic[ShapeT]):
    """One predecessor in the Stack closure of a seed/base.

    ``trace`` is deliberately opaque to this branch.  The Stack backend owns
    its format and the TMAM integration branch later turns it into ProofNodes.
    """

    shape: ShapeT
    trace: object | None = None


@dataclass(frozen=True)
class PPSeed(Generic[ShapeT]):
    """A seed whose Stack closure may be Pin-Pushed in one PP batch."""

    shape: ShapeT
    source_rank: int
    source_kind: str
    proof: object | None = None


@dataclass(frozen=True)
class PinPushCertificate(Generic[ShapeT]):
    """Parent record kept for a PP discovery."""

    target: ShapeT
    predecessor: ShapeT
    seed: ShapeT
    seed_rank: int
    batch: int
    stack_trace: object | None = None


@dataclass(frozen=True)
class PPEntry(Generic[ShapeT]):
    """A retained PP parent entry.

    ``discovery_rank`` is immutable and is the rank used by build-plan
    recursion.  An entry may later become globally stack-redundant; it remains
    retained because later parent chains can still depend on it.
    """

    shape: ShapeT
    discovery_rank: int
    parent: PinPushCertificate[ShapeT]


@dataclass(frozen=True)
class PPRankResult(Generic[ShapeT]):
    """Complete output of the abstract cpcp-style batch engine."""

    entries: Mapping[ShapeT, PPEntry[ShapeT]]
    batches: tuple[tuple[ShapeT, ...], ...]
    same_batch_redundant: Mapping[ShapeT, StackCertificate[ShapeT]]
    global_redundant: Mapping[ShapeT, StackCertificate[ShapeT]]
    termination_reason: str
    stats: Mapping[str, int] = field(default_factory=dict)

    @property
    def true_pp(self) -> tuple[ShapeT, ...]:
        return tuple(
            shape for shape in self.entries if shape not in self.global_redundant
        )

    @property
    def retained_for_parent_chain(self) -> tuple[ShapeT, ...]:
        return tuple(
            shape for shape in self.entries if shape in self.global_redundant
        )

    @property
    def fixed_point_proved(self) -> bool:
        """Whether the batch loop ended by an exact closure argument.

        A user-imposed ``max_batches`` stop is intentionally not a proof of a
        fixed point and must never be interpreted as global UNSAT/completeness.
        """

        return self.termination_reason in {
            "fixed_point",
            "batch_fully_stack_redundant",
        }
