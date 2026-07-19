from shapez2_core import (
    CRYSTAL,
    EMPTY,
    NORMAL,
    PIN,
    CompactShape,
    ShapeBuilder,
    canonical,
    canonical_with_transform,
    mirror,
    rotate,
)


def test_parse_structural_and_repository_roundtrip():
    structural = "SPc-:-S-P"
    shape = CompactShape.parse(structural, cap=5)
    assert shape.to_structural() == structural
    exact = shape.to_repository_code()
    assert CompactShape.parse(exact, cap=5) == shape


def test_empty_and_cap_are_explicit():
    empty = CompactShape.empty(12)
    assert empty.height == 0
    assert empty.to_structural() == "----"
    assert empty.cap == 12


def test_rotation_and_mirror_group_laws():
    shape = CompactShape.parse("SPc-:c-PS", cap=7)
    assert rotate(shape, 4) == shape
    assert rotate(rotate(shape, 2), 2) == shape
    assert mirror(mirror(shape)) == shape
    assert canonical(rotate(shape)) == canonical(shape)
    assert canonical(mirror(shape)) == canonical(shape)


def test_layer_bytes_and_canonical_witness():
    shape = CompactShape.parse("SPc-:c-PS", cap=9)
    payload = shape.to_layer_bytes()
    assert CompactShape.from_layer_bytes(payload, cap=9) == shape
    canonical_shape, turns, mirrored = canonical_with_transform(shape)
    transformed = rotate(shape, turns)
    if mirrored:
        transformed = mirror(transformed)
    assert transformed == canonical_shape == canonical(shape)


def test_mutable_builder_freezes_to_immutable_shape():
    builder = ShapeBuilder(20)
    builder.set_cell(0, 0, NORMAL)
    builder.set_cell(19, 3, CRYSTAL)
    frozen = builder.freeze()
    assert frozen.cell(0, 0) == NORMAL
    assert frozen.cell(19, 3) == CRYSTAL
    assert frozen.cap == 20
    copy = ShapeBuilder.from_shape(frozen)
    copy.set_cell(19, 3, EMPTY)
    assert copy.freeze() != frozen
