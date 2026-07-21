from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_VERSION = 2


def insert_once(text: str, marker: str, addition: str) -> str:
    if addition in text:
        return text
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"expected one marker, got {count}: {marker[:100]!r}")
    return text.replace(marker, addition + marker, 1)


def replace_once_if_needed(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one source block, got {count}: {old[:100]!r}")
    return text.replace(old, new, 1)


def patch_proof_dag() -> None:
    path = ROOT / "backend/corner_half/proof_dag.py"
    text = path.read_text(encoding="utf-8")

    raw_marker = '''def rotate_proof(child: ProofNode, steps_cw: int) -> ProofNode:\n'''
    full_tower = '''@lru_cache(maxsize=None)\ndef full_s_tower_proof(height: int, cap: int) -> ProofNode:\n    """Build a full SSSS tower with one shared raw input per level.\n\n    A raw structural input already is exactly one SSSS layer.  Reusing that\n    leaf and stacking it directly avoids rebuilding every layer from four\n    isolated cells while preserving a complete primitive replay DAG.\n    """\n    if not 1 <= height <= cap:\n        raise ProofDagError("full S tower height must be in 1..cap")\n    raw = raw_input_proof(cap)\n    current = raw\n    for _ in range(1, height):\n        current = stack_proof(current, raw)\n    expected = code([[ORDINARY] * 4 for _ in range(height)])\n    if current.result != expected:\n        raise ProofDagError(("full S tower proof", height, current.result, expected))\n    return current\n\n\n'''
    text = insert_once(text, raw_marker, full_tower)

    text = replace_once_if_needed(
        text,
        '''    if not 0 <= mask < 16:\n        raise ProofDagError("mask must be 0..15")\n    current = empty_shape_proof(cap)\n''',
        '''    if not 0 <= mask < 16:\n        raise ProofDagError("mask must be 0..15")\n    if mask == 0:\n        return empty_shape_proof(cap)\n    if mask == 0b1111:\n        return raw_input_proof(cap)\n    current = empty_shape_proof(cap)\n''',
    )

    text = replace_once_if_needed(
        text,
        '''    if not normalized:\n        return empty_shape_proof(cap)\n    layer_codes = normalized.split(":")\n    prefix = ":".join(layer_codes[:-1])\n''',
        '''    if not normalized:\n        return empty_shape_proof(cap)\n    layer_codes = normalized.split(":")\n    if all(layer == ORDINARY * 4 for layer in layer_codes):\n        return full_s_tower_proof(len(layer_codes), cap)\n    prefix = ":".join(layer_codes[:-1])\n''',
    )

    text = replace_once_if_needed(
        text,
        '''    _BUILDING_CORNER.add(key)\n    try:\n        replay = replay_corner_full(normalized, cap, False)\n''',
        '''    _BUILDING_CORNER.add(key)\n    try:\n        # Positive accelerator only: an exact legacy-style all-layer\n        # predecessor is assembled once, pushed once and independently replayed.\n        # Any mismatch falls back to the complete C1..C7 constructor below.\n        try:\n            from .global_proof_fastpath import try_global_corner_raw_proof\n            fast = try_global_corner_raw_proof(normalized, cap)\n        except Exception:\n            fast = None\n        if fast is not None:\n            _CORNER_CACHE[key] = fast\n            return fast\n\n        replay = replay_corner_full(normalized, cap, False)\n''',
    )

    text = replace_once_if_needed(
        text,
        '''        raw_input_proof, single_cell_proof, empty_shape_proof,\n''',
        '''        raw_input_proof, full_s_tower_proof, single_cell_proof, empty_shape_proof,\n''',
    )

    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_proof_dag()
    print(f"latest proof fast paths applied v{PATCH_VERSION}")


if __name__ == "__main__":
    main()
