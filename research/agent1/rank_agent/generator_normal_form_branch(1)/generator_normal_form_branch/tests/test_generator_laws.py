from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator_normal_form import (
    generator_forward_structural,
    row_occupied_mask,
    set_cell,
    trim_shape,
)


def rotate_row_cw(row: int) -> int:
    out = 0
    # q0 <- old q3, q1 <- old q0, q2 <- old q1, q3 <- old q2
    mapping = (3, 0, 1, 2)
    for q, old_q in enumerate(mapping):
        out = set_cell(out, q, (row >> (old_q * 2)) & 3)
    return out


def mirror_row(row: int) -> int:
    out = 0
    mapping = (0, 3, 2, 1)
    for q, old_q in enumerate(mapping):
        out = set_cell(out, q, (row >> (old_q * 2)) & 3)
    return out


def rotate_shape(shape):
    return trim_shape(tuple(rotate_row_cw(row) for row in shape))


def mirror_shape(shape):
    return trim_shape(tuple(mirror_row(row) for row in shape))


class TestGeneratorLaws(unittest.TestCase):
    def test_height_preservation_and_full_output_L2(self):
        for cells in itertools.product(range(4), repeat=8):
            rows = []
            for l in range(2):
                row = 0
                for q in range(4):
                    row = set_cell(row, q, cells[l * 4 + q])
                rows.append(row)
            shape = trim_shape(rows)
            out = generator_forward_structural(shape)
            self.assertEqual(len(out), len(shape))
            for row in out:
                self.assertEqual(row_occupied_mask(row), 0b1111)

    def test_structural_idempotence_L2(self):
        for cells in itertools.product(range(4), repeat=8):
            rows = []
            for l in range(2):
                row = 0
                for q in range(4):
                    row = set_cell(row, q, cells[l * 4 + q])
                rows.append(row)
            shape = trim_shape(rows)
            once = generator_forward_structural(shape)
            twice = generator_forward_structural(once)
            self.assertEqual(twice, once)

    def test_rotation_commutation_L2(self):
        for cells in itertools.product(range(4), repeat=8):
            rows = []
            for l in range(2):
                row = 0
                for q in range(4):
                    row = set_cell(row, q, cells[l * 4 + q])
                rows.append(row)
            shape = trim_shape(rows)
            self.assertEqual(
                rotate_shape(generator_forward_structural(shape)),
                generator_forward_structural(rotate_shape(shape)),
            )

    def test_mirror_commutation_L2(self):
        for cells in itertools.product(range(4), repeat=8):
            rows = []
            for l in range(2):
                row = 0
                for q in range(4):
                    row = set_cell(row, q, cells[l * 4 + q])
                rows.append(row)
            shape = trim_shape(rows)
            self.assertEqual(
                mirror_shape(generator_forward_structural(shape)),
                generator_forward_structural(mirror_shape(shape)),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
