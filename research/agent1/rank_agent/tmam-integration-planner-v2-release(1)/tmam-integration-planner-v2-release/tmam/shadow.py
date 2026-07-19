from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .classification import ClassificationResult


@dataclass(frozen=True)
class ShadowDiff:
    legacy_name: str | None
    new_name: str
    matches: bool
    legacy_reason: str
    new_reason_codes: tuple[str, ...]


def compare_legacy_result(
    *,
    legacy_value: Any,
    legacy_reason: str,
    legacy_enum,
    new_result: ClassificationResult,
) -> ShadowDiff:
    legacy_name = None
    for member in legacy_enum:
        if member.value == legacy_value:
            legacy_name = member.name
            break
    return ShadowDiff(
        legacy_name=legacy_name,
        new_name=new_result.primary.name,
        matches=legacy_name == new_result.primary.name,
        legacy_reason=legacy_reason,
        new_reason_codes=tuple(code.value for code in new_result.reason_codes),
    )
