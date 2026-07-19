from __future__ import annotations

import unittest

from tmam import (
    ClassificationMode,
    ClassificationPolicy,
    Decision,
    LegacyShapeTypeKey,
    Operation,
    ShapeFacts,
)


class ClassificationTests(unittest.TestCase):
    def facts(self, **overrides):
        values = dict(
            shape="X",
            shape_key="X",
            empty=False,
            has_crystal=True,
            active_columns=(0, 1, 2, 3),
            buildable=Decision.YES,
            analysis_complete=True,
            possible_last_operations=frozenset(),
            operation_decisions={op: Decision.NO for op in Operation},
            minimum_proof=None,
            strict_claw=Decision.NO,
            is_corner=False,
            minimum_pp_rank=None,
            stack_depth=None,
            traits=frozenset(),
            metadata={},
        )
        values.update(overrides)
        return ShapeFacts(**values)

    def test_impossible(self):
        result = ClassificationPolicy().classify(
            self.facts(buildable=Decision.NO, analysis_complete=True)
        )
        self.assertEqual(result.primary, LegacyShapeTypeKey.IMPOSSIBLE)

    def test_incomplete_is_unknown(self):
        result = ClassificationPolicy().classify(
            self.facts(buildable=Decision.UNKNOWN, analysis_complete=False)
        )
        self.assertEqual(result.primary, LegacyShapeTypeKey.UNKNOWN)

    def test_strict_claw(self):
        result = ClassificationPolicy().classify(self.facts(strict_claw=Decision.YES))
        self.assertEqual(result.primary, LegacyShapeTypeKey.CLAW)

    def test_claw_hybrid(self):
        result = ClassificationPolicy().classify(
            self.facts(
                possible_last_operations=frozenset({Operation.STACK}),
                stack_depth=1,
                traits=frozenset({"claw_base_stack", "canonical_stack"}),
            )
        )
        self.assertEqual(result.primary, LegacyShapeTypeKey.CLAW_HYBRID)

    def test_complex_hybrid(self):
        result = ClassificationPolicy().classify(
            self.facts(
                possible_last_operations=frozenset({Operation.STACK}),
                stack_depth=3,
                traits=frozenset({"stack"}),
            )
        )
        self.assertEqual(result.primary, LegacyShapeTypeKey.COMPLEX_HYBRID)

    def test_corner_claw(self):
        result = ClassificationPolicy().classify(
            self.facts(
                active_columns=(0,),
                is_corner=True,
                strict_claw=Decision.YES,
            )
        )
        self.assertEqual(result.primary, LegacyShapeTypeKey.CLAW_CORNER)

    def test_legacy_crystal_free_precedence(self):
        result = ClassificationPolicy(ClassificationMode.LEGACY_COMPAT).classify(
            self.facts(
                has_crystal=False,
                possible_last_operations=frozenset({Operation.SWAP}),
            )
        )
        self.assertEqual(result.primary, LegacyShapeTypeKey.SIMPLE)


if __name__ == "__main__":
    unittest.main()
