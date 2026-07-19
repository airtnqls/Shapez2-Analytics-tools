from __future__ import annotations

import random

from corner_half.c7_gadget import C7Duty, DutyKind, compile_c7
from corner_half.structural_physics import CRYSTAL, EMPTY, NORMAL, PIN


def make_post(cap: int, duties: tuple[C7Duty, ...]) -> str:
    post = [EMPTY] * cap
    post[0] = EMPTY if duties[0].kind is DutyKind.FLOOR else PIN
    if post[0] == PIN:
        post[1] = NORMAL  # occupied pre-bottom types the P receipt
    for i, duty in enumerate(duties):
        f, t = duty.source, duty.target
        if duty.kind is DutyKind.FLOOR:
            # post[1] remains empty; sacrificial material begins above it.
            # A static cell at f+1 supports the harmless D cap.
            for layer in range(2, f):
                post[layer] = CRYSTAL
            if f + 1 < cap:
                post[f + 1] = CRYSTAL
        else:
            assert t >= 1 and post[t - 1] == EMPTY
            for layer in range(t, f):
                post[layer] = CRYSTAL
        post[f] = NORMAL
        if i + 1 < len(duties):
            post[f + 1] = CRYSTAL  # keeper
            post[f + 2] = NORMAL   # static holder / higher D anchor
    return "".join(post).rstrip(EMPTY)


def small_systematic() -> int:
    checked = 0
    for cap in range(4, 15):
        # One unit. P-receipt anchored duties need target >= 3 because layer 1
        # is occupied and layer target-1 must be empty.
        for source in range(2, cap):
            floor = C7Duty(source, 0, DutyKind.FLOOR)
            try:
                cert = compile_c7(make_post(cap, (floor,)), cap, (floor,))
            except ValueError:
                pass
            else:
                assert cert.replay_ok, cert
                checked += 1
            for target in range(3, source):
                duty = C7Duty(source, target, DutyKind.ANCHORED)
                cert = compile_c7(make_post(cap, (duty,)), cap, (duty,))
                assert cert.replay_ok, cert
                checked += 1

        # Two units with keeper, holder, and a gap before the upper target.
        for f1 in range(2, cap - 5):
            first_variants = [C7Duty(f1, 0, DutyKind.FLOOR)]
            first_variants += [
                C7Duty(f1, t1, DutyKind.ANCHORED)
                for t1 in range(3, f1)
            ]
            for first in first_variants:
                for t2 in range(f1 + 4, cap - 1):
                    for f2 in range(t2 + 1, cap):
                        duties = (first, C7Duty(f2, t2, DutyKind.ANCHORED))
                        cert = compile_c7(make_post(cap, duties), cap, duties)
                        assert cert.replay_ok, cert
                        checked += 1
    return checked


def high_random(count: int = 10_000, seed: int = 20260717) -> int:
    rng = random.Random(seed)
    checked = 0
    attempts = 0
    while checked < count and attempts < count * 100:
        attempts += 1
        cap = rng.randint(7, 128)
        max_units = min(10, max(1, (cap - 1) // 5))
        wanted = rng.randint(1, max_units)
        duties: list[C7Duty] = []
        lower_source = -1
        for i in range(wanted):
            remaining = wanted - i - 1
            if i == 0:
                min_target = 0
                min_source = 2
            else:
                min_target = lower_source + 4
                min_source = min_target + 1
            max_source = cap - 1 - remaining * 5
            if min_source > max_source:
                break
            floor_choice = i == 0 and rng.random() < 0.2
            if floor_choice:
                max_source = min(max_source, cap - 2)
            if min_source > max_source:
                break
            source = rng.randint(min_source, max_source)
            if floor_choice:
                target = 0
                kind = DutyKind.FLOOR
            else:
                target_min = 3 if i == 0 else min_target
                if target_min >= source:
                    break
                target = rng.randint(target_min, source - 1)
                kind = DutyKind.ANCHORED
            duties.append(C7Duty(source, target, kind))
            lower_source = source
        if not duties:
            continue
        duty_tuple = tuple(duties)
        try:
            cert = compile_c7(make_post(cap, duty_tuple), cap, duty_tuple)
        except ValueError:
            continue
        assert cert.replay_ok, cert
        checked += 1
    assert checked == count, (checked, attempts)
    return checked


def main() -> None:
    print({"small_systematic": small_systematic(), "high_random": high_random()})


if __name__ == "__main__":
    main()
