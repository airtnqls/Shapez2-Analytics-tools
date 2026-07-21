from __future__ import annotations

import itertools
import json
import sys
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.c7_gadget import C7CompilationError, C7Duty, DutyKind, compile_c7
from backend.corner_half.corner_event_plan import compile_corner_event
from backend.corner_half.structural_physics import column, parse, push_pin

TARGET = "SS-S-cS-S-c"
CAP = len(TARGET)


def ordered_mappings(sources: list[int], targets: list[int]):
    """Order-preserving source-to-target injections with no upward moves."""
    if len(sources) < len(targets):
        return
    for chosen in itertools.combinations(sources, len(targets)):
        if all(target <= source for source, target in zip(chosen, targets)):
            yield tuple(zip(chosen, targets))


def duty_kind_options(source: int, target: int):
    if source == target:
        return (None,)
    if target == 0:
        return (DutyKind.FLOOR,)
    return (DutyKind.ANCHORED, DutyKind.NATURAL)


def main() -> None:
    event = compile_corner_event(TARGET, CAP)
    post = event.c7.post_lift_a
    sources = [i for i, cell in enumerate(post) if cell == "S"]
    targets = [i for i, cell in enumerate(TARGET) if cell == "S"]
    failures: Counter[str] = Counter()
    examples: dict[str, str] = {}
    checked = 0
    hits: list[dict[str, object]] = []

    for mapping in ordered_mappings(sources, targets):
        option_sets = [duty_kind_options(source, target) for source, target in mapping]
        for kinds in itertools.product(*option_sets):
            duties = tuple(
                C7Duty(source, target, kind)
                for (source, target), kind in zip(mapping, kinds)
                if kind is not None
            )
            checked += 1
            try:
                cert = compile_c7(post, CAP, duties)
            except C7CompilationError as exc:
                key = str(exc).split(":", 1)[0]
                failures[key] += 1
                examples.setdefault(key, str(exc))
                continue
            if cert.actual_a == TARGET and cert.replay_ok:
                replay = column(push_pin(parse(cert.predecessor, CAP), CAP), 0)
                hits.append({
                    "mapping": [list(pair) for pair in mapping],
                    "duties": [[d.source, d.target, d.kind.value] for d in duties],
                    "postLiftA": post,
                    "predecessor": cert.predecessor,
                    "predecessorColumns": list(cert.predecessor_columns),
                    "actualA": cert.actual_a,
                    "replayA": replay,
                    "anchors": list(cert.anchors),
                })

    report = {
        "schemaVersion": 1,
        "target": TARGET,
        "cap": CAP,
        "base": {
            "postLiftA": post,
            "baseDuties": [[d.source, d.target, d.kind.value] for d in event.duties],
            "baseActualA": event.c7.actual_a,
            "postMoves": [[m.kind.value, m.layer] for m in event.post_event_moves],
            "sources": sources,
            "targets": targets,
        },
        "checked": checked,
        "hits": hits,
        "failureCounts": dict(failures.most_common()),
        "failureExamples": examples,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        print(json.dumps({
            "schemaVersion": 1,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, indent=2))
        raise
