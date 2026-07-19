from __future__ import annotations

import unittest

from legacy_corner_recipe import solve_recipe


class LegacyCornerRecipeTests(unittest.TestCase):
    def test_legacy_pinable_constructor_matches_target_q0_above_bottom(self) -> None:
        result = solve_recipe()
        self.assertTrue(result.q0_matches_above_bottom, result)
        self.assertEqual(result.q0_bottom_transition, "P->S")

    def test_pin_push_alone_is_not_misreported_as_complete(self) -> None:
        result = solve_recipe()
        self.assertFalse(result.pin_replay_ok)
        self.assertGreater(result.corner_cell_distance, 0)

    def test_optional_one_swap_recipe_must_replay_if_found(self) -> None:
        result = solve_recipe()
        if result.one_swap_recipe is not None:
            self.assertTrue(result.final_replay_ok, result)
            self.assertEqual(result.final, result.target)


if __name__ == "__main__":
    unittest.main()
