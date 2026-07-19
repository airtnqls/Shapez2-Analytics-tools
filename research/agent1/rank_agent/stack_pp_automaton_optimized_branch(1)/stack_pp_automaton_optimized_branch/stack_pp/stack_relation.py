from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Hashable, Iterator, TypeVar

from .model import FamilyWitness, RawStackCandidate, StackCertificate
from .protocols import RawStackInverseBackend, ShapeFamily, StackKernel

ShapeT = TypeVar("ShapeT", bound=Hashable)


class StackReplayError(AssertionError):
    """A backend emitted a candidate that fails exact forward replay."""


@dataclass
class FamilyConstrainedStackRelation(Generic[ShapeT]):
    """Exact Stack inverse intersected with two explicitly supplied families.

    This is the only safe way the TMAM planner may call a generic Stack inverse:

        Stack^{-1}(X) ∩ (BottomFamily × TopFamily)

    The unrestricted ``solve(A); solve(B)`` recursion rejected by the user is
    intentionally not exposed here.
    """

    backend: RawStackInverseBackend[ShapeT]
    kernel: StackKernel[ShapeT]
    verify_replay: bool = True

    def candidates(
        self,
        target: ShapeT,
        bottom_family: ShapeFamily[ShapeT],
        top_family: ShapeFamily[ShapeT],
        *,
        limit: int | None = None,
    ) -> Iterator[StackCertificate[ShapeT]]:
        if limit is not None and limit < 0:
            raise ValueError("limit must be nonnegative or None")
        if limit == 0:
            return

        emitted = 0
        seen: set[tuple[ShapeT, ShapeT]] = set()
        for raw in self.backend.candidates(target):
            bottom_witness = bottom_family.witness(raw.bottom)
            if bottom_witness is None:
                continue
            top_pieces = raw.top_pieces or (raw.top,)
            top_piece_witnesses = tuple(
                top_family.witness(piece) for piece in top_pieces
            )
            if any(witness is None for witness in top_piece_witnesses):
                continue
            typed_top_witnesses = tuple(
                witness for witness in top_piece_witnesses if witness is not None
            )
            if len(typed_top_witnesses) == 1 and top_pieces == (raw.top,):
                top_witness = typed_top_witnesses[0]
            else:
                top_witness = FamilyWitness(
                    top_family.name,
                    raw.top,
                    {"piece_witnesses": typed_top_witnesses},
                )

            pair = (
                self.kernel.canonical(raw.bottom),
                self.kernel.canonical(raw.top),
            )
            if pair in seen:
                continue
            seen.add(pair)

            if self.verify_replay:
                replay = self.kernel.stack(raw.bottom, raw.top)
                if self.kernel.canonical(replay) != self.kernel.canonical(target):
                    raise StackReplayError(
                        "raw Stack backend violated its contract: "
                        f"target={target!r}, replay={replay!r}, "
                        f"bottom={raw.bottom!r}, top={raw.top!r}"
                    )

            yield StackCertificate(
                target=target,
                bottom=raw.bottom,
                top=raw.top,
                bottom_family=bottom_family.name,
                top_family=top_family.name,
                bottom_witness=bottom_witness,
                top_witness=top_witness,
                backend_payload=raw.payload,
                top_pieces=top_pieces,
                top_piece_witnesses=typed_top_witnesses,
            )
            emitted += 1
            if limit is not None and emitted >= limit:
                return

    def first(
        self,
        target: ShapeT,
        bottom_family: ShapeFamily[ShapeT],
        top_family: ShapeFamily[ShapeT],
    ) -> StackCertificate[ShapeT] | None:
        return next(
            self.candidates(target, bottom_family, top_family, limit=1),
            None,
        )

    def exists(
        self,
        target: ShapeT,
        bottom_family: ShapeFamily[ShapeT],
        top_family: ShapeFamily[ShapeT],
    ) -> bool:
        return self.first(target, bottom_family, top_family) is not None
