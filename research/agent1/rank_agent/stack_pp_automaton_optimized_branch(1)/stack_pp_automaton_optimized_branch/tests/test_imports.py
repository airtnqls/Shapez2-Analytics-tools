from __future__ import annotations

import unittest


class ImportTests(unittest.TestCase):
    def test_public_import_surface(self):
        import stack_pp

        expected = {
            "FamilyConstrainedStackRelation",
            "PPRankEngine",
            "PredicateFamily",
            "StackCertificate",
        }
        self.assertTrue(expected.issubset(set(stack_pp.__all__)))


if __name__ == "__main__":
    unittest.main()
