from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH_VERSION = 1


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_proof_dag() -> None:
    path = ROOT / "backend/corner_half/proof_dag.py"
    replace_once(
        path,
        '''@lru_cache(maxsize=None)\ndef raw_input_proof(cap: int) -> ProofNode:\n    if cap < 1:\n        raise ProofDagError("cap must be positive")\n    return _node("RAW_INPUT", cap, input_full(), note="one-layer SSSS")\n\n\ndef rotate_proof(child: ProofNode, steps_cw: int) -> ProofNode:\n''',
        '''@lru_cache(maxsize=None)\ndef raw_input_proof(cap: int) -> ProofNode:\n    if cap < 1:\n        raise ProofDagError("cap must be positive")\n    return _node("RAW_INPUT", cap, input_full(), note="one-layer SSSS")\n\n\n@lru_cache(maxsize=None)\ndef full_s_tower_proof(height: int, cap: int) -> ProofNode:\n    """Build an all-SSSS tower with one raw layer per added level.\n\n    The previous generic S-only route rebuilt the same one-layer SSSS mask from\n    four isolated cells for every level.  A raw input already is exactly SSSS,\n    so the direct stack chain is both smaller and independently replayable.\n    """\n    if not 1 <= height <= cap:\n        raise ProofDagError("full S tower height must be in 1..cap")\n    raw = raw_input_proof(cap)\n    current = raw\n    for _ in range(1, height):\n        current = stack_proof(current, raw)\n    expected = code([[ORDINARY] * 4 for _ in range(height)])\n    if current.result != expected:\n        raise ProofDagError(("full S tower proof", height, current.result, expected))\n    return current\n\n\ndef rotate_proof(child: ProofNode, steps_cw: int) -> ProofNode:\n''',
    )
    replace_once(
        path,
        '''    if not 0 <= mask < 16:\n        raise ProofDagError("mask must be 0..15")\n    current = empty_shape_proof(cap)\n''',
        '''    if not 0 <= mask < 16:\n        raise ProofDagError("mask must be 0..15")\n    if mask == 0:\n        return empty_shape_proof(cap)\n    if mask == 0b1111:\n        return raw_input_proof(cap)\n    current = empty_shape_proof(cap)\n''',
    )
    replace_once(
        path,
        '''    if not normalized:\n        return empty_shape_proof(cap)\n    layer_codes = normalized.split(":")\n    prefix = ":".join(layer_codes[:-1])\n''',
        '''    if not normalized:\n        return empty_shape_proof(cap)\n    layer_codes = normalized.split(":")\n    if all(layer == ORDINARY * 4 for layer in layer_codes):\n        return full_s_tower_proof(len(layer_codes), cap)\n    prefix = ":".join(layer_codes[:-1])\n''',
    )
    replace_once(
        path,
        '''        raw_input_proof, single_cell_proof, empty_shape_proof,\n''',
        '''        raw_input_proof, full_s_tower_proof, single_cell_proof, empty_shape_proof,\n''',
    )


def patch_corner_full_replay() -> None:
    path = ROOT / "backend/corner_half/corner_full_replay.py"
    replace_once(
        path,
        '''    ops.append(FullOperationStep("swap_restore_east_tower",code(rotated),code(prefab_tt),code(imported),a,a))\n    ops.append(FullOperationStep("rotate_ccw_restore",code(imported),"",code(final),a,a))\n    return final\n\n\ndef _restore_after_c7(current, a:str, height:int, cap:int, ops:list[FullOperationStep], audit: bool = True):\n''',
        '''    ops.append(FullOperationStep("swap_restore_east_tower",code(rotated),code(prefab_tt),code(imported),a,a))\n    ops.append(FullOperationStep("rotate_ccw_restore",code(imported),"",code(final),a,a))\n    return final\n\n\ndef _ensure_canonical(current, a:str, height:int, cap:int, ops:list[FullOperationStep], audit: bool = True):\n    """Return an already canonical support state without emitting identity work."""\n    t = _tower(height)\n    if _columns(current, cap) == (a, t, t, t):\n        return current\n    return _restore_from_east(current, a, height, cap, ops, audit)\n\n\ndef _restore_after_c7(current, a:str, height:int, cap:int, ops:list[FullOperationStep], audit: bool = True):\n''',
    )
    text = path.read_text(encoding="utf-8")
    count = text.count("current=_restore_from_east(")
    if count < 5:
        raise RuntimeError(f"{path}: expected replay restore sites, got {count}")
    path.write_text(text.replace("current=_restore_from_east(", "current=_ensure_canonical("), encoding="utf-8")


def main() -> None:
    patch_proof_dag()
    patch_corner_full_replay()
    print(f"latest proof fast paths applied v{PATCH_VERSION}")


if __name__ == "__main__":
    main()
