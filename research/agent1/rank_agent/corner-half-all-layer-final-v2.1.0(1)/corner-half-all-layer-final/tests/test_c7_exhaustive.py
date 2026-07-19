from __future__ import annotations

import itertools
import random

from corner_half.c7_gadget import C7CompilationError, C7Duty, DutyKind, compile_c7

ALPHABET = "-SPc"


def exhaustive_single(cap: int = 6) -> dict[str, int]:
    attempted = accepted = failed = 0
    first_failure = None
    for tail in itertools.product(ALPHABET, repeat=cap - 1):
        # post[0] is forced by pre-bottom = post[1]
        receipt = "P" if tail and tail[0] != "-" else "-"
        post = receipt + "".join(tail)
        for source in range(1, cap):
            if post[source] != "S":
                continue
            for target in range(source):
                attempted += 1
                kind = DutyKind.FLOOR if target == 0 else DutyKind.ANCHORED
                try:
                    cert = compile_c7(post, cap, [C7Duty(source, target, kind)])
                except C7CompilationError:
                    continue
                accepted += 1
                if not cert.replay_ok:
                    failed += 1
                    if first_failure is None:
                        first_failure = cert
    assert failed == 0, first_failure
    return {"cap": cap, "attempted": attempted, "accepted": accepted, "failed": failed}


def random_multi(seed: int = 20260717, cases: int = 50_000) -> dict[str, int]:
    rng = random.Random(seed)
    accepted = failed = rejected = 0
    first_failure = None
    for _ in range(cases):
        cap = rng.randint(7, 40)
        post = ["-"] * cap
        duties: list[C7Duty] = []

        # Optional floor unit first.
        cursor = 1
        if rng.random() < 0.25:
            source = rng.randint(2, min(5, cap - 3))
            post[source] = "S"
            if source + 1 < cap:
                post[source + 1] = "c"
            # keep post[1] empty, so receipt is a gap
            for l in range(2, source):
                if rng.random() < 0.75:
                    post[l] = "c"
            duties.append(C7Duty(source, 0, DutyKind.FLOOR))
            cursor = source + 1
        else:
            # lowest anchored unit; may have P or gap receipt
            target = rng.randint(1, min(3, cap - 3))
            source = rng.randint(target + 1, min(target + 3, cap - 2))
            for l in range(target, source):
                post[l] = "c"
            post[source] = "S"
            duties.append(C7Duty(source, target))
            cursor = source + 1

        # Add separated upper units.  The static A anchor is explicit.
        desired = rng.randint(1, min(6, max(1, (cap - cursor) // 3 + 1)))
        while len(duties) < desired and cursor + 3 < cap:
            anchor = cursor
            post[anchor] = rng.choice(("S", "c", "P"))
            target = anchor + rng.randint(1, min(2, cap - anchor - 2))
            source = rng.randint(target + 1, min(target + 3, cap - 1))
            for l in range(target, source):
                post[l] = "c"
            post[source] = "S"
            duties.append(C7Duty(source, target))
            cursor = source + rng.randint(1, 2)

        # Add harmless static cells outside relay intervals.
        relay = set()
        for d in duties:
            relay.update(range(1, d.source + 1) if d.kind is DutyKind.FLOOR else range(d.target, d.source))
        source_set = {d.source for d in duties}
        for l in range(1, cap):
            if l in relay or l in source_set or post[l] != "-":
                continue
            if rng.random() < 0.15:
                post[l] = rng.choice(("S", "P"))

        post[0] = "P" if post[1] != "-" else "-"
        value = "".join(post).rstrip("-")
        try:
            cert = compile_c7(value, cap, duties)
        except C7CompilationError:
            rejected += 1
            continue
        accepted += 1
        if not cert.replay_ok:
            failed += 1
            if first_failure is None:
                first_failure = cert
                break
    assert failed == 0, first_failure
    return {"cases": cases, "accepted": accepted, "rejected": rejected, "failed": failed}


def main() -> None:
    print(exhaustive_single())
    print(random_multi())


if __name__ == "__main__":
    main()
