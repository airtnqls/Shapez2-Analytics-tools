from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.proof_dag import (
    ProofDagError,
    shape_raw_proof,
    stack_proof,
    verify_proof,
)

CAP = 11
TARGET = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--"
PREFIX = "SS--"
BLOCK = "SS--:-S--:SS--:-S--:cS--"


def main() -> None:
    baseline = shape_raw_proof(TARGET, CAP)
    prefix = shape_raw_proof(PREFIX, CAP)
    block = shape_raw_proof(BLOCK, CAP)
    repeated = stack_proof(block, block)
    candidate = stack_proof(prefix, repeated)
    base_audit = verify_proof(baseline)
    block_audit = verify_proof(block)
    candidate_audit = verify_proof(candidate)
    if candidate.result != TARGET or not candidate_audit.replay_ok:
        raise ProofDagError((candidate.result, TARGET, candidate_audit))
    print(json.dumps({
        "schemaVersion": 1,
        "target": TARGET,
        "decomposition": {"prefix": PREFIX, "block": BLOCK, "repeats": 2},
        "baseline": asdict(base_audit),
        "block": asdict(block_audit),
        "periodic": asdict(candidate_audit),
        "removedOperations": base_audit.operation_nodes - candidate_audit.operation_nodes,
        "reductionRatio": 1 - candidate_audit.operation_nodes / base_audit.operation_nodes,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
