from __future__ import annotations

import sys
import types
import unittest
from dataclasses import dataclass

from stack_pp.adapters import ShapezStackFrontierBackend


@dataclass
class Candidate:
    bottom: str
    top: str
    cuts: tuple[int, int, int, int] = (0, 0, 0, 0)
    switch_masks: tuple[int, ...] = (1,)
    visible_top_pieces: int = 1
    scaffold_crystals: int = 0


class AdapterTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("_dummy_stack_frontier", None)
        sys.modules.pop("_dummy_stack_frontier_old_sig", None)

    def test_optimized_frontier_adapter(self):
        module = types.ModuleType("_dummy_stack_frontier")

        def candidates(target, *, require_claw, verify_stack):
            self.assertEqual(target, "X")
            self.assertFalse(require_claw)
            self.assertFalse(verify_stack)
            yield Candidate("A", "B")

        module.claw_hybrid_candidates = candidates
        sys.modules[module.__name__] = module
        backend = ShapezStackFrontierBackend(module.__name__)
        rows = list(backend.candidates("X"))
        self.assertEqual((rows[0].bottom, rows[0].top), ("A", "B"))
        self.assertEqual(rows[0].payload["cuts"], (0, 0, 0, 0))

    def test_signature_compatibility_fallback(self):
        module = types.ModuleType("_dummy_stack_frontier_old_sig")

        def candidates(target, *, require_claw):
            self.assertEqual(target, "X")
            self.assertFalse(require_claw)
            yield Candidate("A", "B")

        module.claw_hybrid_candidates = candidates
        sys.modules[module.__name__] = module
        backend = ShapezStackFrontierBackend(module.__name__)
        self.assertEqual(len(list(backend.candidates("X"))), 1)


if __name__ == "__main__":
    unittest.main()
