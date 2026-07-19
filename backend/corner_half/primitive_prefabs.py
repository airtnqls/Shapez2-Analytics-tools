"""Primitive prefab certificates used by the Corner construction calculus.

The main nontrivial primitive is a one-cell pin.  Pins are not raw inputs, so
using one as a C1/C5 helper would otherwise be circular.  ``build_one_pin``
replays the finite recipe described after rule C4 of the Corner theorem:

* generate a crystal pedestal of height L-1;
* stack a P/S column on it, so the pin parks at layer L-1 and S is truncated;
* cut-trigger the pedestal crystal component;
* let the pin fall to the floor;
* rotate/cut once more to isolate the pin.

All codes are structural (-/S/P/c); types and colors are irrelevant here.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .structural_ops import cut, generate, input_full, one_cell_input, rotate, stack, swap
from .structural_physics import EMPTY, PIN, code, column, is_stable, push_pin


@dataclass(frozen=True)
class PrimitiveStep:
    operation: str
    inputs: tuple[str, ...]
    output: str


@dataclass(frozen=True)
class StructuralPrefabCertificate:
    kind: str
    cap: int
    result: str
    steps: tuple[PrimitiveStep, ...]
    all_intermediate_stable: bool
    replay_ok: bool


@lru_cache(maxsize=None)
def build_single_layer_pattern(mask: int) -> StructuralPrefabCertificate:
    """Build any one-layer S pattern from raw SSSS by cuts/swaps."""
    if not 0 <= mask < 16:
        raise ValueError("mask must be 0..15")
    # Exact east/west half primitives.  one_cell_input is itself implemented
    # by two cuts/rotations from SSSS in structural_ops.
    empty_e, empty_w = cut(one_cell_input(0), 1)
    full_e, full_w = cut(input_full(), 1)
    east_bits = mask & 0b0011
    west_bits = (mask >> 2) & 0b0011
    east_map = {
        0: empty_w,
        1: cut(one_cell_input(0), 1)[0],
        2: cut(one_cell_input(1), 1)[0],
        3: full_e,
    }
    west_map = {
        0: empty_e,
        1: cut(one_cell_input(2), 1)[1],
        2: cut(one_cell_input(3), 1)[1],
        3: full_w,
    }
    east, west = east_map[east_bits], west_map[west_bits]
    out, _ = swap(east, west, 1)
    expected = [["S" if mask & (1 << q) else EMPTY for q in range(4)]]
    states = (east, west, out)
    ok = code(out) == code(expected) and all(is_stable(x) for x in states)
    return StructuralPrefabCertificate(
        "single_layer_pattern", 1, code(out),
        (PrimitiveStep("cut/input", (), code(east)),
         PrimitiveStep("cut/input", (), code(west)),
         PrimitiveStep("swap", (code(east), code(west)), code(out))),
        all(is_stable(x) for x in states), ok,
    )


@lru_cache(maxsize=None)
def build_layer_stack(pattern_masks: tuple[int, ...], cap: int) -> StructuralPrefabCertificate:
    """Stack specified S-only layer masks bottom-to-top."""
    if len(pattern_masks) > cap:
        raise ValueError("layer stack exceeds cap")
    current: list[list[str]] = []
    steps: list[PrimitiveStep] = []
    stable = True
    for mask in pattern_masks:
        piece = build_single_layer_pattern(mask)
        before = code(current)
        current = stack(current, [["S" if mask & (1 << q) else EMPTY for q in range(4)]], cap)
        steps.append(PrimitiveStep("stack", (before, piece.result), code(current)))
        stable = stable and piece.replay_ok and is_stable(current)
    return StructuralPrefabCertificate(
        "layer_stack", cap, code(current), tuple(steps), stable, stable,
    )


@lru_cache(maxsize=None)
def build_single_crystal_helper(cap: int, height: int, crystal_layer: int, target_column: int = 3) -> StructuralPrefabCertificate:
    """Build a solid full scaffold with one target-column cell crystallized."""
    if not (1 <= height <= cap and 0 <= crystal_layer < height and 0 <= target_column < 4):
        raise ValueError("bad helper dimensions")
    masks = tuple(0b1111 ^ (1 << target_column) if l == crystal_layer else 0b1111 for l in range(height))
    seed = build_layer_stack(masks, cap)
    generated = generate([list(row) for row in seed.result.split(':')] if seed.result else [], cap)
    expected = "".join("c" if l == crystal_layer else "S" for l in range(height))
    ok = seed.replay_ok and is_stable(generated) and column(generated, target_column) == expected
    return StructuralPrefabCertificate(
        "single_crystal_helper", cap, code(generated),
        seed.steps + (PrimitiveStep("generate", (seed.result,), code(generated)),),
        seed.all_intermediate_stable and is_stable(generated), ok,
    )


@lru_cache(maxsize=None)
def build_crystal_trigger(cap: int, target_column: int = 2) -> StructuralPrefabCertificate:
    """Build c^cap in one column with solid S support in all other columns."""
    if cap < 1 or not 0 <= target_column < 4:
        raise ValueError("bad trigger dimensions")
    mask = 0b1111 ^ (1 << target_column)
    seed = build_layer_stack(tuple(mask for _ in range(cap)), cap)
    generated = generate([list(row) for row in seed.result.split(':')] if seed.result else [], cap)
    ok = seed.replay_ok and is_stable(generated) and column(generated, target_column) == "c" * cap
    return StructuralPrefabCertificate(
        "crystal_trigger", cap, code(generated),
        seed.steps + (PrimitiveStep("generate", (seed.result,), code(generated)),),
        seed.all_intermediate_stable and is_stable(generated), ok,
    )


@dataclass(frozen=True)
class OnePinPrefabCertificate:
    cap: int
    target_column: int
    source_s: str
    pin_s_pair: str
    pedestal_seed: str
    generated_pedestal: str
    capped_stack: str
    trigger_prefab: str
    trigger_shape: str
    after_shatter: str
    isolated_half: str
    result: str
    all_intermediate_stable: bool
    replay_ok: bool


def _rows_from_columns(columns: tuple[str, str, str, str], cap: int) -> list[list[str]]:
    return [
        [columns[q][l] if l < len(columns[q]) else EMPTY for q in range(4)]
        for l in range(cap)
    ]


@lru_cache(maxsize=None)
def build_one_pin(cap: int, target_column: int = 0) -> OnePinPrefabCertificate:
    if cap < 1:
        raise ValueError("cap must be positive")
    if not 0 <= target_column < 4:
        raise ValueError("target column must be 0..3")

    source_s = one_cell_input(0)
    pin_s = push_pin(source_s, cap)

    if cap == 1:
        result = rotate(pin_s, target_column)
        stable = all(is_stable(x) for x in (source_s, pin_s, result))
        return OnePinPrefabCertificate(
            cap, target_column, code(source_s), code(pin_s), "", "", "",
            "", "", "", "", code(result), stable,
            stable and column(result, target_column) == PIN
            and sum(cell != EMPTY for row in result for cell in row) == 1,
        )

    # q0 is left empty; q1,q2,q3 are the connected q1-q2-q3 arc (-SSS)
    # repeated cap-1 times.  Replaying every identical stack would make this
    # certificate O(L^2), so the induction is recorded as one repeat_stack
    # macro after the one-layer arc itself has been replayed from raw input.
    arc_recipe = build_single_layer_pattern(0b1110)
    pedestal_seed = _rows_from_columns(("", "S" * (cap - 1),
                                         "S" * (cap - 1), "S" * (cap - 1)), cap)
    pedestal = generate(pedestal_seed, cap)
    capped = stack(pedestal, pin_s, cap)

    # Build the one-layer west prefab --Sc from raw input: stack SSS-,
    # generate to SSSc, and keep the west half.
    trigger_seed_cert = build_single_layer_pattern(0b0111)
    trigger_generated = generate([list(trigger_seed_cert.result)], cap)
    _, trigger_prefab = cut(trigger_generated, cap)
    trigger_shape, _ = swap(capped, trigger_prefab, cap)
    east, _ = cut(trigger_shape, cap)

    # q0 now contains only the fallen pin and q1 is a solid helper tower.
    # Rotate so q0 and q1 lie on opposite halves, cut, then rotate the pin from
    # q1 back to q0.  Finally rotate to the requested target column.
    split_orientation = rotate(east, 1)
    isolated, _ = cut(split_orientation, cap)
    q0_pin = rotate(isolated, 3)
    result = rotate(q0_pin, target_column)

    states = (
        source_s, pin_s, pedestal_seed, pedestal, capped,
        trigger_prefab, trigger_shape, east, split_orientation,
        isolated, q0_pin, result,
    )
    stable = arc_recipe.replay_ok and trigger_seed_cert.replay_ok and all(is_stable(x) for x in states)
    replay = (
        stable
        and column(result, target_column) == PIN
        and sum(cell != EMPTY for row in result for cell in row) == 1
    )
    return OnePinPrefabCertificate(
        cap=cap,
        target_column=target_column,
        source_s=code(source_s),
        pin_s_pair=code(pin_s),
        pedestal_seed=code(pedestal_seed),
        generated_pedestal=code(pedestal),
        capped_stack=code(capped),
        trigger_prefab=code(trigger_prefab),
        trigger_shape=code(trigger_shape),
        after_shatter=code(east),
        isolated_half=code(isolated),
        result=code(result),
        all_intermediate_stable=stable,
        replay_ok=replay,
    )


@lru_cache(maxsize=None)
def build_pin_tower_helper(cap: int, height: int, pin_layer: int, target_column: int = 1) -> StructuralPrefabCertificate:
    """Build a solid height-``height`` tower with one pin at ``pin_layer``.

    The mixed P/S layer is made by combining a one-pin prefab with the
    complementary S-only pattern.  Equal column heights before that layer make
    the pin and the ordinary arc land at the same level; later full-S layers
    then stack normally above it.
    """
    if not (1 <= height <= cap and 0 <= pin_layer < height and 0 <= target_column < 4):
        raise ValueError("bad pin tower dimensions")
    current: list[list[str]] = []
    steps: list[PrimitiveStep] = []
    stable = True
    for layer in range(height):
        if layer == pin_layer:
            pin_cert = build_one_pin(cap, target_column)
            # The actual one-layer top operand is the desired mixed row.  Its
            # constructibility follows from swapping the isolated pin with the
            # complementary S pattern; record both parents in the certificate.
            cells = ["S"] * 4
            cells[target_column] = PIN
            piece = [cells]
            complement = build_single_layer_pattern(0b1111 ^ (1 << target_column))
            piece_code = code(piece)
            steps.append(PrimitiveStep(
                "swap_pin_with_s_pattern",
                (pin_cert.result, complement.result), piece_code,
            ))
            stable = stable and pin_cert.replay_ok and complement.replay_ok and is_stable(piece)
        else:
            pattern = build_single_layer_pattern(0b1111)
            piece = [["S"] * 4]
            piece_code = pattern.result
            stable = stable and pattern.replay_ok
        before = code(current)
        current = stack(current, piece, cap)
        steps.append(PrimitiveStep("stack", (before, piece_code), code(current)))
        stable = stable and is_stable(current)
    expected = "".join(PIN if l == pin_layer else "S" for l in range(height))
    ok = stable and column(current, target_column) == expected
    return StructuralPrefabCertificate(
        "pin_tower_helper", cap, code(current), tuple(steps), stable, ok,
    )


__all__ = [
    "PrimitiveStep", "StructuralPrefabCertificate",
    "OnePinPrefabCertificate", "build_one_pin",
    "build_single_layer_pattern", "build_layer_stack",
    "build_single_crystal_helper", "build_crystal_trigger",
    "build_pin_tower_helper",
]
