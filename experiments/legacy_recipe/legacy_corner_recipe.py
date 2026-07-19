from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass, asdict


def _install_pyqt_stub() -> None:
    """shape.py only needs QThread/pyqtSignal types during import in this harness."""
    if "PyQt6.QtCore" in sys.modules:
        return
    pyqt6 = types.ModuleType("PyQt6")
    qtcore = types.ModuleType("PyQt6.QtCore")

    class QThread:
        pass

    def pyqtSignal(*_args, **_kwargs):
        return None

    qtcore.QThread = QThread
    qtcore.pyqtSignal = pyqtSignal
    pyqt6.QtCore = qtcore
    sys.modules["PyQt6"] = pyqt6
    sys.modules["PyQt6.QtCore"] = qtcore


_install_pyqt_stub()

from shape import Shape  # noqa: E402
from corner_tracer import build_pinable_shape  # noqa: E402

TARGET_CODE = (
    "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:"
    "SuSu----:--Su----:SuSu----:--Su----:cwSu----"
)
TARGET_LEFT_PILLAR = "SS-S-cS-S-c"


def structural(shape: Shape) -> str:
    rows: list[str] = []
    for layer in shape.layers:
        row = []
        for q in layer.quadrants:
            if q is None:
                row.append("-")
            elif q.shape == "P":
                row.append("P")
            elif q.shape == "c":
                row.append("c")
            else:
                row.append("S")
        rows.append("".join(row))
    while rows and rows[-1] == "----":
        rows.pop()
    return ":".join(rows)


def rotate(shape: Shape, turns: int) -> Shape:
    out = shape.copy()
    for _ in range(turns % 4):
        out = out.rotate(clockwise=True)
    return out


@dataclass(frozen=True)
class RecipeResult:
    cap: int
    pillar: str
    predecessor: str
    pin_result: str
    corner_target: str
    pin_replay_ok: bool
    swap_recipe: dict | None
    target: str
    final: str | None
    final_replay_ok: bool


def solve_recipe() -> RecipeResult:
    cap = len(TARGET_LEFT_PILLAR)
    Shape.MAX_LAYERS = cap

    predecessor_code = build_pinable_shape(TARGET_LEFT_PILLAR)
    predecessor = Shape.from_string(predecessor_code)
    predecessor.max_layers = cap
    pin_result = predecessor.push_pin()

    corner_target_code = ":".join(ch + "---" for ch in TARGET_LEFT_PILLAR)
    corner_target = Shape.from_string(corner_target_code)
    corner_target.max_layers = cap
    pin_ok = structural(pin_result) == structural(corner_target)

    spine = Shape.from_string(":".join("-S--" for _ in range(cap)))
    spine.max_layers = cap
    target = Shape.from_string(TARGET_CODE)
    target.max_layers = cap
    target_struct = structural(target)

    recipe = None
    final_struct = None
    if pin_ok:
        for corner_turns in range(4):
            for spine_turns in range(4):
                a = rotate(pin_result, corner_turns)
                b = rotate(spine, spine_turns)
                out_a, out_b = Shape.swap(a, b)
                for output_index, output in enumerate((out_a, out_b)):
                    for final_turns in range(4):
                        candidate = rotate(output, final_turns)
                        if structural(candidate) == target_struct:
                            recipe = {
                                "corner_turns": corner_turns,
                                "spine_turns": spine_turns,
                                "swap_output": output_index,
                                "final_turns": final_turns,
                                "operations": [
                                    "BUILD_PINABLE_CORNER_PREDECESSOR",
                                    "PIN_PUSH",
                                    "BUILD_SOLID_SPINE",
                                    f"ROTATE_CORNER_{corner_turns}",
                                    f"ROTATE_SPINE_{spine_turns}",
                                    "SWAP",
                                    f"SELECT_OUTPUT_{output_index}",
                                    f"ROTATE_FINAL_{final_turns}",
                                ],
                            }
                            final_struct = structural(candidate)
                            break
                    if recipe is not None:
                        break
                if recipe is not None:
                    break
            if recipe is not None:
                break

    return RecipeResult(
        cap=cap,
        pillar=TARGET_LEFT_PILLAR,
        predecessor=structural(predecessor),
        pin_result=structural(pin_result),
        corner_target=structural(corner_target),
        pin_replay_ok=pin_ok,
        swap_recipe=recipe,
        target=target_struct,
        final=final_struct,
        final_replay_ok=final_struct == target_struct,
    )


if __name__ == "__main__":
    print(json.dumps(asdict(solve_recipe()), ensure_ascii=False, indent=2))
