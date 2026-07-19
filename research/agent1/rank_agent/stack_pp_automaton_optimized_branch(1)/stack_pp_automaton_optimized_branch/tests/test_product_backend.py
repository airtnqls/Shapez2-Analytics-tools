from __future__ import annotations

import unittest

from stack_pp import RowInfo
from stack_pp.model import RawStackCandidate
from stack_pp.stack_product import FamilyProductStackBackend


class AllFamily:
    name = "all"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        return state

    def accepts(self, state):
        return True


class Materializer:
    def rows(self, target):
        del target
        return (
            RowInfo.from_cells((1, 0, 0, 0)),
            RowInfo.from_cells((1, 1, 0, 0)),
        )

    def materialize(self, target, ownership_path):
        return RawStackCandidate(
            bottom=f"A:{ownership_path}",
            top=f"B:{ownership_path}",
            payload={"target": target},
            top_pieces=(f"p0:{ownership_path}", f"p1:{ownership_path}"),
        )


class ProductBackendTests(unittest.TestCase):
    def test_backend_materializes_only_product_paths(self):
        rows = list(FamilyProductStackBackend(AllFamily(), Materializer()).candidates("X"))
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("ownership_path", row.payload)
            self.assertEqual(row.payload["bottom_family"], "all")
            self.assertEqual(len(row.top_pieces), 2)


if __name__ == "__main__":
    unittest.main()
