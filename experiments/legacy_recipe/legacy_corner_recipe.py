from __future__ import annotations

import contextlib
import io
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

# corner_tracer currently runs an unfinished debug example at import time. Keep
# the production experiment JSON clean while reusing the legacy constructor.
with contextlib.redirect_stdout(io.StringIO()):
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


def pillar(code: str, quadrant: int) -> str:
    result = []
    for row in code.split(":") if code else []:
        result.append(row[quadrant])
    return "".join(result)


def cell_distance(a: str, b: str) -> int:
    ar = a.split(":") if a else []
    br = b.split(":") if b else []
    n = max(len(ar), len(br))
    distance = 0
    for i in range(n):
        x = ar[i] if i < len(ar) else "----"
        y = br[i] if i < len(br) else "----"
        distance += sum(cx != cy for cx, cy in zip(x, y))
    return distance


@dataclass(frozen=True)
class RecipeResult:
    cap: int
    pillar: str
    predecessor: str
    pin_result: str
    pin_q0: str
    target_q0: str
    q0_matches_above_bottom: bool
    q0_bottom_transition: str
    corner_target: str
    pin_replay_ok: bool
    corner_cell_distance: int
    one_swap_recipe: dict | None
    target: str
    final: str | None
    final_replay_ok: bool


def solve_recipe() -> RecipeResult:
    cap = len(TARGET_LEFT_PILLAR)
    Shape.MAX_LAYERS = cap

    with contextlib.redirect_stdout(io.StringIO()):
        predecessor_code = build_pinable_shape(TARGET_LEFT_PILLAR)
    predecessor = Shape.from_string(predecessor_code)
    predecessor.max_layers = cap
    pin_result = predecessor.push_pin()

    corner_target_code = ":".join(ch + "---" for ch in TARGET_LEFT_PILLAR)
    corner_target = Shape.from_string(corner_target_code)
    corner_target.max_layers = cap
    pin_struct = structural(pin_result)
    corner_struct = structural(corner_target)
    pin_q0 = pillar(pin_struct, 0)
    target_q0 = TARGET_LEFT_PILLAR
    pin_ok = pin_struct == corner_struct

    spine = Shape.from_string(":".join("-S--" for _ in range(cap)))
    spine.max_layers = cap
    target = Shape.from_string(TARGET_CODE)
    target.max_layers = cap
    target_struct = structural(target)

    recipe = None
    final_struct = None
    # Test the most optimistic constant-width lowering: pushed legacy scaffold
    # plus one solid spine and one Swap. It is recorded as a diagnostic, not an
    # assumption. The broader restricted search lives in search_legacy_recipe.py.
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
        pin_result=pin_struct,
        pin_q0=pin_q0,
        target_q0=target_q0,
        q0_matches_above_bottom=pin_q0[1:] == target_q0[1:],
        q0_bottom_transition=f"{pin_q0[:1]}->{target_q0[:1]}",
        corner_target=corner_struct,
        pin_replay_ok=pin_ok,
        corner_cell_distance=cell_distance(pin_struct, corner_struct),
        one_swap_recipe=recipe,
        target=target_struct,
        final=final_struct,
        final_replay_ok=final_struct == target_struct,
    )


if __name__ == "__main__":
    print(json.dumps(asdict(solve_recipe()), ensure_ascii=False, indent=2))
