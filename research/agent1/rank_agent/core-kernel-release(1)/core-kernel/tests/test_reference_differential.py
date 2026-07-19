import itertools
import random

from shapez2_core import CompactShape
from shapez2_core import kernel as fast
from shapez2_core import reference as slow


def all_shapes(cap: int):
    for bits in range(1 << (8 * cap)):
        yield CompactShape(bits, cap)



def test_exhaustive_support_fixed_point_cap_1_and_2():
    for cap in (1, 2):
        for shape in all_shapes(cap):
            assert fast.support_positions(shape) == slow.support_positions(shape)


def test_horizontal_cut_is_rotated_vertical_cut():
    rng = random.Random(0xC077)
    for cap in range(1, 10):
        for _ in range(500):
            shape = fast.apply_gravity(
                CompactShape(rng.randrange(1 << (8 * cap)), cap)
            )
            rotated = fast.rotate(shape, 1)
            north_r, south_r = fast.cut(rotated, 0)
            expected = (fast.rotate(north_r, 3), fast.rotate(south_r, 3))
            assert fast.cut(shape, 1) == expected

def test_exhaustive_gravity_cap_1_and_2():
    for cap in (1, 2):
        for shape in all_shapes(cap):
            assert fast.apply_gravity(shape) == slow.apply_gravity(shape)


def test_unary_operations_dense_deterministic_sample():
    # The complete 65,536-state unary audit lives in scripts/validate_kernel.py.
    # Keeping a deterministic 8,192-state slice here makes ordinary pytest runs
    # fast even under tracing/coverage plugins.
    samples = list(range(4096)) + list(range((1 << 16) - 4096, 1 << 16))
    for bits in samples:
        shape = CompactShape(bits, 2)
        assert fast.rotate(shape, 1) == slow.rotate(shape, 1)
        assert fast.rotate(shape, 2) == slow.rotate(shape, 2)
        assert fast.mirror(shape) == slow.mirror(shape)
        assert fast.crystal_generator(shape) == slow.crystal_generator(shape)
        assert fast.pin_push(shape) == slow.pin_push(shape)
        assert fast.cut(shape, 0) == slow.cut(shape, 0)
        assert fast.cut(shape, 1) == slow.cut(shape, 1)


def test_random_binary_operations_differential():
    rng = random.Random(0xB1A2)
    for cap in range(1, 11):
        for _ in range(1000):
            a = fast.apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
            b = fast.apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
            assert fast.stack(a, b) == slow.stack(a, b)
            assert fast.swap(a, b, 0) == slow.swap(a, b, 0)
            assert fast.swap(a, b, 1) == slow.swap(a, b, 1)
