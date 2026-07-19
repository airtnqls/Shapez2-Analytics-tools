from dataclasses import dataclass

from shapez2_core import CompactShape, from_legacy_shape, to_legacy_shape


@dataclass
class Q:
    shape: str
    color: str = "u"


@dataclass
class L:
    quadrants: list


class S:
    def __init__(self, layers):
        self.layers = layers
        self.max_layers = 9


class FakeModule:
    Quadrant = Q
    Layer = L
    Shape = S


def test_adapter_roundtrip_with_shape_like_protocol():
    legacy = S([L([Q("S"), Q("P"), Q("c"), None])])
    compact = from_legacy_shape(legacy)
    assert compact == CompactShape.parse("SPc-", cap=9)
    reconstructed = to_legacy_shape(compact, shape_module=FakeModule)
    assert from_legacy_shape(reconstructed, cap=9) == compact
