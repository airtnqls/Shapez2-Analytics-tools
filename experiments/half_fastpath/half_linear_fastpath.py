from __future__ import annotations

from dataclasses import dataclass
from math import log
from time import perf_counter
from typing import Iterable, Sequence

Row = tuple[str, str, str, str]

# The straight-line operation labels visible in the supplied legacy trace.
# This module only uses them as proof-graph labels. The independently checked
# replay contract is the structural Half witness below;