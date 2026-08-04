from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.service import analyze


EXPLICIT_TARGETS = (
    ("PPPP:-PSS:-P--:-ScS", 5),
    ("PPPP:cSSS:S-S-:SScS", 5),
    ("P-PP:S-PP:--Pc:-SSS:-P--:cS--", 6),
    ("SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----", 11),
    ("--PP:--PP:--Pc:SSSS:-SS-:cS-S", 5),
)


def proof_targets() -> list[tuple[str, int]]:
    samples_path = PROJECT_ROOT / "public/data/known_samples.json"
    samples = json.loads(samples_path.read_text(encoding="utf-8"))
    targets = {
        (str(code), int(entry.get("cap", 5)))
        for code, entry in samples.items()
        if entry.get("status") == "possible"
    }
    targets.update(EXPLICIT_TARGETS)
    return sorted(targets, key=lambda item: (item[1], item[0]))


def main() -> None:
    cache: dict[str, dict] = {}
    targets = proof_targets()
    for index, (code, cap) in enumerate(targets, start=1):
        result = analyze(code, cap, "proof")
        proof = result.get("proof")
        has_macro = bool(proof) and any(
            node.get("operation") == "CERTIFIED_MACRO"
            for node in proof.get("nodes", [])
        )
        if (
            result.get("verdict") != "POSSIBLE"
            or not proof
            or proof.get("replayStatus") != "passed"
            or not proof.get("primitiveComplete")
            or proof.get("omittedReasons")
            or has_macro
        ):
            raise RuntimeError(f"client proof cache validation failed: {code}")
        cache[f"{result['cap']}|{result['normalizedCode']}"] = proof
        if index % 20 == 0 or index == len(targets):
            print({"progress": f"{index}/{len(targets)}", "graphs": len(cache)})

    output = PROJECT_ROOT / "public/data/client_proof_cache.json.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(json.dumps(cache, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), compresslevel=9))
    print({"status": "PASS", "graphs": len(cache), "targets": len(targets), "bytes": output.stat().st_size})


if __name__ == "__main__":
    main()
