from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


_IMPOSSIBLE_RULES = tuple(
    (name, re.compile(pattern))
    for name, pattern in (
        ("pin after empty", r"-P"),
        ("crystal after leading empty gap", r"^P*-+c"),
        ("pin after non-pin before crystal", r"[^P]P.*c"),
        ("crystal gap starts empty", r"c-.*c"),
        ("crystal gap is supported then empty", r"cS-+c"),
        ("sparse S chain after crystal", r"^S*-?S*c(.*c)?(S-+)+c"),
    )
)


def matched_rule(shape: str) -> tuple[str, str] | None:
    """Return the first impossible rule matched by one pillar string."""
    shape = shape.strip()
    for name, pattern in _IMPOSSIBLE_RULES:
        if pattern.search(shape):
            return name, pattern.pattern
    return None


def is_true(shape: str) -> bool:
    """Return the corner-rule answer for one pillar string."""
    return matched_rule(shape) is None


def answer(shape: str) -> str:
    return "TRUE" if is_true(shape) else "FALSE"


def print_answer(shape: str, debug: bool = False) -> None:
    shape = shape.strip()
    result = answer(shape)
    print(result)

    if not debug:
        return

    match = matched_rule(shape)
    print(f"input={shape}")
    if match is None:
        print("matched_rule=None")
        print("reason=no impossible rule matched")
    else:
        name, pattern = match
        print(f"matched_rule={name}")
        print(f"pattern={pattern}")


def _load_truth(path: Path) -> list[tuple[str, bool]]:
    rows: list[tuple[str, bool]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue

        parts = line.split()
        if len(parts) != 2 or parts[1] not in {"TRUE", "FALSE"}:
            raise ValueError(f"invalid truth row at line {line_no}: {line!r}")

        rows.append((parts[0], parts[1] == "TRUE"))

    return rows


def validate(path: Path) -> int:
    rows = _load_truth(path)
    by_input: dict[str, set[bool]] = defaultdict(set)
    counts_by_input: dict[str, dict[bool, int]] = defaultdict(lambda: {False: 0, True: 0})
    for shape, expected in rows:
        by_input[shape].add(expected)
        counts_by_input[shape][expected] += 1

    conflicts = {shape: values for shape, values in by_input.items() if len(values) > 1}
    minimum_errors = sum(
        min(counts[False], counts[True])
        for shape, counts in counts_by_input.items()
        if shape in conflicts
    )
    errors = [
        (shape, expected, is_true(shape))
        for shape, expected in rows
        if is_true(shape) != expected
    ]
    avoidable_errors = len(errors) - minimum_errors

    print(f"rows={len(rows)} unique_inputs={len(by_input)}")
    print(
        f"errors={len(errors)} avoidable_errors={avoidable_errors} "
        f"minimum_possible_errors={minimum_errors} conflicts={len(conflicts)}"
    )

    if conflicts:
        print("conflicting inputs:")
        for shape in sorted(conflicts):
            print(f"  {shape}: FALSE and TRUE")

    if errors:
        print("mismatches:")
        for shape, expected, actual in errors[:50]:
            print(
                f"  {shape}: expected={'TRUE' if expected else 'FALSE'} "
                f"actual={'TRUE' if actual else 'FALSE'}"
            )
        if len(errors) > 50:
            print(f"  ... {len(errors) - 50} more")

    return 0 if avoidable_errors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    if not raw_args:
        truth_path = Path(__file__).with_name("true.txt")
        print(f"default_validate={truth_path}")
        return validate(truth_path)

    if len(raw_args) == 1 and raw_args[0] not in {"-h", "--help", "--validate", "--debug"}:
        print_answer(raw_args[0])
        return 0

    parser = argparse.ArgumentParser()
    parser.add_argument("shape", nargs="?", help="input pillar string")
    parser.add_argument("--debug", action="store_true", help="print rule matching logs")
    parser.add_argument(
        "--validate",
        nargs="?",
        const="true.txt",
        metavar="PATH",
        help="validate against a truth file",
    )
    args = parser.parse_args(raw_args)

    if args.validate is not None:
        return validate(Path(args.validate))

    if args.shape is not None:
        print_answer(args.shape, args.debug)
        return 0

    for line in sys.stdin:
        shape = line.strip()
        if shape:
            print_answer(shape, args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
