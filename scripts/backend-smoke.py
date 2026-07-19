from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.service import analyze, operate


def main() -> None:
    rotate = operate("rotate_cw", "SS--", cap=5)
    cut = operate("half_cutter", "SSSS", cap=5)
    assert rotate["outputs"] == ["-SS-"]
    assert cut["outputs"] == ["SS--", "--SS"]

    reports = []
    for code in ("SS-P", "cS-P", "-PPP:SS-P:---P:c--P:cS-S"):
        result = analyze(code, 5, "proof")
        graph = result["proof"]
        assert graph["primitiveComplete"] is True
        assert graph["replayStatus"] == "passed"
        assert not graph["omittedReasons"]
        assert not any(node.get("operation") == "CERTIFIED_MACRO" for node in graph["nodes"])
        replay_note = next(note for note in result["diagnostics"]["tablesLoaded"] if note.startswith("ZIP proof operation replay "))
        assert replay_note.startswith("ZIP proof operation replay ")
        reports.append({
            "code": code,
            "type": result["shapeType"],
            "nodes": len(graph["nodes"]),
            "operations": graph["uniqueOperationCount"],
            "validation": replay_note,
        })
    headroom_code = "--PP:--PP:--Pc:SSSS:-SS-:cS-S"
    headroom = analyze(headroom_code, 5, "proof")
    assert headroom["cap"] == 7
    assert headroom["verdict"] == "POSSIBLE"
    assert headroom["shapeType"] == "PIN_PUSH"
    assert headroom["route"] == "pp-receipt-chain"
    assert any("작업층 1개" in warning for warning in headroom["diagnostics"]["warnings"])
    assert headroom["proof"]["replayStatus"] == "passed"
    reports.append({
        "code": headroom_code,
        "requestedCap": 5,
        "effectiveCap": headroom["cap"],
        "type": headroom["shapeType"],
        "route": headroom["route"],
        "nodes": len(headroom["proof"]["nodes"]),
        "operations": headroom["proof"]["uniqueOperationCount"],
    })
    tall_half_code = "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----"
    tall_half = analyze(tall_half_code, 5, "proof")
    assert tall_half["cap"] == 11
    assert tall_half["verdict"] == "POSSIBLE"
    assert tall_half["shapeType"] == "HALF"
    assert tall_half["route"] == "half"
    assert tall_half["proof"]["primitiveComplete"] is True
    assert tall_half["proof"]["replayStatus"] == "passed"
    assert tall_half["proof"]["uniqueOperationCount"] < 324
    assert any("DAG optimization removed" in note for note in tall_half["diagnostics"]["tablesLoaded"])
    reports.append({
        "code": tall_half_code,
        "effectiveCap": tall_half["cap"],
        "type": tall_half["shapeType"],
        "route": tall_half["route"],
        "nodes": len(tall_half["proof"]["nodes"]),
        "operations": tall_half["proof"]["uniqueOperationCount"],
    })
    print({"status": "PASS", "operations": {"rotate": rotate["outputs"], "cut": cut["outputs"]}, "proofs": reports})


if __name__ == "__main__":
    main()
