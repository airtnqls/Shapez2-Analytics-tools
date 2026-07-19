from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stack_pp.finite_oracle import FiniteStringDomain
from stack_pp.pp_rank import PPRankEngine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the stack-pp rank engine on a fixed-cap exported oracle"
    )
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--max-batches", type=int, default=None)
    args = parser.parse_args()

    data = json.loads(args.oracle.read_text(encoding="utf-8"))
    domain = FiniteStringDomain.from_json_dict(data)
    result = PPRankEngine(domain).run(max_batches=args.max_batches)
    output = {
        "batches": [list(batch) for batch in result.batches],
        "entries": {
            shape: {
                "rank": entry.discovery_rank,
                "predecessor": entry.parent.predecessor,
                "seed": entry.parent.seed,
                "seed_rank": entry.parent.seed_rank,
            }
            for shape, entry in result.entries.items()
        },
        "same_batch_redundant": sorted(result.same_batch_redundant),
        "global_redundant": sorted(result.global_redundant),
        "true_pp": list(result.true_pp),
        "retained_for_parent_chain": list(result.retained_for_parent_chain),
        "termination_reason": result.termination_reason,
        "stats": dict(result.stats),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
