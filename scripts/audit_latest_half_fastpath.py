from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict

from backend.corner_half.corner_ir import compile_corner_ir
from backend.corner_half.corner_full_replay import replay_corner_full
from backend.corner_half.half_family import analyze_half
from backend.corner_half.proof_dag import half_raw_proof, verify_proof, verify_proof_forest

TARGET = (
    "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:"
    "SuSu----:--Su----:SuSu----:--Su----:cwSu----"
)
STRUCTURAL_TARGET = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--"
CAP = 11


def walk(root):
    seen = set()
    stack = [root]
    nodes = []
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        nodes.append(node)
        stack.extend(node.children)
    return nodes


def main() -> None:
    analysis = analyze_half(STRUCTURAL_TARGET, CAP)
    root = half_raw_proof(STRUCTURAL_TARGET, CAP)
    audit = verify_proof(root)
    nodes = walk(root)
    ops = Counter(node.operation for node in nodes)
    left_ir = compile_corner_ir(analysis.left_column, CAP)
    right_ir = compile_corner_ir(analysis.right_column, CAP)
    left_replay = replay_corner_full(analysis.left_column, CAP, True)
    right_replay = replay_corner_full(analysis.right_column, CAP, True)

    report = {
        "target": TARGET,
        "structuralTarget": STRUCTURAL_TARGET,
        "cap": CAP,
        "half": {
            "left": analysis.left_column,
            "right": analysis.right_column,
            "buildable": analysis.buildable,
        },
        "baseline": asdict(audit),
        "operationHistogram": dict(sorted(ops.items())),
        "leftIR": [
            {
                "rule": step.rule.value,
                "before": step.before,
                "after": step.after,
                "layer": step.layer,
                "helper": step.helper,
                "metadata": dict(step.metadata),
            }
            for step in left_ir.steps
        ],
        "rightIR": [
            {
                "rule": step.rule.value,
                "before": step.before,
                "after": step.after,
                "layer": step.layer,
                "helper": step.helper,
            }
            for step in right_ir.steps
        ],
        "fullReplay": {
            "leftOperations": len(left_replay.operations),
            "rightOperations": len(right_replay.operations),
            "leftHistogram": dict(Counter(step.operation for step in left_replay.operations)),
            "rightHistogram": dict(Counter(step.operation for step in right_replay.operations)),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
