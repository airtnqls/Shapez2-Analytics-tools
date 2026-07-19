from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Iterable

from ..model import RawStackCandidate


@dataclass
class ShapezStackFrontierBackend:
    """Adapter for the optimized all-layer ``claw_hybrid_frontier`` module.

    It deliberately requests the raw relation (``require_claw=False``).  Family
    membership is applied by :class:`FamilyConstrainedStackRelation`, not by the
    legacy classifier.

    This adapter is merge-ready now, but it is a *late-filtering baseline*.
    After ``corner-half`` exposes a layer automaton, the final backend should
    form the Stack-frontier × Half-family product so impossible bases are
    pruned during the layer scan rather than after materialization.
    """

    module_name: str = "claw_hybrid_frontier"
    verify_stack_in_backend: bool = False

    def candidates(self, target) -> Iterable[RawStackCandidate]:
        module = import_module(self.module_name)
        generator = module.claw_hybrid_candidates
        kwargs = {
            "require_claw": False,
            "verify_stack": self.verify_stack_in_backend,
        }
        # Optimized releases differ slightly in optional verification keyword
        # names.  Retry only for signature compatibility; semantic failures are
        # never swallowed.
        try:
            rows = generator(target, **kwargs)
        except TypeError:
            kwargs.pop("verify_stack")
            rows = generator(target, **kwargs)
        for candidate in rows:
            yield RawStackCandidate(
                bottom=candidate.bottom,
                top=candidate.top,
                payload={
                    "cuts": getattr(candidate, "cuts", None),
                    "switch_masks": getattr(candidate, "switch_masks", None),
                    "visible_top_pieces": getattr(candidate, "visible_top_pieces", None),
                    "scaffold_crystals": getattr(candidate, "scaffold_crystals", None),
                },
            )
