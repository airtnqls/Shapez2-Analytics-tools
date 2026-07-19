from __future__ import annotations

import itertools
import random
import unittest

from stack_pp.rows import CRYSTAL, EMPTY, NORMAL, PIN, ADJACENT, RowInfo, landing_row_is_valid
from stack_pp.stack_product import StackFamilyProductDAG


class AllFamily:
    name = "all"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        del row_signature
        return state

    def accepts(self, state):
        return state == 0


class NoPinFamily:
    name = "no-pin"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        occupied, crystal, pin, ordinary = row_signature
        del occupied, crystal, ordinary
        return None if pin else state

    def accepts(self, state):
        return state == 0


def stable(rows: tuple[RowInfo, ...]) -> bool:
    occupied = {(l, q) for l, row in enumerate(rows) for q in range(4) if row.occupied & (1 << q)}
    crystal = {(l, q) for l, row in enumerate(rows) for q in range(4) if row.crystal & (1 << q)}
    pin = {(l, q) for l, row in enumerate(rows) for q in range(4) if row.pin & (1 << q)}
    supported = {(0, q) for q in range(4) if (0, q) in occupied}
    while True:
        before = set(supported)
        for l, q in list(occupied):
            if l > 0 and (l - 1, q) in supported:
                supported.add((l, q))
            if (l, q) in pin:
                continue
            for nq in ADJACENT[q]:
                if (l, nq) in supported and (l, nq) not in pin:
                    supported.add((l, q))
            if (l, q) in crystal and (l + 1, q) in supported and (l + 1, q) in crystal:
                supported.add((l, q))
        if supported == before:
            break
    return supported == occupied


def brute_paths(rows: tuple[RowInfo, ...], *, no_pin=False):
    out = set()

    def visit(layer, switched, path):
        if layer == len(rows):
            if switched == 0:
                return
            a_rows = tuple(row.project(~mask & 15) for row, mask in zip(rows, path))
            if not any(row.occupied for row in a_rows):
                return
            if no_pin and any(row.pin for row in a_rows):
                return
            if stable(a_rows):
                out.add(tuple(path))
            return
        row = rows[layer]
        if switched & row.crystal:
            return
        startable = row.occupied & ~row.crystal & ~switched & 15
        subset = startable
        below = rows[layer - 1].occupied if layer else 0
        while True:
            next_mask = switched | subset
            b_mask = row.occupied & next_mask
            if landing_row_is_valid(
                is_floor=layer == 0,
                b_mask=b_mask,
                row=row,
                below_occupied=below,
            ):
                visit(layer + 1, next_mask, path + [next_mask])
            if subset == 0:
                break
            subset = (subset - 1) & startable

    visit(0, 0, [])
    return out


class StackProductTests(unittest.TestCase):
    def test_exhaustive_one_layer_all_family(self):
        for cells in itertools.product((EMPTY, NORMAL, PIN, CRYSTAL), repeat=4):
            rows = (RowInfo.from_cells(cells),)
            dag = StackFamilyProductDAG(rows, AllFamily())
            expected = brute_paths(rows)
            self.assertEqual(set(dag.iter_paths()), expected, cells)
            self.assertEqual(dag.path_count(), len(expected))
            self.assertEqual(dag.exists(), bool(expected))

    def test_random_two_and_three_layer_against_brute(self):
        rng = random.Random(20260717)
        for layers in (2, 3):
            for _ in range(500):
                rows = tuple(
                    RowInfo.from_cells(rng.choices((EMPTY, NORMAL, PIN, CRYSTAL), k=4))
                    for _ in range(layers)
                )
                expected = brute_paths(rows)
                actual = set(StackFamilyProductDAG(rows, AllFamily()).iter_paths())
                self.assertEqual(actual, expected)

    def test_family_product_prunes_A_pins(self):
        rng = random.Random(1707)
        for _ in range(500):
            rows = tuple(
                RowInfo.from_cells(rng.choices((EMPTY, NORMAL, PIN, CRYSTAL), k=4))
                for _ in range(3)
            )
            expected = brute_paths(rows, no_pin=True)
            dag = StackFamilyProductDAG(rows, NoPinFamily())
            self.assertEqual(set(dag.iter_paths()), expected)
            if expected:
                self.assertIn(dag.best_path(), expected)


if __name__ == "__main__":
    unittest.main()
