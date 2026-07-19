from __future__ import annotations

from itertools import product
from collections import Counter

from corner_half.component_plans import event_zone_plan, _replay_event_zone
from corner_half.corner_regions import is_z_evt


def main() -> None:
    cases = Counter()
    checked = 0
    for n in range(0, 15):
        for chars in product('-SP', repeat=n):
            zone = ''.join(chars)
            # Valid zones have only a bottom P prefix; is_z_evt enforces body alphabet
            # but not P placement, so filter explicit prefix form.
            a = 0
            while a < len(zone) and zone[a] == 'P':
                a += 1
            if 'P' in zone[a:] or not is_z_evt(zone):
                continue
            plan = event_zone_plan(zone)
            assert _replay_event_zone(plan) == zone, plan
            cases[plan.case] += 1
            checked += 1
    print({'checked': checked, 'cases': dict(cases)})


if __name__ == '__main__':
    main()
