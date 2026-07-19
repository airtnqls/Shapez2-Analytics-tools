import random

from shapez2_core import (
    CompactShape,
    CutAxis,
    apply_gravity,
    crystal_generator,
    cut,
    is_stable,
    pin_push,
    rotate,
    stack,
    stack_compact_equivalent,
    swap,
)


def random_shape(rng: random.Random, cap: int) -> CompactShape:
    bits = rng.randrange(1 << (8 * cap))
    return CompactShape(bits, cap)


def test_gravity_is_idempotent_random():
    rng = random.Random(0xC0DE)
    for cap in range(1, 13):
        for _ in range(300):
            once = apply_gravity(random_shape(rng, cap))
            assert apply_gravity(once) == once
            assert is_stable(once)


def test_forward_operations_produce_stable_shapes_on_stable_inputs():
    rng = random.Random(0x5151)
    for cap in range(1, 9):
        for _ in range(150):
            first = apply_gravity(random_shape(rng, cap))
            second = apply_gravity(random_shape(rng, cap))
            assert is_stable(pin_push(first))
            assert is_stable(crystal_generator(first))
            for axis in (CutAxis.VERTICAL, CutAxis.HORIZONTAL):
                assert all(is_stable(part) for part in cut(first, axis))
                assert all(is_stable(part) for part in swap(first, second, axis))
            assert is_stable(stack(first, second))


def test_compact_stack_optimization_matches_authoritative_stack_on_random_stable_inputs():
    rng = random.Random(0x57AC)
    for cap in range(1, 13):
        for _ in range(500):
            bottom = apply_gravity(random_shape(rng, cap))
            top = apply_gravity(random_shape(rng, cap))
            assert stack_compact_equivalent(bottom, top) == stack(bottom, top)
