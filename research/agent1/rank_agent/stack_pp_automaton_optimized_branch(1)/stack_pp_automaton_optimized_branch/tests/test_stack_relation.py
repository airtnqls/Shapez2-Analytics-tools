from __future__ import annotations

import unittest

from stack_pp import (
    FamilyConstrainedStackRelation,
    PredicateFamily,
    RawStackCandidate,
    StackReplayError,
    UnionFamily,
)


class Kernel:
    def stack(self, bottom: str, top: str) -> str:
        return bottom + "+" + top

    def canonical(self, shape: str) -> str:
        return shape.lower()

    def order_key(self, shape: str) -> tuple:
        return (shape,)


class Backend:
    def candidates(self, target: str):
        del target
        yield RawStackCandidate("A", "B", {"id": 1})
        yield RawStackCandidate("a", "b", {"id": 2})  # canonical duplicate
        yield RawStackCandidate("X", "Y", {"id": 3})


class StackRelationTests(unittest.TestCase):
    def test_family_intersection_and_deduplication(self):
        relation = FamilyConstrainedStackRelation(Backend(), Kernel())
        bottoms = PredicateFamily("bottom", lambda s: s.lower() == "a")
        tops = PredicateFamily("top", lambda s: s.lower() == "b")
        rows = list(relation.candidates("A+B", bottoms, tops))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].bottom, "A")
        self.assertEqual(rows[0].top, "B")
        self.assertEqual(rows[0].bottom_family, "bottom")

    def test_replay_failure_is_fatal(self):
        relation = FamilyConstrainedStackRelation(Backend(), Kernel())
        all_family = PredicateFamily("all", lambda _s: True)
        with self.assertRaises(StackReplayError):
            list(relation.candidates("wrong", all_family, all_family, limit=1))


    def test_union_family_preserves_member_witness(self):
        a = PredicateFamily("a", lambda s: s == "A")
        x = PredicateFamily("x", lambda s: s == "X")
        union = UnionFamily("a-or-x", (a, x))
        witness = union.witness("X")
        self.assertIsNotNone(witness)
        self.assertEqual(witness.payload["member_family"], "x")

    def test_zero_limit_does_not_touch_backend(self):
        class Exploding:
            def candidates(self, target):
                raise AssertionError(target)
                yield  # pragma: no cover

        relation = FamilyConstrainedStackRelation(Exploding(), Kernel())
        all_family = PredicateFamily("all", lambda _s: True)
        self.assertEqual(
            list(relation.candidates("T", all_family, all_family, limit=0)),
            [],
        )



    def test_top_piece_family_is_checked_piecewise(self):
        class PieceBackend:
            def candidates(self, target):
                self.target = target
                yield RawStackCandidate(
                    "A",
                    "BUNDLE",
                    {"kind": "layer-sequence"},
                    top_pieces=("p0", "p1"),
                )

        class PieceKernel(Kernel):
            def stack(self, bottom, top):
                self.seen = (bottom, top)
                return "X"

        backend = PieceBackend()
        kernel = PieceKernel()
        relation = FamilyConstrainedStackRelation(backend, kernel)
        bottom = PredicateFamily("bottom", lambda shape: shape == "A")
        pieces = PredicateFamily("pieces", lambda shape: shape in {"p0", "p1"})
        result = relation.first("X", bottom, pieces)
        self.assertIsNotNone(result)
        self.assertEqual(result.pieces, ("p0", "p1"))
        self.assertEqual(len(result.top_piece_witnesses), 2)

if __name__ == "__main__":
    unittest.main()
