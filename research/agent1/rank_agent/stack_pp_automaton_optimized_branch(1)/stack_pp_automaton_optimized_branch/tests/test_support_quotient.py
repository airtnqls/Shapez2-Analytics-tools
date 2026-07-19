from __future__ import annotations

import itertools
import random
import unittest

from stack_pp.row_table import ROW_INFO
from stack_pp.stack_product import (
    _GLOBAL_BEHAVIORS,
    _advance_behavior_id,
    _support_behavior_accepts,
)
from stack_pp.support_quotient import (
    SUPPORT_ACCEPTING,
    SUPPORT_INCLUDES,
    SUPPORT_START,
    SUPPORT_STATE_COUNT,
    SUPPORT_TRANSITIONS,
)


class SupportQuotientTests(unittest.TestCase):
    def test_inclusion_is_closed_under_every_row(self):
        for left in range(SUPPORT_STATE_COUNT):
            dominated = SUPPORT_INCLUDES[left]
            while dominated:
                bit = dominated & -dominated
                right = bit.bit_length() - 1
                dominated -= bit
                if SUPPORT_ACCEPTING[right]:
                    self.assertTrue(SUPPORT_ACCEPTING[left])
                for row_id in range(256):
                    left_next = SUPPORT_TRANSITIONS[left][row_id]
                    right_next = SUPPORT_TRANSITIONS[right][row_id]
                    self.assertTrue(
                        (SUPPORT_INCLUDES[left_next] >> right_next) & 1,
                        (left, right, row_id, left_next, right_next),
                    )

    def test_raw_behavior_and_quotient_agree_on_random_streams(self):
        rng = random.Random(0x5A770011)
        for layers in range(1, 25):
            for _ in range(250):
                row_ids = [rng.randrange(256) for _ in range(layers)]
                raw_behavior = 0
                raw_occupied = raw_crystal = 0
                quotient = None
                for layer, row_id in enumerate(row_ids):
                    row = ROW_INFO[row_id]
                    raw_behavior = _advance_behavior_id(
                        raw_behavior,
                        raw_occupied,
                        raw_crystal,
                        row.occupied,
                        row.crystal,
                        row.pin,
                        layer == 0,
                    )
                    raw_occupied = row.occupied
                    raw_crystal = row.crystal
                    quotient = (
                        SUPPORT_START[row_id]
                        if quotient is None
                        else SUPPORT_TRANSITIONS[quotient][row_id]
                    )
                raw_accepts = _support_behavior_accepts(
                    _GLOBAL_BEHAVIORS[raw_behavior], raw_occupied
                )
                self.assertEqual(raw_accepts, SUPPORT_ACCEPTING[quotient])

    def test_every_two_row_stream_matches_raw_support(self):
        for lower_id, upper_id in itertools.product(range(256), repeat=2):
            lower = ROW_INFO[lower_id]
            upper = ROW_INFO[upper_id]
            lower_behavior = _advance_behavior_id(
                0,
                0,
                0,
                lower.occupied,
                lower.crystal,
                lower.pin,
                True,
            )
            raw = _advance_behavior_id(
                lower_behavior,
                lower.occupied,
                lower.crystal,
                upper.occupied,
                upper.crystal,
                upper.pin,
                False,
            )
            raw_accepts = _support_behavior_accepts(
                _GLOBAL_BEHAVIORS[raw], upper.occupied
            )
            quotient = SUPPORT_TRANSITIONS[SUPPORT_START[lower_id]][upper_id]
            self.assertEqual(raw_accepts, SUPPORT_ACCEPTING[quotient])


if __name__ == "__main__":
    unittest.main()
