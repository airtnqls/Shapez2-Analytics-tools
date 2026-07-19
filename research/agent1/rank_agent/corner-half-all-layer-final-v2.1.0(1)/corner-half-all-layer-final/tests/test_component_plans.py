from __future__ import annotations

from itertools import product

from corner_half.component_plans import (
    event_segment_plan,
    natural_segment_plan,
    natural_zone_body_plan,
    replay_region,
)
from corner_half.corner_regions import is_i_nat, is_i_weak


def dead(v: str) -> bool:
    return bool(v) and v.startswith('-') and v.endswith('-') and 'SS' not in v


def main() -> None:
    totals = {'segment_natural': 0, 'segment_event': 0, 'zone_natural': 0}
    for n in range(0, 15):
        for chars in product('-S', repeat=n):
            s = ''.join(chars)
            if is_i_nat(s):
                p = natural_segment_plan(s)
                assert replay_region(p) == s, p
                totals['segment_natural'] += 1
            if is_i_weak(s):
                p = event_segment_plan(s)
                assert replay_region(p, include_event=p.event_source is not None) == s, p
                totals['segment_event'] += 1
            if not dead(s):
                p = natural_zone_body_plan(s)
                assert replay_region(p) == s, p
                totals['zone_natural'] += 1
    print(totals)


if __name__ == '__main__':
    main()
