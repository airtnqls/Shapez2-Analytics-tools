from __future__ import annotations


class LegacyShapeKernel:
    """Temporary adapter for the mutable project ``Shape`` class.

    The ``core-kernel`` branch should replace this in hot paths.  It remains
    useful as an independent executable oracle during differential testing.
    """

    def stack(self, bottom, top):
        from shape import Shape

        return Shape.stack(bottom, top)

    def canonical(self, shape):
        # Exact orientation is retained.  The future CompactShape adapter may
        # canonicalize rotations/mirrors for storage, but Stack replay must use
        # the original orientation.
        return repr(shape)

    def order_key(self, shape) -> tuple:
        return (repr(shape),)
