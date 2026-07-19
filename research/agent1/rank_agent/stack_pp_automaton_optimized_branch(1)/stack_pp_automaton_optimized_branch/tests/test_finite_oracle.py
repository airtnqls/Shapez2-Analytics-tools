from __future__ import annotations

import json
import unittest
from pathlib import Path

from stack_pp.finite_oracle import FiniteStringDomain
from stack_pp.pp_rank import PPRankEngine


class FiniteOracleTests(unittest.TestCase):
    def test_json_oracle(self):
        here = Path(__file__).resolve()
        candidates = []
        for parent in here.parents:
            candidates.extend(
                (
                    parent / "examples" / "toy_oracle.json",
                    parent / "examples" / "stack_pp" / "toy_oracle.json",
                )
            )
        path = next((candidate for candidate in candidates if candidate.exists()), None)
        self.assertIsNotNone(path)
        domain = FiniteStringDomain.from_json_dict(json.loads(path.read_text()))
        result = PPRankEngine(domain).run()
        self.assertEqual(result.batches, (("A",), ("C",)))
        self.assertEqual(result.true_pp, ("C",))


if __name__ == "__main__":
    unittest.main()
