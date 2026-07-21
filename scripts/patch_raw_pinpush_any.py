from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "lib/raw-pinpush-rank0.ts"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match, got {count}: {old[:100]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '  route?: "plain" | "cap-one" | "swappable-overflow" | "stack-overflow";\n',
        '  route?: "plain" | "cap-one" | "swappable-overflow" | "stack-overflow" | "general-overflow";\n',
    )
    text = replace_once(
        text,
        '      result.route = requireSwappable ? "swappable-overflow" : "stack-overflow";\n',
        '      result.route = requireSwappable ? "swappable-overflow" : (requireRank0Stack ? "stack-overflow" : "general-overflow");\n',
    )
    marker = '''export function uniquePlainPinPushPredecessor(targetRows: ShapeRows, cap: number): string | null {\n'''
    addition = '''export function solveAnyPinPush(targetRows: ShapeRows, cap: number, hooks: Rank0PinPushHooks = {}): Rank0PinPushResult {\n  const target = rowsFromShape(targetRows, cap);\n  const plain = solvePlainInverse(target);\n  if (plain) return { ok: true, predecessor: rowsCode(plain), transitions: 0, maxFailedStates: 0, bottomMask: occupiedMask(plain[0] ?? 0), axis: -2, route: "plain" };\n  if (cap === 1) {\n    const capOne = solveCapOne(target);\n    if (capOne) return { ok: true, predecessor: rowsCode(capOne), transitions: 0, maxFailedStates: 0, bottomMask: occupiedMask(capOne[0]), axis: -3, route: "cap-one" };\n    return { ok: false, transitions: 0, maxFailedStates: 0, bottomMask: 0, axis: -3 };\n  }\n  return solveOverflow(target, false, false, hooks);\n}\n\n'''
    text = replace_once(text, marker, addition + marker)
    PATH.write_text(text, encoding="utf-8")
    print("unrestricted Pin Push inverse export applied")


if __name__ == "__main__":
    main()
