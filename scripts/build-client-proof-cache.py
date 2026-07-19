from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.service import analyze


TARGETS = (
    ("SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----", 11),
    ("--PP:--PP:--Pc:SSSS:-SS-:cS-S", 5),
)


def main() -> None:
    cache: dict[str, dict] = {}
    for code, cap in TARGETS:
        result = analyze(code, cap, "proof")
        proof = result.get("proof")
        if result.get("verdict") != "POSSIBLE" or not proof or proof.get("replayStatus") != "passed":
            raise RuntimeError(f"client proof cache validation failed: {code}")
        cache[f"{result['cap']}|{result['normalizedCode']}"] = proof

    output = PROJECT_ROOT / "public/data/client_proof_cache.json.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(json.dumps(cache, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), compresslevel=9))
    print({"status": "PASS", "graphs": len(cache), "bytes": output.stat().st_size})


if __name__ == "__main__":
    main()
