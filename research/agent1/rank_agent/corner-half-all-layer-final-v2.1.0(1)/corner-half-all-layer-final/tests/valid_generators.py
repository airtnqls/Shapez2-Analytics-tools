"""High-layer semantic generators; no exponentially rare rejection sampling."""
from __future__ import annotations

import random

from corner_half.corner_dfa import is_craftable_column
from corner_half.corner_regions import Route, analyze_column, is_i_nat, is_z_nat


def _top(rng: random.Random, n: int) -> str:
    out: list[str] = []
    for _ in range(n):
        choices = ['-', 'S', 'P']
        if out and out[-1] == '-':
            choices = ['-', 'S']
        out.append(rng.choice(choices))
    while out and out[-1] == '-':
        out.pop()
    return ''.join(out)


def _inat(rng: random.Random, n: int) -> str:
    if n <= 0:
        return ''
    if n == 1:
        return 'S'
    chars = [rng.choice('-S') for _ in range(n)]
    chars[0] = 'S'
    if rng.random() < 0.5:
        chars[-1] = 'S'
        if chars.count('S') < 2:
            chars[rng.randrange(1, n)] = 'S'
    else:
        i = rng.randrange(0, n - 1)
        chars[i] = chars[i + 1] = 'S'
        chars[0] = 'S'
    value = ''.join(chars)
    assert is_i_nat(value)
    return value


def _znat(rng: random.Random, max_len: int) -> str:
    pins = rng.randint(0, min(8, max_len))
    room = max_len - pins
    n = rng.randint(0, room)
    body = [rng.choice('-S') for _ in range(n)]
    value = 'P' * pins + ''.join(body)
    if not is_z_nat(value):
        # A dead body starts/ends with a gap and has no SS.  One endpoint S is
        # sufficient to move it into Z_nat without changing its length.
        if body:
            body[0] = 'S'
        value = 'P' * pins + ''.join(body)
    assert is_z_nat(value)
    return value


def make_natural_case(rng: random.Random, max_len: int = 200) -> str:
    if max_len < 1:
        return ''
    for _ in range(100):
        if rng.random() < 0.15:
            value = _top(rng, rng.randint(1, max_len))
            if value and is_craftable_column(value):
                return value

        zone_budget = max(0, max_len // 4)
        zone = _znat(rng, zone_budget)
        remaining = max_len - len(zone) - 1
        if remaining < 0:
            continue
        segment_count = rng.randint(0, min(20, remaining))
        segments: list[str] = []
        for _ in range(segment_count):
            if remaining <= 1:
                break
            n = rng.randint(0, min(12, remaining - 1))
            segments.append(_inat(rng, n))
            remaining -= n + 1
        top = _top(rng, rng.randint(0, min(30, max(0, remaining))))
        value = zone + 'c' + ''.join(seg + 'c' for seg in segments) + top
        if len(value) <= max_len and is_craftable_column(value):
            route = analyze_column(value).route
            if route in (Route.NATURAL, Route.CRYSTAL_FREE):
                return value
    raise RuntimeError('natural generator failed')
