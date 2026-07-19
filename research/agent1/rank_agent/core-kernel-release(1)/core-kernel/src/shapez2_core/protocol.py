"""Small stable integration surface shared with future solver branches."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .kernel import CutAxis, crystal_generator, cut, pin_push, rotate, stack, swap
from .model import CompactShape

SEMANTICS_NAME = "shapez2-quad-structural"
SEMANTICS_VERSION = "cpcp-shape.cpp@0bc7a30b + core-kernel/0.1.0"


class Operation(str, Enum):
    ROTATE = "rotate"
    CUT = "cut"
    STACK = "stack"
    SWAP = "swap"
    PIN_PUSH = "pin_push"
    CRYSTAL_GENERATOR = "crystal_generator"


@dataclass(frozen=True, slots=True)
class ForwardCall:
    operation: Operation
    parents: tuple[CompactShape, ...]
    parameters: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "parameters", MappingProxyType(dict(self.parameters))
        )


def replay(call: ForwardCall) -> tuple[CompactShape, ...]:
    op = call.operation
    parents = call.parents
    params = call.parameters
    if op is Operation.ROTATE:
        if len(parents) != 1:
            raise ValueError("rotate requires one parent")
        return (rotate(parents[0], int(params.get("turns", 1))),)
    if op is Operation.CUT:
        if len(parents) != 1:
            raise ValueError("cut requires one parent")
        return cut(parents[0], CutAxis(int(params.get("axis", 0))))
    if op is Operation.STACK:
        if len(parents) != 2:
            raise ValueError("stack requires two parents")
        return (stack(parents[0], parents[1]),)
    if op is Operation.SWAP:
        if len(parents) != 2:
            raise ValueError("swap requires two parents")
        return swap(parents[0], parents[1], CutAxis(int(params.get("axis", 0))))
    if op is Operation.PIN_PUSH:
        if len(parents) != 1:
            raise ValueError("pin_push requires one parent")
        return (pin_push(parents[0]),)
    if op is Operation.CRYSTAL_GENERATOR:
        if len(parents) != 1:
            raise ValueError("crystal_generator requires one parent")
        return (crystal_generator(parents[0]),)
    raise ValueError(op)
