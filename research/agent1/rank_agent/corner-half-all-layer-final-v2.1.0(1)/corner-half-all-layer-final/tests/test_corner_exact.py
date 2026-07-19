from __future__ import annotations

import itertools
import re

from corner_half.corner_dfa import (
    ALPHABET,
    FORBIDDEN_RULES,
    build_minimized_dfa,
    first_rejection,
    is_craftable_column,
)
from corner_half.corner_regions import analyze_column

REGEX = tuple((name, re.compile(pattern)) for name, pattern in FORBIDDEN_RULES)


def regex_answer(s: str) -> bool:
    return not any(p.search(s.rstrip("-")) for _, p in REGEX)


def main() -> None:
    dfa = build_minimized_dfa()
    assert dfa.state_count > 1
    total = 0
    for n in range(10):
        for chars in itertools.product(ALPHABET, repeat=n):
            s = "".join(chars).rstrip("-")
            expected = regex_answer(s)
            actual = is_craftable_column(s)
            assert actual == expected, (s, expected, actual, first_rejection(s))
            if actual:
                analyze_column(s)
            total += 1
    print({"checked": total, "dfa_states": dfa.state_count})


if __name__ == "__main__":
    main()
