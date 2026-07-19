from __future__ import annotations

import unittest
from enum import Enum

from tmam import ClassificationResult, LegacyShapeTypeKey, ReasonCode, compare_legacy_result


class Legacy(Enum):
    SIMPLE = "simple translated"
    CLAW = "claw translated"


class ShadowTests(unittest.TestCase):
    def test_match(self):
        new = ClassificationResult(
            LegacyShapeTypeKey.CLAW,
            (ReasonCode.STRICT_CLAW,),
            frozenset(),
            True,
            {},
        )
        diff = compare_legacy_result(
            legacy_value=Legacy.CLAW.value,
            legacy_reason="old",
            legacy_enum=Legacy,
            new_result=new,
        )
        self.assertTrue(diff.matches)
        self.assertEqual(diff.legacy_name, "CLAW")


if __name__ == "__main__":
    unittest.main()
