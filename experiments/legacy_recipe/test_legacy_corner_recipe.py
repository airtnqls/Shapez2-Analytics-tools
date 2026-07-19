from __future__ import annotations

import unittest

from legacy_corner_recipe import solve_recipe


class LegacyCornerRecipeTests(unittest.TestCase):
    def test_legacy_pinable_constructor_replays(self) -> None:
        result = solve_recipe()
        self.assertTrue(result.pin_replay_ok, result)

    def test_corner_plus_spine_swap_reaches_supplied_half(self) -> None:
        result = solve_recipe()
        self.assertIsNotNone(result.swap_recipe, result)
        self.assertTrue(result.final_replay_ok, result)
        self.assertEqual(result.final, result.target)

    def test_recipe_is_constant_width_linear_construction(self) -> None:
        result = solve_recipe()
        self.assertIsNotNone(result.swap_recipe)
        assert result.swap_recipe is not None
        # One direct Corner predecessor pass, one Pin Push, one spine, one Swap,
        # and constant rotations/output selection. No recursive target search.
        self.assertLessEqual(len(result.swap_recipe["operations"]), 8)


if __name__ == "__main__":
    unittest.main()
