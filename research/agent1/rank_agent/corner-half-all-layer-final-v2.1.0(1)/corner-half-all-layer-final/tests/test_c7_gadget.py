from __future__ import annotations

from corner_half.c7_gadget import C7Duty, DutyKind, compile_c7


def run(name: str, post_a: str, duties: list[C7Duty], cap: int) -> None:
    cert = compile_c7(post_a, cap, duties)
    print({
        "name": name,
        "post_a": post_a,
        "duties": duties,
        "anchors": cert.anchors,
        "pre": cert.predecessor,
        "expected_a": cert.expected_a,
        "actual_a": cert.actual_a,
        "stable": cert.stable_predecessor,
        "replay": cert.replay_ok,
    })
    assert cert.replay_ok, cert


def main() -> None:
    # Post-lift A: P,S,-,c,c,c,S,c.  The run 3..5 dies and S 6 anchors at 3.
    run("single_anchored", "PS-cccSc", [C7Duty(6, 3)], 8)

    # Empty receipt, relay supports S at 6; it free-falls to layer 0.
    run("single_floor", "--ccccSc", [C7Duty(6, 0, DutyKind.FLOOR)], 8)

    # Two units separated by the static keeper at layer 5.
    run(
        "two_anchored",
        "PS-ccScS-ccSc",
        [C7Duty(5, 3), C7Duty(11, 9)],
        13,
    )


if __name__ == "__main__":
    main()
