from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.corner_half.corner_full_replay import replay_corner_full
from backend.corner_half.corner_ir import compile_corner_ir
from backend.corner_half.proof_compactor import compact_proof
from backend.corner_half.proof_dag import corner_raw_proof, half_raw_proof, verify_proof

LEFT = "SS-S-cS-S-c"
RIGHT = "S" * 11
HALF = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--"
CAP = 11


def rle(values: list[str]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for value in values:
        if out and out[-1][0] == value:
            out[-1] = (value, out[-1][1] + 1)
        else:
            out.append((value, 1))
    return out


def main() -> None:
    ir = compile_corner_ir(LEFT, CAP)
    full = replay_corner_full(LEFT, CAP, False)
    left_proof = corner_raw_proof(LEFT, CAP)
    half_proof = half_raw_proof(HALF, CAP)
    compact_left = compact_proof(left_proof)
    compact_half = compact_proof(half_proof)
    left_audit = verify_proof(left_proof)
    half_audit = verify_proof(half_proof)
    compact_left_audit = verify_proof(compact_left)
    compact_half_audit = verify_proof(compact_half)
    report = {
        "schemaVersion": 3,
        "leftColumn": LEFT,
        "rightColumn": RIGHT,
        "half": HALF,
        "cornerKind": ir.kind.value,
        "cornerIrSteps": [
            {
                "index": index + 1,
                "rule": step.rule.value,
                "before": step.before,
                "after": step.after,
                "layer": step.layer,
                "helper": step.helper,
                "metadata": dict(step.metadata),
            }
            for index, step in enumerate(ir.steps)
        ],
        "fullReplayOperations": [
            {
                "index": index + 1,
                "operation": step.operation,
                "before": step.before,
                "operand": step.operand,
                "after": step.after,
                "targetBefore": step.target_before,
                "targetAfter": step.target_after,
            }
            for index, step in enumerate(full.operations)
        ],
        "fullReplayHistogram": dict(sorted(Counter(step.operation for step in full.operations).items())),
        "fullReplayRunLength": rle([step.operation for step in full.operations]),
        "leftProofAudit": left_audit.__dict__,
        "halfProofAudit": half_audit.__dict__,
        "compactLeftProofAudit": compact_left_audit.__dict__,
        "compactHalfProofAudit": compact_half_audit.__dict__,
    }
    reports = PROJECT_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    output = reports / "FASTPATH_CORNER_STRUCTURE.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "## Corner/Half 구조 감사",
        "",
        f"- Left column: `{LEFT}`",
        f"- Corner IR steps: **{len(ir.steps)}**",
        f"- Full replay top-level operations: **{len(full.operations)}**",
        f"- Left raw proof: **{left_audit.unique_nodes} nodes / {left_audit.operation_nodes} operations / depth {left_audit.max_depth}**",
        f"- Left compact proof: **{compact_left_audit.unique_nodes} nodes / {compact_left_audit.operation_nodes} operations / depth {compact_left_audit.max_depth}**",
        f"- Half raw proof: **{half_audit.unique_nodes} nodes / {half_audit.operation_nodes} operations / depth {half_audit.max_depth}**",
        f"- Half compact proof: **{compact_half_audit.unique_nodes} nodes / {compact_half_audit.operation_nodes} operations / depth {compact_half_audit.max_depth}**",
        "",
        "### IR transitions",
    ]
    lines.extend(
        f"- {index + 1}. `{step.rule.value}` layer={step.layer} · `{step.before or '<empty>'}` → `{step.after or '<empty>'}` · helper=`{step.helper}`"
        for index, step in enumerate(ir.steps)
    )
    lines.extend([
        "",
        "### Full replay operation RLE",
        "",
        "`" + " → ".join(f"{name}×{count}" if count > 1 else name for name, count in report["fullReplayRunLength"]) + "`",
        "",
    ])
    (reports / "FASTPATH_CORNER_STRUCTURE.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
