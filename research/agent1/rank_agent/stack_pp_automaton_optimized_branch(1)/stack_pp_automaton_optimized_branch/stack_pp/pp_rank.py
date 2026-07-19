from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Hashable, Iterable, TypeVar

from .model import (
    PPEntry,
    PPRankResult,
    PinPushCertificate,
    StackCertificate,
)
from .protocols import PPRankDomain

ShapeT = TypeVar("ShapeT", bound=Hashable)


class RankInvariantError(AssertionError):
    """A domain adapter violated the well-founded PP-rank contract."""


class PinPushReplayError(AssertionError):
    """The domain's Pin Push/canonicalization contract is inconsistent."""


@dataclass(frozen=True)
class _ParentCandidate(Generic[ShapeT]):
    target: ShapeT
    predecessor: ShapeT
    seed: ShapeT
    seed_rank: int
    batch: int
    stack_trace: object | None


class PPRankEngine(Generic[ShapeT]):
    """cpcp-style PP batch engine over an injected exact symbolic domain.

    The engine itself never enumerates the global shape universe.  Its domain
    supplies symbolic/finite Stack closures for exactly the accepted seeds.

    Discovery ranks are immutable and every recorded PP parent uses a seed from
    a strictly lower rank.  This is the termination argument later consumed by
    the proof-tree branch.
    """

    def __init__(self, domain: PPRankDomain[ShapeT]):
        self.domain = domain

    def _parent_order_key(self, candidate: _ParentCandidate[ShapeT]) -> tuple:
        return (
            candidate.batch,
            candidate.seed_rank,
            self.domain.order_key(candidate.predecessor),
            self.domain.order_key(candidate.seed),
            repr(candidate.stack_trace),
        )

    def _lower_rank_allowed(
        self,
        retained: dict[ShapeT, PPEntry[ShapeT]],
        batch: int,
    ) -> Callable[[ShapeT], bool]:
        def allowed(base: ShapeT) -> bool:
            if self.domain.is_swappable(base):
                return True
            entry = retained.get(self.domain.canonical(base))
            return entry is not None and entry.discovery_rank < batch

        return allowed

    def run(self, *, max_batches: int | None = None) -> PPRankResult[ShapeT]:
        if max_batches is not None and max_batches < 0:
            raise ValueError("max_batches must be nonnegative or None")

        retained: dict[ShapeT, PPEntry[ShapeT]] = {}
        batches: list[tuple[ShapeT, ...]] = []
        same_batch_redundant: dict[ShapeT, StackCertificate[ShapeT]] = {}
        previous_batch: tuple[PPEntry[ShapeT], ...] = ()
        stats = {
            "seeds": 0,
            "closure_nodes": 0,
            "pinpush_results": 0,
            "empty_skips": 0,
            "swappable_skips": 0,
            "lower_rank_stackable_skips": 0,
            "duplicate_skips": 0,
            "same_batch_redundant": 0,
            "retained": 0,
        }

        batch = 0
        termination_reason = "fixed_point"
        while max_batches is None or batch < max_batches:
            raw: dict[ShapeT, _ParentCandidate[ShapeT]] = {}
            lower_allowed = self._lower_rank_allowed(retained, batch)

            seeds = tuple(
                self.domain.seeds_for_batch(batch, previous_batch, retained)
            )
            for seed in sorted(seeds, key=lambda item: self.domain.order_key(item.shape)):
                stats["seeds"] += 1
                if seed.source_rank >= batch:
                    raise RankInvariantError(
                        f"batch {batch} received seed rank {seed.source_rank}: {seed!r}"
                    )
                for node in self.domain.stack_closure(seed):
                    stats["closure_nodes"] += 1
                    target = self.domain.canonical(self.domain.pin_push(node.shape))
                    stats["pinpush_results"] += 1

                    if self.domain.is_empty(target):
                        stats["empty_skips"] += 1
                        continue
                    if self.domain.is_swappable(target):
                        stats["swappable_skips"] += 1
                        continue
                    if target in retained:
                        stats["duplicate_skips"] += 1
                        continue
                    if self.domain.stack_witness(target, lower_allowed) is not None:
                        stats["lower_rank_stackable_skips"] += 1
                        continue

                    candidate = _ParentCandidate(
                        target=target,
                        predecessor=node.shape,
                        seed=seed.shape,
                        seed_rank=seed.source_rank,
                        batch=batch,
                        stack_trace=node.trace,
                    )
                    old = raw.get(target)
                    if old is None or self._parent_order_key(candidate) < self._parent_order_key(old):
                        raw[target] = candidate

            if not raw:
                termination_reason = "fixed_point"
                break

            # Same-batch cleanup is processed in a well-founded order.  A
            # target may use an already accepted peer only if that peer has a
            # strictly smaller progress key; therefore no same-batch cycle can
            # enter a construction proof.
            accepted_this_batch: dict[ShapeT, PPEntry[ShapeT]] = {}
            ordered_targets = sorted(
                raw,
                key=lambda shape: (
                    self.domain.progress_key(shape),
                    self.domain.order_key(shape),
                ),
            )

            for target in ordered_targets:
                target_progress = self.domain.progress_key(target)

                def allowed_with_peers(base: ShapeT) -> bool:
                    canonical_base = self.domain.canonical(base)
                    if lower_allowed(canonical_base):
                        return True
                    peer = accepted_this_batch.get(canonical_base)
                    if peer is None:
                        return False
                    return self.domain.progress_key(canonical_base) < target_progress

                witness = self.domain.stack_witness(target, allowed_with_peers)
                if witness is not None:
                    same_batch_redundant[target] = witness
                    stats["same_batch_redundant"] += 1
                    continue

                parent = raw[target]
                if self.domain.canonical(self.domain.pin_push(parent.predecessor)) != target:
                    raise PinPushReplayError(
                        f"Pin Push replay failed for target {target!r}"
                    )
                certificate = PinPushCertificate(
                    target=target,
                    predecessor=parent.predecessor,
                    seed=parent.seed,
                    seed_rank=parent.seed_rank,
                    batch=batch,
                    stack_trace=parent.stack_trace,
                )
                accepted_this_batch[target] = PPEntry(
                    shape=target,
                    discovery_rank=batch,
                    parent=certificate,
                )

            if not accepted_this_batch:
                termination_reason = "batch_fully_stack_redundant"
                break

            batch_shapes = tuple(
                sorted(accepted_this_batch, key=self.domain.order_key)
            )
            batches.append(batch_shapes)
            retained.update(accepted_this_batch)
            stats["retained"] += len(accepted_this_batch)
            previous_batch = tuple(accepted_this_batch[s] for s in batch_shapes)
            batch += 1
        else:
            termination_reason = "max_batches"

        # Final semantic cleanup is descriptive only.  A later-rank shape may
        # render an earlier entry Stack-redundant while itself depending on that
        # earlier entry.  Such entries are kept for the acyclic parent chain,
        # matching cpcp's retained-vs-true-PP distinction.
        global_redundant: dict[ShapeT, StackCertificate[ShapeT]] = {}
        all_shapes = set(retained)
        for target in sorted(retained, key=self.domain.order_key):
            target_progress = self.domain.progress_key(target)

            def any_smaller_retained(base: ShapeT) -> bool:
                canonical_base = self.domain.canonical(base)
                if self.domain.is_swappable(canonical_base):
                    return True
                return (
                    canonical_base in all_shapes
                    and canonical_base != target
                    and self.domain.progress_key(canonical_base) < target_progress
                )

            witness = self.domain.stack_witness(target, any_smaller_retained)
            if witness is not None:
                global_redundant[target] = witness

        self._validate_result(retained, batches)
        return PPRankResult(
            entries=dict(retained),
            batches=tuple(batches),
            same_batch_redundant=dict(same_batch_redundant),
            global_redundant=global_redundant,
            termination_reason=termination_reason,
            stats=stats,
        )

    @staticmethod
    def _validate_result(
        retained: dict[ShapeT, PPEntry[ShapeT]],
        batches: list[tuple[ShapeT, ...]],
    ) -> None:
        seen: set[ShapeT] = set()
        for rank, shapes in enumerate(batches):
            for shape in shapes:
                if shape in seen:
                    raise RankInvariantError(f"duplicate PP entry {shape!r}")
                seen.add(shape)
                entry = retained[shape]
                if entry.discovery_rank != rank:
                    raise RankInvariantError(
                        f"entry {shape!r} has rank {entry.discovery_rank}, expected {rank}"
                    )
                if entry.parent.seed_rank >= rank:
                    raise RankInvariantError(
                        f"entry {shape!r} does not decrease rank: "
                        f"seed={entry.parent.seed_rank}, child={rank}"
                    )
        if seen != set(retained):
            raise RankInvariantError("batch index and retained map disagree")


def trace_pp_seed_chain(result: PPRankResult[ShapeT], target: ShapeT) -> tuple[PPEntry[ShapeT], ...]:
    """Follow retained PP seeds until a non-PP base is reached.

    Every step must strictly lower discovery rank; otherwise the stored result
    is corrupt.  Stack-closure details remain in each entry's opaque trace.
    """

    chain: list[PPEntry[ShapeT]] = []
    seen: set[ShapeT] = set()
    current = target
    while current in result.entries:
        if current in seen:
            raise RankInvariantError(f"cycle in PP seed chain at {current!r}")
        seen.add(current)
        entry = result.entries[current]
        chain.append(entry)
        seed = entry.parent.seed
        next_entry = result.entries.get(seed)
        if next_entry is None:
            break
        if next_entry.discovery_rank >= entry.discovery_rank:
            raise RankInvariantError(
                f"rank did not decrease: {current!r}({entry.discovery_rank}) -> "
                f"{seed!r}({next_entry.discovery_rank})"
            )
        current = seed
    return tuple(chain)
