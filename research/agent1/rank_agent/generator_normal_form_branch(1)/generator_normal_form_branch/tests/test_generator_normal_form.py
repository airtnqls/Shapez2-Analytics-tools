from __future__ import annotations

import itertools
import random
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator_normal_form import (
    CRYSTAL,
    EMPTY,
    NORMAL,
    PIN,
    CellKind,
    ExactCell,
    GeneratorConstraint,
    NoGeneratorPredecessor,
    NotGeneratorImage,
    canonical_raw_predecessor,
    count_with_deterministic_family,
    decode_row,
    encode_row,
    exact_to_structural,
    format_exact_code,
    format_structural,
    generator_forward_exact,
    generator_forward_project,
    generator_forward_structural,
    materialize_exact_predecessor,
    parse_exact_code,
    parse_structural,
    possible_productive_colors,
    set_cell,
    solve_exact_with_family,
    stable_single_pin_predecessor,
    solve_with_family,
    structural_crystal_count,
    trim_shape,
)


def all_structural_shapes(max_layers: int):
    for cells in itertools.product(range(4), repeat=4 * max_layers):
        rows = []
        for l in range(max_layers):
            row = 0
            for q in range(4):
                row = set_cell(row, q, cells[l * 4 + q])
            rows.append(row)
        yield trim_shape(rows)


class TrieFamily:
    """Deterministic layer DFA accepting an explicit finite shape set."""

    def __init__(self, accepted):
        self.accepted = frozenset(tuple(shape) for shape in accepted)
        prefixes = {()}
        for shape in self.accepted:
            for i in range(1, len(shape) + 1):
                prefixes.add(shape[:i])
        self.prefixes = frozenset(prefixes)

    def initial_state(self):
        return ()

    def transition(self, state, row):
        nxt = state + (row,)
        return nxt if nxt in self.prefixes else None

    def is_accepting(self, state):
        return state in self.accepted


class TestEncoding(unittest.TestCase):
    def test_roundtrip_rows(self):
        for chars in itertools.product("-SPc", repeat=4):
            text = "".join(chars)
            self.assertEqual(decode_row(encode_row(text)), text)

    def test_shape_roundtrip(self):
        code = "S-Pc:ccSS:----"
        self.assertEqual(format_structural(parse_structural(code)), "S-Pc:ccSS")


class FakeQuadrant:
    def __init__(self, shape, color):
        self.shape = shape
        self.color = color

    def copy(self):
        return FakeQuadrant(self.shape, self.color)


class FakeLayer:
    def __init__(self, quadrants):
        self.quadrants = quadrants

    def copy(self):
        return FakeLayer([q.copy() if q else None for q in self.quadrants])


class FakeShape:
    def __init__(self, layers):
        self.layers = layers
        self.max_layers = max(5, len(layers))

    def copy(self):
        out = FakeShape([layer.copy() for layer in self.layers])
        out.max_layers = self.max_layers
        return out


class TestProjectAdapter(unittest.TestCase):
    def fake_shape_module(self):
        return types.SimpleNamespace(Shape=FakeShape, Layer=FakeLayer, Quadrant=FakeQuadrant)

    def test_empty_shape_stays_empty(self):
        source = FakeShape([])
        with patch.dict(sys.modules, {"shape": self.fake_shape_module()}):
            out = generator_forward_project(source, "r")
        self.assertEqual(out.layers, [])
        self.assertEqual(out.max_layers, source.max_layers)

    def test_trailing_empty_internal_layers_are_not_filled(self):
        source = FakeShape([
            FakeLayer([FakeQuadrant("S", "u"), None, FakeQuadrant("P", "u"), FakeQuadrant("c", "b")]),
            FakeLayer([None, None, None, None]),
            FakeLayer([None, None, None, None]),
        ])
        source.max_layers = 9
        with patch.dict(sys.modules, {"shape": self.fake_shape_module()}):
            out = generator_forward_project(source, "r")
        self.assertEqual(len(out.layers), 1)
        row = out.layers[0].quadrants
        self.assertEqual((row[0].shape, row[0].color), ("S", "u"))
        self.assertEqual((row[1].shape, row[1].color), ("c", "r"))
        self.assertEqual((row[2].shape, row[2].color), ("c", "r"))
        self.assertEqual((row[3].shape, row[3].color), ("c", "b"))
        self.assertEqual(out.max_layers, 9)


class TestExactCode(unittest.TestCase):
    def test_roundtrip(self):
        code = "CuP-cr--:----Sg--"
        self.assertEqual(format_exact_code(parse_exact_code(code)), code)

    def test_reference_cases_from_cpcp(self):
        self.assertEqual(format_exact_code(generator_forward_exact(parse_exact_code(""), "r")), "")
        self.assertEqual(
            format_exact_code(generator_forward_exact(parse_exact_code("CuCu----"), "r")),
            "CuCucrcr",
        )
        self.assertEqual(
            format_exact_code(generator_forward_exact(parse_exact_code("P-P-P-P-"), "r")),
            "crcrcrcr",
        )
        self.assertEqual(
            format_exact_code(generator_forward_exact(parse_exact_code("cucuCuCu"), "r")),
            "cucuCuCu",
        )


class TestForwardSemantics(unittest.TestCase):
    def test_empty_stays_empty(self):
        self.assertEqual(generator_forward_structural(()), ())

    def test_fills_gaps_and_replaces_pins(self):
        source = parse_structural("S-Pc:P---")
        self.assertEqual(format_structural(generator_forward_structural(source)), "Sccc:cccc")

    def test_preserves_normals_and_crystals(self):
        source = parse_structural("ScSc")
        self.assertEqual(generator_forward_structural(source), source)

    def test_exact_color_semantics(self):
        e = ExactCell.empty()
        p = ExactCell.pin()
        red = ExactCell.crystal("r")
        blue = ExactCell.crystal("b")
        normal = ExactCell(CellKind.NORMAL, "S", "u")
        source = ((e, p, blue, normal),)
        expected = ((red, red, blue, normal),)
        self.assertEqual(generator_forward_exact(source, "r"), expected)


class TestImageAndNormalForm(unittest.TestCase):
    def test_rejects_gap_output(self):
        with self.assertRaises(NotGeneratorImage):
            GeneratorConstraint.structural(parse_structural("S-cc"))

    def test_rejects_pin_output(self):
        with self.assertRaises(NotGeneratorImage):
            GeneratorConstraint.structural(parse_structural("SPcc"))

    def test_rejects_productive_crystal_free_output(self):
        with self.assertRaises(NotGeneratorImage):
            GeneratorConstraint.structural(parse_structural("SSSS"), productive_only=True)

    def test_nonproductive_crystal_free_output_has_identity_only(self):
        target = parse_structural("SSSS")
        constraint = GeneratorConstraint.structural(target, productive_only=False)
        self.assertEqual(list(constraint.iter_raw_predecessors()), [target])
        self.assertEqual(constraint.unconstrained_count(), 1)

    def test_top_layer_height_is_preserved(self):
        target = parse_structural("cccc:cccc")
        constraint = GeneratorConstraint.structural(target)
        for predecessor in constraint.iter_raw_predecessors():
            self.assertEqual(len(predecessor), 2)
            self.assertNotEqual(decode_row(predecessor[-1]), "----")
            self.assertEqual(generator_forward_structural(predecessor), target)

    def test_canonical_raw_witness_is_productive_and_decreases_crystals(self):
        target = parse_structural("cccc:cccc")
        witness = canonical_raw_predecessor(GeneratorConstraint.structural(target))
        witness.certify()
        self.assertTrue(witness.productive)
        self.assertGreater(witness.crystal_drop, 0)
        self.assertEqual(structural_crystal_count(target), 8)
        # With no fixed top cells, the canonical raw witness keeps one top pin
        # to preserve the global height and generates every other crystal.
        self.assertEqual(witness.objective.retained_eligible_crystals, 0)
        self.assertEqual(witness.objective.pins, 1)

    def test_stable_single_pin_normal_form_is_full(self):
        target = parse_structural("cScS:cccc")
        constraint = GeneratorConstraint.structural(target)
        witness = stable_single_pin_predecessor(constraint)
        self.assertEqual(witness.crystal_drop, 1)
        self.assertEqual(witness.objective.pins, 1)
        for row in witness.predecessor:
            self.assertNotIn("-", decode_row(row))
        witness.certify()

    def test_unconstrained_count_closed_form(self):
        target = parse_structural("cccc:cccc")
        all_constraint = GeneratorConstraint.structural(target, productive_only=False)
        productive = GeneratorConstraint.structural(target, productive_only=True)
        # 3^8 choices, except the all-empty top row (3^4 lower choices).
        expected_all = 3**8 - 3**4
        self.assertEqual(all_constraint.unconstrained_count(), expected_all)
        self.assertEqual(productive.unconstrained_count(), expected_all - 1)


class TestExactColorConstraint(unittest.TestCase):
    def test_only_selected_color_is_eligible(self):
        normal = ExactCell(CellKind.NORMAL, "S", "u")
        red = ExactCell.crystal("r")
        blue = ExactCell.crystal("b")
        target = ((red, blue, normal, red),)
        constraint = GeneratorConstraint.exact(target, "r")
        self.assertEqual(constraint.eligible_crystal_masks, (0b1001,))
        self.assertEqual(constraint.fixed_crystal_masks, (0b0010,))
        for predecessor in constraint.iter_raw_predecessors():
            # Blue crystal must remain a crystal in every predecessor.
            self.assertEqual((predecessor[0] >> 2) & 0b11, CRYSTAL)

    def test_exact_materialization_and_replay(self):
        normal = ExactCell(CellKind.NORMAL, "R", "g")
        red = ExactCell.crystal("r")
        blue = ExactCell.crystal("b")
        target = ((red, blue, normal, red),)
        constraint = GeneratorConstraint.exact(target, "r")
        witness = canonical_raw_predecessor(constraint)
        predecessor = materialize_exact_predecessor(target, constraint, witness)
        self.assertEqual(generator_forward_exact(predecessor, "r"), target)
        # Fixed normal and non-selected crystal payloads survive exactly.
        self.assertEqual(predecessor[0][1], blue)
        self.assertEqual(predecessor[0][2], normal)

    def test_best_color_family_solution(self):
        normal = ExactCell(CellKind.NORMAL, "S", "u")
        red = ExactCell.crystal("r")
        blue = ExactCell.crystal("b")
        target = ((red, blue, normal, red),)
        # Accept all structural predecessors.  Red can generate two cells and
        # therefore wins the default objective over blue.
        from generator_normal_form import AcceptAllFamily
        solution = solve_exact_with_family(target, AcceptAllFamily())
        self.assertEqual(solution.generator_color, "r")
        solution.certify(target)

    def test_possible_productive_colors(self):
        target = ((
            ExactCell.crystal("b"),
            ExactCell.crystal("r"),
            ExactCell.crystal("b"),
            ExactCell(CellKind.NORMAL, "S", "u"),
        ),)
        self.assertEqual(possible_productive_colors(target), ("b", "r"))


class TestExhaustiveL2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forward_map = {}
        for predecessor in set(all_structural_shapes(2)):
            target = generator_forward_structural(predecessor)
            cls.forward_map.setdefault(target, set()).add(predecessor)

    def test_complete_inverse_relation(self):
        checked = 0
        for target, expected in self.forward_map.items():
            constraint = GeneratorConstraint.structural(target, productive_only=False)
            actual = set(constraint.iter_raw_predecessors())
            self.assertEqual(actual, expected, msg=f"target={format_structural(target)}")
            checked += 1
        self.assertEqual(checked, 273)  # empty + 2^4 + 2^8 full outputs

    def test_complete_productive_inverse_relation(self):
        for target, expected_all in self.forward_map.items():
            expected = {p for p in expected_all if p != target}
            if not expected:
                with self.assertRaises(NotGeneratorImage):
                    GeneratorConstraint.structural(target, productive_only=True)
                continue
            constraint = GeneratorConstraint.structural(target, productive_only=True)
            actual = set(constraint.iter_raw_predecessors())
            self.assertEqual(actual, expected, msg=f"target={format_structural(target)}")

    def test_family_intersection_against_bruteforce(self):
        rng = random.Random(20260717)
        targets = [target for target in self.forward_map if target and any(
            CRYSTAL in [((row >> (2 * q)) & 3) for q in range(4)] for row in target
        )]
        for _ in range(80):
            target = rng.choice(targets)
            constraint = GeneratorConstraint.structural(target, productive_only=True)
            universe = list(self.forward_map[target])
            accepted = {shape for shape in universe if rng.randrange(4) == 0}
            family = TrieFamily(accepted)
            expected = {shape for shape in accepted if constraint.accepts_predecessor(shape)}
            count = count_with_deterministic_family(constraint, family)
            self.assertEqual(count, len(expected))
            if expected:
                witness = solve_with_family(constraint, family)
                self.assertIn(witness.predecessor, expected)
                witness.certify()
            else:
                with self.assertRaises(NoGeneratorPredecessor):
                    solve_with_family(constraint, family)


if __name__ == "__main__":
    unittest.main(verbosity=2)
