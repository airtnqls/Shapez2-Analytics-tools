from __future__ import annotations

import contextlib
import copy
import io
import sys
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

with contextlib.redirect_stdout(io.StringIO()):
    from data_operations import simplify_shape
    from shape import Quadrant, ReverseTracer, Shape
    import symbolic_frontier_automaton as sfa


@dataclass(frozen=True)
class ProductionNode:
    op: str
    shape: str = ""
    children: tuple["ProductionNode", ...] = field(default_factory=tuple)
    note: str = ""


_GRAPH_CACHE: dict[tuple[str, int], ProductionNode] = {}
SHALLOW_INPUT_KINDS = frozenset(
    {
        "single_column",
        "east_half",
        "west_half",
        "north_half",
        "south_half",
        "single_layer_pair",
    }
)


def build_claw_pinpush_graph(
    target: str,
    predecessor: str = "",
    layers: int = 6,
    decomposition_tree: dict[str, Any] | None = None,
    max_depth: int = 5,
) -> ProductionNode | None:
    _GRAPH_CACHE.clear()
    target_norm = sfa.normalize_code(target)
    predecessor_norm = sfa.normalize_code(predecessor) if predecessor else ""
    pushed = sfa.bitmask_push_pin(predecessor_norm, layers) if predecessor_norm else ""

    if predecessor_norm and pushed == target_norm:
        child = _build_shape_graph(predecessor_norm, max_depth=max_depth, seen=set())
        graph = ProductionNode("pin_push", _detail_or_self(target_norm), (child,), "input_predecessor")
        return _refine_shallow_pin_push_leaves(graph, layers, max_depth)
    if decomposition_tree:
        graph = _from_decomposition_tree(decomposition_tree, layers, max_depth=max_depth, seen=set())
        return _refine_shallow_pin_push_leaves(graph, layers, max_depth)
    return None


def build_shape_production_graph(code: str, max_depth: int = 5) -> ProductionNode:
    _GRAPH_CACHE.clear()
    graph = _build_shape_graph(code, max_depth=max_depth, seen=set())
    return _refine_shallow_pin_push_leaves(graph, max(6, len(Shape.from_string(code).layers)), max_depth)


def render_graph(node: ProductionNode | None) -> list[str]:
    if node is None:
        return []

    def walk(current: ProductionNode, depth: int) -> list[str]:
        indent = "  " * depth
        suffix = f" {current.shape}" if current.shape else ""
        lines = [f"{indent}[{current.op}]{suffix}".rstrip()]
        for child in current.children:
            lines.extend(walk(child, depth + 1))
        return lines

    return walk(node, 0)


def validate_graph(node: ProductionNode | None, layers: int = 6) -> tuple[bool, str]:
    if node is None:
        return False, "missing_graph"
    try:
        _validate_node(node, layers)
        return True, "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def assess_production_graph(
    node: ProductionNode | None,
    layers: int = 6,
    probe_max_steps: int = 3,
    probe_max_states: int = 12000,
    probe_pair_limit: int = 180,
    probe_shallow_inputs: bool = False,
) -> dict[str, object]:
    valid = validate_graph(node, layers)
    quality = graph_quality_stats(node)
    diagnostics = (
        diagnose_complex_inputs(
            node,
            probe_max_steps=probe_max_steps,
            probe_max_states=probe_max_states,
            probe_pair_limit=probe_pair_limit,
        )
        if int(quality["complex_input_leaves"])
        else []
    )
    shallow_diagnostics = (
        diagnose_shallow_inputs(
            node,
            include_probe=probe_shallow_inputs,
            probe_max_steps=probe_max_steps,
            probe_max_states=probe_max_states,
            probe_pair_limit=probe_pair_limit,
        )
        if int(quality["shallow_input_leaves"])
        else []
    )
    unknown_shallow_diagnostics = [
        diagnostic
        for diagnostic in shallow_diagnostics
        if not is_impossible_rule_closed_shallow_diagnostic(diagnostic)
        and not is_known_structural_shallow_diagnostic(diagnostic)
    ]
    return {
        "valid": valid,
        "quality": quality,
        "diagnostics": diagnostics,
        "shallow_diagnostics": shallow_diagnostics,
        "unknown_shallow_diagnostics": unknown_shallow_diagnostics,
        "resolved": bool(node) and valid[0] and not int(quality["complex_input_leaves"]),
        "structural_resolved": (
            bool(node)
            and valid[0]
            and not int(quality["complex_input_leaves"])
            and not unknown_shallow_diagnostics
        ),
        "strict_resolved": (
            bool(node)
            and valid[0]
            and not int(quality["complex_input_leaves"])
            and not int(quality["shallow_input_leaves"])
            and not int(quality["terminal_leaves"])
        ),
    }


def pinpush_overall_verdict(
    production_resolved: bool,
    pushed_matches: bool,
    claw_possible: bool,
    strict_verdict: str,
    explain_verdict: str,
) -> str:
    if strict_verdict == "impossible" or explain_verdict == "impossible":
        return "impossible"
    if production_resolved and (pushed_matches or claw_possible or explain_verdict == "possible"):
        return "possible"
    return "unknown"


def graph_quality_stats(node: ProductionNode | None) -> dict[str, object]:
    stats: dict[str, object] = {
        "nodes": 0,
        "max_depth": 0,
        "input_leaves": 0,
        "max_input_leaf_depth": 0,
        "max_shallow_input_leaf_depth": 0,
        "max_complex_input_leaf_depth": 0,
        "complex_input_leaves": 0,
        "shallow_input_leaves": 0,
        "terminal_leaves": 0,
        "legacy_possible_terminal_leaves": 0,
        "complex_input_shapes": [],
        "shallow_input_shapes": [],
        "terminal_shapes": [],
        "input_leaf_kinds": {},
        "ops": {},
    }
    if node is None:
        return stats

    def visit(current: ProductionNode, depth: int = 0) -> None:
        stats["nodes"] = int(stats["nodes"]) + 1
        stats["max_depth"] = max(int(stats["max_depth"]), depth)
        ops = stats["ops"]
        assert isinstance(ops, dict)
        ops[current.op] = int(ops.get(current.op, 0)) + 1
        if current.op == "input" and not current.children:
            stats["input_leaves"] = int(stats["input_leaves"]) + 1
            stats["max_input_leaf_depth"] = max(int(stats["max_input_leaf_depth"]), depth)
            kinds = stats["input_leaf_kinds"]
            assert isinstance(kinds, dict)
            kind = _input_leaf_kind(current.shape)
            kinds[kind] = int(kinds.get(kind, 0)) + 1
            if _is_shallow_input_leaf(current.shape):
                stats["shallow_input_leaves"] = int(stats["shallow_input_leaves"]) + 1
                stats["max_shallow_input_leaf_depth"] = max(int(stats["max_shallow_input_leaf_depth"]), depth)
                shapes = stats["shallow_input_shapes"]
                assert isinstance(shapes, list)
                if len(shapes) < 8:
                    shapes.append(current.shape)
            if _is_complex_input_leaf(current.shape):
                stats["complex_input_leaves"] = int(stats["complex_input_leaves"]) + 1
                stats["max_complex_input_leaf_depth"] = max(int(stats["max_complex_input_leaf_depth"]), depth)
                shapes = stats["complex_input_shapes"]
                assert isinstance(shapes, list)
                if len(shapes) < 8:
                    shapes.append(current.shape)
        if current.op.startswith("terminal_") and not current.children:
            stats["terminal_leaves"] = int(stats["terminal_leaves"]) + 1
            if current.op.startswith("terminal_legacy_possible_"):
                stats["legacy_possible_terminal_leaves"] = int(stats["legacy_possible_terminal_leaves"]) + 1
            shapes = stats["terminal_shapes"]
            assert isinstance(shapes, list)
            if len(shapes) < 8:
                shapes.append(current.shape)
        for child in current.children:
            visit(child, depth + 1)

    visit(node)
    return stats


def input_leaf_kinds(node: ProductionNode | None) -> dict[str, int]:
    quality = graph_quality_stats(node)
    kinds = quality["input_leaf_kinds"]
    assert isinstance(kinds, dict)
    return {str(key): int(value) for key, value in kinds.items()}


def input_leaf_examples(node: ProductionNode | None, max_per_kind: int = 4) -> dict[str, list[str]]:
    examples: dict[str, list[str]] = {}
    if node is None:
        return examples

    def visit(current: ProductionNode) -> None:
        if current.op == "input" and not current.children:
            kind = _input_leaf_kind(current.shape)
            values = examples.setdefault(kind, [])
            detail = _detail_or_self(current.shape)
            if len(values) < max_per_kind and detail not in values:
                values.append(detail)
        for child in current.children:
            visit(child)

    visit(node)
    return examples


def diagnose_terminal_leaves(node: ProductionNode | None) -> list[dict[str, object]]:
    if node is None:
        return []
    diagnostics: list[dict[str, object]] = []

    def visit(current: ProductionNode, depth: int = 0) -> None:
        if current.op.startswith("terminal_") and not current.children:
            legacy, strict, cls, reason = sfa.legacy_verdict(_simplified_or_self(current.shape))
            explanation = _explain_shape_dict_cached(_simplified_or_self(current.shape), max(6, len(_simplified_or_self(current.shape).split(":"))))
            tree = explanation.get("decomposition_tree") if explanation else None
            open_leaf_keys: dict[str, int] = {}
            open_leaf_descriptions: tuple[str, ...] = ()
            open_leaf_shapes: tuple[str, ...] = ()
            self_open_leaf_keys: dict[str, int] = {}
            unexpanded_leaf_keys: dict[str, int] = {}
            self_unexpanded_leaf_keys: dict[str, int] = {}
            explain_reason = ""
            if isinstance(explanation, dict):
                explain_reason = str(explanation.get("explain_reason", ""))
            if isinstance(tree, dict):
                try:
                    open_leaf_keys = _decomposition_open_leaf_keys_from_dict(tree)
                    open_leaf_descriptions = _decomposition_open_leaf_descriptions_from_dict(tree)
                    open_leaf_shapes = _decomposition_open_leaf_shapes_from_dict(tree)
                    current_norm = _simplified_or_self(current.shape)
                    self_open_leaf_keys = _decomposition_open_leaf_keys_from_dict(
                        tree,
                        shape_filter=current_norm,
                    )
                    unexpanded_leaf_keys = _decomposition_unexpanded_leaf_keys_from_dict(tree)
                    self_unexpanded_leaf_keys = _decomposition_unexpanded_leaf_keys_from_dict(
                        tree,
                        shape_filter=current_norm,
                    )
                except Exception:
                    open_leaf_keys = {}
                    open_leaf_descriptions = ()
                    open_leaf_shapes = ()
                    self_open_leaf_keys = {}
                    unexpanded_leaf_keys = {}
                    self_unexpanded_leaf_keys = {}
            diagnostics.append(
                {
                    "shape": _simplified_or_self(current.shape),
                    "detail": current.shape,
                    "op": current.op,
                    "note": current.note,
                    "leaf_depth": depth,
                    "explain_reason": explain_reason,
                    "open_leaf_keys": open_leaf_keys,
                    "open_leaf_descriptions": open_leaf_descriptions,
                    "open_leaf_shapes": open_leaf_shapes,
                    "self_open_leaf_keys": self_open_leaf_keys,
                    "self_open_leaf_count": sum(self_open_leaf_keys.values()),
                    "unexpanded_leaf_keys": unexpanded_leaf_keys,
                    "self_unexpanded_leaf_keys": self_unexpanded_leaf_keys,
                    "self_unexpanded_leaf_count": sum(self_unexpanded_leaf_keys.values()),
                    "legacy_verdict": legacy,
                    "legacy_strict_verdict": strict,
                    "legacy_class": cls,
                    "legacy_reason": reason,
                    "leaf_features": _leaf_features(Shape.from_string(current.shape)),
                }
            )
        for child in current.children:
            visit(child, depth + 1)

    visit(node)
    return diagnostics


def _decomposition_open_leaf_keys_from_dict(
    tree: dict[str, object],
    shape_filter: str | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()

    def visit(current: dict[str, object]) -> None:
        children = current.get("children")
        if isinstance(children, list) and children:
            for child in children:
                if isinstance(child, dict):
                    visit(child)
            return
        kind = str(current.get("kind", ""))
        detail = str(current.get("detail", ""))
        if kind in sfa.OPEN_DECOMPOSITION_LEAF_KINDS or (kind == "pp" and detail == "empty_trace"):
            if shape_filter is not None and _simplified_or_self(str(current.get("shape", ""))) != shape_filter:
                return
            counts[_decomposition_root_key_from_dict(current)] += 1

    visit(tree)
    return dict(counts)


def _decomposition_open_leaf_descriptions_from_dict(tree: dict[str, object], limit: int = 4) -> tuple[str, ...]:
    descriptions: list[str] = []

    def visit(current: dict[str, object]) -> None:
        if len(descriptions) >= limit:
            return
        children = current.get("children")
        if isinstance(children, list) and children:
            for child in children:
                if isinstance(child, dict):
                    visit(child)
            return
        kind = str(current.get("kind", ""))
        detail = str(current.get("detail", ""))
        if kind in sfa.OPEN_DECOMPOSITION_LEAF_KINDS or (kind == "pp" and detail == "empty_trace"):
            descriptions.append(f"{_decomposition_root_key_from_dict(current)} shape={current.get('shape', '')}")

    visit(tree)
    return tuple(descriptions)


def _decomposition_open_leaf_shapes_from_dict(tree: dict[str, object], limit: int = 8) -> tuple[str, ...]:
    shapes: list[str] = []

    def visit(current: dict[str, object]) -> None:
        if len(shapes) >= limit:
            return
        children = current.get("children")
        if isinstance(children, list) and children:
            for child in children:
                if isinstance(child, dict):
                    visit(child)
            return
        kind = str(current.get("kind", ""))
        detail = str(current.get("detail", ""))
        if kind in sfa.OPEN_DECOMPOSITION_LEAF_KINDS or (kind == "pp" and detail == "empty_trace"):
            shapes.append(_simplified_or_self(str(current.get("shape", ""))))

    visit(tree)
    return tuple(shapes)


UNEXPANDED_DECOMPOSITION_LEAF_KINDS = frozenset({"pin_push", "stack", "swap"})


def _decomposition_unexpanded_leaf_keys_from_dict(
    tree: dict[str, object],
    shape_filter: str | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()

    def visit(current: dict[str, object]) -> None:
        children = current.get("children")
        if isinstance(children, list) and children:
            for child in children:
                if isinstance(child, dict):
                    visit(child)
            return
        kind = str(current.get("kind", ""))
        if kind not in UNEXPANDED_DECOMPOSITION_LEAF_KINDS:
            return
        if shape_filter is not None and _simplified_or_self(str(current.get("shape", ""))) != shape_filter:
            return
        counts[_decomposition_root_key_from_dict(current)] += 1

    visit(tree)
    return dict(counts)


def _decomposition_root_key_from_dict(node: dict[str, object]) -> str:
    root_key = node.get("root_key")
    if root_key:
        return str(root_key)
    kind = str(node.get("kind", ""))
    detail = str(node.get("detail", ""))
    return f"{kind}:{detail}" if detail else kind


def diagnose_complex_inputs(
    node: ProductionNode | None,
    probe_max_steps: int = 3,
    probe_max_states: int = 12000,
    probe_pair_limit: int = 180,
) -> list[dict[str, object]]:
    return diagnose_input_leaves(
        node,
        kinds={"complex"},
        probe_max_steps=probe_max_steps,
        probe_max_states=probe_max_states,
        probe_pair_limit=probe_pair_limit,
    )


def diagnose_shallow_inputs(
    node: ProductionNode | None,
    include_probe: bool = False,
    probe_max_steps: int = 3,
    probe_max_states: int = 12000,
    probe_pair_limit: int = 180,
) -> list[dict[str, object]]:
    return diagnose_input_leaves(
        node,
        kinds=SHALLOW_INPUT_KINDS,
        include_probe=include_probe,
        probe_max_steps=probe_max_steps,
        probe_max_states=probe_max_states,
        probe_pair_limit=probe_pair_limit,
    )


def diagnose_input_leaves(
    node: ProductionNode | None,
    kinds: set[str] | frozenset[str] | None = None,
    include_probe: bool = False,
    probe_max_steps: int = 3,
    probe_max_states: int = 12000,
    probe_pair_limit: int = 180,
) -> list[dict[str, object]]:
    if node is None:
        return []
    seen: set[str] = set()
    diagnostics: list[dict[str, object]] = []

    def visit(current: ProductionNode, depth: int = 0) -> None:
        if current.op == "input" and not current.children:
            normalized = _simplified_or_self(current.shape)
            kind = _input_leaf_kind(current.shape)
            if (kinds is None or kind in kinds) and normalized not in seen:
                seen.add(normalized)
                diagnostics.append(
                    _input_leaf_diagnostic(
                        current.shape,
                        include_probe=include_probe,
                        probe_max_steps=probe_max_steps,
                        probe_max_states=probe_max_states,
                        probe_pair_limit=probe_pair_limit,
                        leaf_depth=depth,
                    )
                )
        for child in current.children:
            visit(child, depth + 1)

    visit(node)
    return diagnostics


def _is_complex_input_leaf(code: str) -> bool:
    return _input_leaf_kind(code) == "complex"


def _is_shallow_input_leaf(code: str) -> bool:
    return _input_leaf_kind(code) in SHALLOW_INPUT_KINDS


def _input_leaf_kind(code: str) -> str:
    normalized = _simplified_or_self(code)
    if not normalized:
        return "empty"
    layers = normalized.split(":")
    occupied = [(li, qi) for li, layer in enumerate(layers) for qi, ch in enumerate(layer) if ch != "-"]
    if len(occupied) <= 1:
        return "single_cell"
    quadrants = {qi for _li, qi in occupied}
    nonempty_layers = {li for li, _qi in occupied}
    if len(quadrants) == 1:
        return "single_column"
    allowed_halves = (
        ("east_half", {0, 1}),
        ("west_half", {2, 3}),
        ("north_half", {0, 3}),
        ("south_half", {1, 2}),
    )
    for name, half in allowed_halves:
        if quadrants <= half:
            return name
    if len(nonempty_layers) == 1 and len(occupied) <= 2:
        return "single_layer_pair"
    return "complex"


def _input_leaf_diagnostic(
    code: str,
    include_probe: bool = False,
    probe_max_steps: int = 3,
    probe_max_states: int = 12000,
    probe_pair_limit: int = 180,
    leaf_depth: int | None = None,
) -> dict[str, object]:
    normalized = _simplified_or_self(code)
    kind = _input_leaf_kind(code)
    counts = {
        "stack": 0,
        "swap_rot": 0,
        "cut_east_self_rot": 0,
        "destroy_half_rot": 0,
        "crystal_generator": 0,
    }
    try:
        shape = Shape.from_string(code)
        counts["stack"] = len(ReverseTracer.inverse_stack(shape, 1))
        counts["crystal_generator"] = len(ReverseTracer.inverse_crystal_generator(shape, 1))
        for turns in range(4):
            rotated = shape.copy()
            for _ in range(turns):
                rotated = rotated.rotate(False)
            counts["swap_rot"] += len(ReverseTracer.inverse_swap(rotated, turns, 1))
            counts["destroy_half_rot"] += len(ReverseTracer.inverse_destroy_half(rotated, turns, 1))
            _west, east = rotated.simple_cutter(False)
            if _simplified_or_self(repr(east)) == _simplified_or_self(repr(rotated)):
                counts["cut_east_self_rot"] += 1
    except Exception as exc:
        return {
            "shape": normalized,
            "detail": code,
            "kind": kind,
            "error": f"{type(exc).__name__}: {exc}",
        }
    total = sum(counts.values())
    candidate_quality = _best_local_candidate_quality(code)
    legacy_info = _legacy_verdict_info(code)
    impossible_rule = legacy_info if legacy_info["legacy_strict_verdict"] == "impossible" else None
    unsupported_class = _unsupported_leaf_class(shape, kind) if total == 0 else ""
    reason = "no_supported_reverse_candidate"
    if total:
        reason = "candidate_exists_but_not_selected"
        if candidate_quality and not _candidate_improves_leaf(kind, candidate_quality):
            reason = "candidate_exists_but_no_quality_gain"
    candidate_preserves_leaf = bool(
        candidate_quality
        and normalized
        in {
            _simplified_or_self(str(shape_code))
            for shape_code in list(candidate_quality.get("shallow_input_shapes", []))
            + list(candidate_quality.get("complex_input_shapes", []))
        }
    )
    diagnostic = {
        "shape": normalized,
        "detail": code,
        "kind": kind,
        "leaf_depth": leaf_depth,
        "reverse_candidate_counts": counts,
        "best_local_candidate_quality": candidate_quality,
        "candidate_preserves_leaf": candidate_preserves_leaf,
        "reason": reason,
        "legacy_verdict": legacy_info["legacy_verdict"],
        "legacy_strict_verdict": legacy_info["legacy_strict_verdict"],
        "legacy_class": legacy_info["legacy_class"],
        "legacy_reason": legacy_info["legacy_reason"],
        "impossible_rule_closed": bool(impossible_rule),
    }
    if kind in SHALLOW_INPUT_KINDS:
        diagnostic["shallow_class"] = _shallow_leaf_class(shape, kind)
        diagnostic["leaf_features"] = _leaf_features(shape)
        diagnostic["shallow_terminal_hint"] = _shallow_terminal_hint(code, shape)
    if unsupported_class:
        diagnostic["unsupported_class"] = unsupported_class
        diagnostic["extended_reverse_candidate_counts"] = _reverse_candidate_counts(shape, search_depth=6)
        diagnostic["leaf_features"] = _leaf_features(shape)
    if unsupported_class or include_probe:
        probe = bounded_forward_probe(
            code,
            max_steps=probe_max_steps,
            max_states=probe_max_states,
            pair_limit=probe_pair_limit,
        )
        diagnostic["bounded_forward_probe"] = probe
        if kind in SHALLOW_INPUT_KINDS and bool(probe.get("reachable")):
            diagnostic["probe_actionable"] = True
    return diagnostic


def bounded_forward_probe(code: str, max_steps: int = 3, max_states: int = 12000, pair_limit: int = 180) -> dict[str, object]:
    return copy.deepcopy(_bounded_forward_probe_cached(_simplified_or_self(code), max_steps, max_states, pair_limit))


@lru_cache(maxsize=4096)
def _bounded_forward_probe_cached(
    normalized_code: str,
    max_steps: int,
    max_states: int,
    pair_limit: int,
) -> dict[str, object]:
    code = normalized_code
    target = _simplified_or_self(code)
    seeds = _forward_probe_seeds(code)
    target_features = _leaf_features(Shape.from_string(code)) if target else {}
    op_counts: Counter[str] = Counter()
    pruned_counts: Counter[str] = Counter()
    if target in seeds:
        return {
            "reachable": True,
            "status": "reachable",
            "steps": 0,
            "steps_completed": 0,
            "states": len(seeds),
            "frontier": len(seeds),
            "max_steps": max_steps,
            "max_states": max_states,
            "op_counts": {},
            "pruned_counts": {},
            "target_features": target_features,
            "truncated": False,
        }

    states: dict[str, str] = {seed: "seed" for seed in seeds}
    frontier = set(seeds)
    truncated = False
    steps_completed = 0
    for step in range(1, max_steps + 1):
        new_states: dict[str, str] = {}
        for state in list(frontier):
            _forward_add_unary(new_states, state, target_features, op_counts, pruned_counts)
        pair_pool = _rank_forward_states(states, target_features, pair_limit)
        for left in _rank_forward_states(frontier, target_features, pair_limit):
            for right in pair_pool:
                _forward_add_pair(new_states, left, right, target_features, op_counts, pruned_counts)
                if left != right:
                    _forward_add_pair(new_states, right, left, target_features, op_counts, pruned_counts)
                if len(states) + _new_unique_state_count(new_states, states) >= max_states:
                    truncated = True
                    break
            if truncated:
                break
        if target in new_states:
            return {
                "reachable": True,
                "status": "reachable",
                "steps": step,
                "steps_completed": step,
                "states": min(len(states) + len(new_states), max_states),
                "frontier": len(new_states),
                "max_steps": max_steps,
                "max_states": max_states,
                "op_counts": dict(op_counts),
                "pruned_counts": dict(pruned_counts),
                "target_features": target_features,
                "truncated": truncated,
            }
        frontier = set()
        for shape, producer in new_states.items():
            if shape in states:
                continue
            states[shape] = producer
            frontier.add(shape)
            if len(states) >= max_states:
                truncated = True
                break
        steps_completed = step
        if not frontier or truncated:
            break
    status = "not_found_truncated" if truncated else "not_found_complete"
    return {
        "reachable": False,
        "status": status,
        "steps": max_steps,
        "steps_completed": steps_completed,
        "states": len(states),
        "frontier": len(frontier),
        "max_steps": max_steps,
        "max_states": max_states,
        "op_counts": dict(op_counts),
        "pruned_counts": dict(pruned_counts),
        "target_features": target_features,
        "truncated": truncated,
    }


def _forward_probe_seeds(code: str) -> set[str]:
    seeds: set[str] = set()
    try:
        shape = Shape.from_string(code)
    except Exception:
        return seeds
    for layer in shape.layers:
        for quadrant_index, quadrant in enumerate(layer.quadrants):
            if quadrant is None:
                continue
            abstract = "c" if quadrant.shape == "c" else ("P" if quadrant.shape == "P" else "S")
            for q in range(4):
                seeds.add(_simplified_or_self("".join(abstract if i == q else "-" for i in range(4))))
            if quadrant_index < 4:
                seeds.add(_simplified_or_self("".join(abstract if i == quadrant_index else "-" for i in range(4))))
    return {seed for seed in seeds if seed}


def _rank_forward_states(states: dict[str, str] | set[str], target_features: dict[str, int], limit: int) -> list[str]:
    values = list(states.keys()) if isinstance(states, dict) else list(states)
    values.sort(key=lambda code: (_forward_feature_distance(code, target_features), len(code), code))
    return values[:limit]


def _new_unique_state_count(new_states: dict[str, str], existing_states: dict[str, str]) -> int:
    return sum(1 for shape in new_states if shape not in existing_states)


def _forward_feature_distance(code: str, target_features: dict[str, int]) -> tuple[int, int, int, int, int]:
    if not target_features:
        return (0, 0, 0, 0, 0)
    try:
        features = _leaf_features(Shape.from_string(code))
    except Exception:
        return (999, 999, 999, 999, 999)
    return (
        abs(features["layers"] - int(target_features["layers"])),
        abs(features["occupied"] - int(target_features["occupied"])),
        abs(features["crystals"] - int(target_features["crystals"])),
        abs(features["solids"] - int(target_features["solids"])),
        abs(features["pins"] - int(target_features["pins"])),
    )


def _forward_add_unary(
    out: dict[str, str],
    code: str,
    target_features: dict[str, int],
    op_counts: Counter[str],
    pruned_counts: Counter[str],
) -> None:
    try:
        shape = Shape.from_string(code)
    except Exception:
        return
    rotated = shape.copy()
    for turns in range(1, 4):
        rotated = rotated.rotate(True)
        _remember_forward(out, repr(rotated), f"rotate_cw {turns}", target_features, op_counts, pruned_counts)
    _west, east = shape.simple_cutter(False)
    _remember_forward(out, repr(east), "cut_east", target_features, op_counts, pruned_counts)
    for color in ("r",):
        _remember_forward(
            out,
            repr(shape.crystal_generator(color)),
            f"crystal_generator {color}",
            target_features,
            op_counts,
            pruned_counts,
        )


def _forward_add_pair(
    out: dict[str, str],
    left_code: str,
    right_code: str,
    target_features: dict[str, int],
    op_counts: Counter[str],
    pruned_counts: Counter[str],
) -> None:
    try:
        left = Shape.from_string(left_code)
        right = Shape.from_string(right_code)
    except Exception:
        return
    if not _forward_pair_within_pre_bounds(left, right, target_features):
        pruned_counts["pair_pre"] += 1
        return
    _remember_forward(out, repr(Shape.stack(left, right)), "stack", target_features, op_counts, pruned_counts)
    swap_left, swap_right = Shape.swap(left, right)
    _remember_forward(out, repr(swap_left), "swap", target_features, op_counts, pruned_counts)
    _remember_forward(out, repr(swap_right), "swap", target_features, op_counts, pruned_counts)


def _remember_forward(
    out: dict[str, str],
    raw_code: str,
    producer: str,
    target_features: dict[str, int],
    op_counts: Counter[str],
    pruned_counts: Counter[str],
) -> None:
    normalized = _simplified_or_self(raw_code)
    if not normalized or normalized in out:
        return
    if not _forward_state_within_bounds(raw_code, target_features):
        pruned_counts[producer] += 1
        return
    out.setdefault(normalized, producer)
    op_counts[producer] += 1


def _forward_state_within_bounds(raw_code: str, target_features: dict[str, int]) -> bool:
    if not target_features:
        return True
    try:
        features = _leaf_features(Shape.from_string(raw_code))
    except Exception:
        return False
    return (
        features["layers"] <= max(1, int(target_features["layers"]))
        and features["occupied"] <= int(target_features["occupied"])
        and features["pins"] <= int(target_features["pins"]) + 1
        and features["solids"] <= int(target_features["solids"]) + 1
        and features["crystals"] <= int(target_features["crystals"]) + 2
    )


def _forward_pair_within_pre_bounds(left: Shape, right: Shape, target_features: dict[str, int]) -> bool:
    if not target_features:
        return True
    left_features = _leaf_features(left)
    right_features = _leaf_features(right)
    return (
        max(left_features["layers"], right_features["layers"]) <= max(1, int(target_features["layers"]))
        and left_features["occupied"] + right_features["occupied"] <= int(target_features["occupied"]) + 2
        and left_features["pins"] + right_features["pins"] <= int(target_features["pins"]) + 2
        and left_features["solids"] + right_features["solids"] <= int(target_features["solids"]) + 2
        and left_features["crystals"] + right_features["crystals"] <= int(target_features["crystals"]) + 4
    )


def _reverse_candidate_counts(shape: Shape, search_depth: int) -> dict[str, int]:
    counts = {
        "stack": len(ReverseTracer.inverse_stack(shape, search_depth)),
        "swap_rot": 0,
        "destroy_half_rot": 0,
        "crystal_generator": len(ReverseTracer.inverse_crystal_generator(shape, search_depth)),
    }
    for turns in range(4):
        rotated = shape.copy()
        for _ in range(turns):
            rotated = rotated.rotate(False)
        counts["swap_rot"] += len(ReverseTracer.inverse_swap(rotated, turns, search_depth))
        counts["destroy_half_rot"] += len(ReverseTracer.inverse_destroy_half(rotated, turns, search_depth))
    return counts


def _leaf_features(shape: Shape) -> dict[str, int]:
    crystals = 0
    pins = 0
    solids = 0
    occupied = 0
    for layer in shape.layers:
        for quadrant in layer.quadrants:
            if quadrant is None:
                continue
            occupied += 1
            if quadrant.shape == "c":
                crystals += 1
            elif quadrant.shape == "P":
                pins += 1
            else:
                solids += 1
    return {
        "layers": len(shape.layers),
        "occupied": occupied,
        "crystals": crystals,
        "pins": pins,
        "solids": solids,
    }


def _unsupported_leaf_class(shape: Shape, kind: str) -> str:
    features = _leaf_features(shape)
    if kind == "complex" and features["crystals"] and features["solids"]:
        return "unsupported_crystal_solid_entangled"
    if kind == "complex" and features["crystals"] and features["pins"]:
        return "unsupported_crystal_pin_entangled"
    if kind == "complex" and features["crystals"]:
        return "unsupported_crystal_entangled"
    if kind == "complex":
        return "unsupported_complex_geometry"
    return "unsupported_simple_leaf"


def _shallow_leaf_class(shape: Shape, kind: str) -> str:
    features = _leaf_features(shape)
    if kind in {"east_half", "west_half", "north_half", "south_half"}:
        if features["crystals"]:
            return "multi_cell_half_with_crystal_requires_lateral_merge"
        return "multi_cell_half_requires_lateral_merge"
    if kind == "single_column":
        if features["crystals"]:
            return "single_column_with_crystal_stack_blocked"
        return "single_column_stack_candidate_no_gain"
    if kind == "single_layer_pair":
        return "single_layer_pair_requires_lateral_merge"
    return "shallow_leaf_no_quality_gain"


KNOWN_STRUCTURAL_SHALLOW_CLASSES = frozenset(
    {
        "multi_cell_half_with_crystal_requires_lateral_merge",
        "multi_cell_half_requires_lateral_merge",
        "single_column_with_crystal_stack_blocked",
        "single_column_stack_candidate_no_gain",
        "single_layer_pair_requires_lateral_merge",
    }
)


def _probe_status(probe: dict[str, object]) -> str:
    status = str(probe.get("status", ""))
    if status:
        return status
    if bool(probe.get("reachable")):
        return "reachable"
    if bool(probe.get("truncated")):
        return "not_found_truncated"
    return "not_found_complete"


def is_known_structural_shallow_diagnostic(diagnostic: dict[str, object]) -> bool:
    if is_impossible_rule_closed_shallow_diagnostic(diagnostic):
        return False
    if diagnostic.get("reason") != "candidate_exists_but_no_quality_gain":
        return False
    if diagnostic.get("probe_actionable"):
        return False
    probe = diagnostic.get("bounded_forward_probe")
    if isinstance(probe, dict) and _probe_status(probe) in {"reachable", "not_found_truncated"}:
        return False
    return str(diagnostic.get("shallow_class", "")) in KNOWN_STRUCTURAL_SHALLOW_CLASSES


KNOWN_UNSUPPORTED_COMPLEX_CLASSES = frozenset(
    {
        "unsupported_crystal_solid_entangled",
    }
)


def _legacy_verdict_info(code: str) -> dict[str, str]:
    legacy, strict, cls, reason = sfa.legacy_verdict(_simplified_or_self(code))
    return {
        "legacy_verdict": legacy,
        "legacy_strict_verdict": strict,
        "legacy_class": cls,
        "legacy_reason": reason,
    }


def _shallow_terminal_hint(code: str, shape: Shape) -> str:
    legacy, strict, _cls, _reason = sfa.legacy_verdict(_simplified_or_self(code))
    if legacy != "possible" or strict != "possible":
        return ""
    layers = max(6, len(shape.layers))
    if sfa.bitmask_inverse_push_pin_candidates(_simplified_or_self(code), layers):
        return ""
    if sfa.bitmask_bridge_inverse_push_pin_candidates(_simplified_or_self(code), layers):
        return ""
    try:
        explanation = _explain_shape_dict_cached(_simplified_or_self(code), layers)
    except Exception:
        return "legacy_possible_terminal_no_pinpush_predecessor"
    explain_reason = str(explanation.get("explain_reason", "")) if explanation else ""
    if explain_reason in {"swap_limited", "swappable"}:
        return f"legacy_possible_{explain_reason}_terminal_no_pinpush_predecessor"
    if explain_reason:
        return f"legacy_possible_{explain_reason}_terminal_no_pinpush_predecessor"
    return "legacy_possible_terminal_no_pinpush_predecessor"


@lru_cache(maxsize=100_000)
def _explain_shape_dict_cached(code: str, layers: int) -> dict[str, object] | None:
    return sfa.explain_shape_dict(code, layers)


def is_impossible_rule_closed_complex_diagnostic(diagnostic: dict[str, object]) -> bool:
    return (
        diagnostic.get("kind") == "complex"
        and diagnostic.get("legacy_strict_verdict") == "impossible"
        and bool(diagnostic.get("legacy_reason"))
    )


def is_impossible_rule_closed_shallow_diagnostic(diagnostic: dict[str, object]) -> bool:
    return (
        str(diagnostic.get("kind", "")) in SHALLOW_INPUT_KINDS
        and diagnostic.get("legacy_strict_verdict") == "impossible"
        and bool(diagnostic.get("legacy_reason"))
    )


def is_known_unsupported_complex_diagnostic(diagnostic: dict[str, object]) -> bool:
    if is_impossible_rule_closed_complex_diagnostic(diagnostic):
        return False
    if diagnostic.get("reason") != "no_supported_reverse_candidate":
        return False
    if diagnostic.get("unsupported_class") not in KNOWN_UNSUPPORTED_COMPLEX_CLASSES:
        return False
    probe = diagnostic.get("bounded_forward_probe")
    if isinstance(probe, dict) and _probe_status(probe) in {"reachable", "not_found_truncated"}:
        return False
    return True


@lru_cache(maxsize=4096)
def _best_local_candidate_quality(code: str, max_depth: int = 4) -> dict[str, object] | None:
    normalized = _simplified_or_self(code)
    if not normalized:
        return None
    try:
        shape = Shape.from_string(code)
    except Exception:
        return None
    seen = {normalized}
    candidates: list[ProductionNode] = []
    for builder in (
        _corner_swap_candidates,
        _stack_candidates,
        _swap_candidates,
        _simple_cut_candidates,
        _destroy_cut_candidates,
        _pin_push_candidates,
        _crystal_generator_candidates,
        _rotate_candidates,
    ):
        candidates.extend(builder(shape, normalized, 0, max_depth, seen))
    if not candidates:
        return None
    best = min(candidates, key=_graph_score)
    quality = graph_quality_stats(best)
    return {
        "op": best.op,
        "nodes": int(quality["nodes"]),
        "input_leaves": int(quality["input_leaves"]),
        "complex_input_leaves": int(quality["complex_input_leaves"]),
        "shallow_input_leaves": int(quality["shallow_input_leaves"]),
        "input_leaf_kinds": quality["input_leaf_kinds"],
        "complex_input_shapes": list(quality["complex_input_shapes"]),
        "shallow_input_shapes": list(quality["shallow_input_shapes"]),
    }


def _candidate_improves_leaf(kind: str, candidate_quality: dict[str, object]) -> bool:
    if kind == "complex":
        return int(candidate_quality["complex_input_leaves"]) == 0
    if kind in SHALLOW_INPUT_KINDS:
        return int(candidate_quality["complex_input_leaves"]) == 0 and int(candidate_quality["shallow_input_leaves"]) == 0
    return False


def _validate_node(node: ProductionNode, layers: int) -> str:
    child_shapes = tuple(_validate_node(child, layers) for child in node.children)
    node_simple = _simplified_or_self(node.shape)
    if node.op == "input":
        return node_simple
    if node.op.startswith("terminal_legacy_possible_"):
        legacy, strict, _cls, _reason = sfa.legacy_verdict(node_simple)
        if legacy != "possible" or strict != "possible":
            raise ValueError(f"terminal legacy possible mismatch: legacy={legacy} strict={strict}")
        return node_simple
    if node.op == "corner":
        if node.children:
            raise ValueError("corner needs no children")
        if not _is_supported_corner_primitive(node_simple):
            raise ValueError(f"corner primitive mismatch: {node_simple}")
        return node_simple
    if node.op == "pin_push":
        if len(child_shapes) != 1:
            raise ValueError("pin_push needs one child")
        pushed = sfa.bitmask_push_pin(child_shapes[0], layers)
        if pushed != node_simple:
            raise ValueError(f"pin_push mismatch: {pushed} != {node_simple}")
        return node_simple
    if node.op == "stack":
        if len(node.children) != 2:
            raise ValueError("stack needs two children")
        actual = simplify_shape(repr(Shape.stack(Shape.from_string(node.children[0].shape), Shape.from_string(node.children[1].shape))))
        if actual != node_simple:
            raise ValueError(f"stack mismatch: {actual} != {node_simple}")
        return node_simple
    if node.op == "swap":
        if len(node.children) != 2:
            raise ValueError("swap needs two children")
        out_a, out_b = Shape.swap(Shape.from_string(node.children[0].shape), Shape.from_string(node.children[1].shape))
        actuals = {simplify_shape(repr(out_a)), simplify_shape(repr(out_b))}
        if node_simple not in actuals:
            raise ValueError(f"swap mismatch: {actuals} lacks {node_simple}")
        return node_simple
    if node.op.startswith("rotate_cw "):
        if len(node.children) != 1:
            raise ValueError("rotate needs one child")
        turns = int(node.op.split()[1])
        shape = Shape.from_string(node.children[0].shape)
        for _ in range(turns):
            shape = shape.rotate(True)
        actual = simplify_shape(repr(shape))
        if actual != node_simple:
            raise ValueError(f"rotate mismatch: {actual} != {node_simple}")
        return node_simple
    if node.op == "cut_east":
        if len(node.children) != 1:
            raise ValueError("cut_east needs one child")
        _west, east = Shape.from_string(node.children[0].shape).simple_cutter(False)
        actual = simplify_shape(repr(east))
        if actual != node_simple:
            raise ValueError(f"cut_east mismatch: {actual} != {node_simple}")
        return node_simple
    if node.op.startswith("crystal_generator "):
        if len(node.children) != 1:
            raise ValueError("crystal_generator needs one child")
        color = node.op.split(maxsplit=1)[1]
        actual = simplify_shape(repr(Shape.from_string(node.children[0].shape).crystal_generator(color)))
        if actual != node_simple:
            raise ValueError(f"crystal_generator mismatch: {actual} != {node_simple}")
        return node_simple
    raise ValueError(f"unsupported production op: {node.op}")


def _from_decomposition_tree(
    node: dict[str, Any],
    layers: int,
    max_depth: int,
    seen: set[str],
) -> ProductionNode:
    kind = str(node.get("kind", "node"))
    detail = str(node.get("detail", ""))
    shape = str(node.get("shape", ""))
    children = tuple(node.get("children", ()) or ())

    if kind == "pin_push":
        rendered_children = tuple(_from_decomposition_tree(child, layers, max_depth, seen) for child in children)
        return ProductionNode("pin_push", _detail_or_self(shape), rendered_children, detail)
    if kind == "swap":
        if children:
            rendered_children = tuple(_from_decomposition_tree(child, layers, max_depth, seen) for child in children)
            return ProductionNode("swap", _detail_or_self(shape), rendered_children, detail)
        return _build_shape_graph(shape, depth=0, max_depth=max_depth, seen=seen)
    if kind == "stack":
        rendered_children = tuple(_from_decomposition_tree(child, layers, max_depth, seen) for child in children)
        return ProductionNode("stack", _detail_or_self(shape), rendered_children, detail)
    if kind == "corner":
        return ProductionNode("corner", _detail_or_self(shape), (), detail)
    if kind in {"stack_input", "cut_half_unstable"}:
        return _build_shape_graph(shape, depth=0, max_depth=max_depth, seen=seen)
    if kind == "input":
        return ProductionNode("input", _detail_or_self(shape), (), detail)

    rendered_children = tuple(_from_decomposition_tree(child, layers, max_depth, seen) for child in children)
    return ProductionNode(f"{kind}:{detail}" if detail else kind, _detail_or_self(shape), rendered_children)


def _build_shape_graph(
    code: str,
    depth: int = 0,
    max_depth: int = 5,
    seen: set[str] | None = None,
) -> ProductionNode:
    if seen is None:
        seen = set()
    normalized = _simplified_or_self(code)
    detail = _detail_or_self(code)
    if not normalized:
        return ProductionNode("input")
    if depth >= max_depth or normalized in seen:
        return ProductionNode("input", detail)
    cache_key = (normalized, max_depth - depth)
    if cache_key in _GRAPH_CACHE:
        return _GRAPH_CACHE[cache_key]

    next_seen = set(seen)
    next_seen.add(normalized)
    shape = Shape.from_string(code)

    candidates: list[ProductionNode] = []
    for builder in (
        _corner_swap_candidates,
        _stack_candidates,
        _swap_candidates,
        _simple_cut_candidates,
        _destroy_cut_candidates,
        _crystal_generator_candidates,
        _rotate_candidates,
    ):
        candidates.extend(builder(shape, normalized, depth, max_depth, next_seen))
    if candidates:
        result = min(candidates, key=_graph_score)
        _GRAPH_CACHE[cache_key] = result
        return result
    result = ProductionNode("input", detail)
    _GRAPH_CACHE[cache_key] = result
    return result


def _is_supported_corner_primitive(code: str) -> bool:
    normalized = _simplified_or_self(code)
    if not normalized:
        return False
    try:
        parts = normalized.split(":")
        occupied_columns = {
            quadrant_index
            for layer in parts
            for quadrant_index, quadrant in enumerate(layer)
            if quadrant != "-"
        }
        return (
            len(occupied_columns) == 1
            and sfa.corner_columns_allowed(normalized)
            and sfa.bitmask_physics_stable(normalized)
        )
    except Exception:
        return False


def _corner_swap_candidates(
    shape: Shape,
    normalized: str,
    depth: int,
    max_depth: int,
    seen: set[str],
) -> list[ProductionNode]:
    if depth >= max_depth or "c" not in normalized or "P" in normalized:
        return []
    if not any(ch not in {"-", "c", ":"} for ch in normalized):
        return []
    out: list[ProductionNode] = []
    seen_pairs: set[tuple[str, str]] = set()
    for horizontal, detail in ((False, "corner_swap_12_34"), (True, "corner_swap_14_23")):
        left, right = shape.simple_cutter(horizontal=horizontal)
        left_norm = _simplified_or_self(repr(left))
        right_norm = _simplified_or_self(repr(right))
        if not left_norm or not right_norm:
            continue
        if not _is_supported_corner_primitive(left_norm) or not _is_supported_corner_primitive(right_norm):
            continue
        pair_key = (left_norm, right_norm)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        out_a, out_b = Shape.swap(Shape.from_string(left_norm), Shape.from_string(right_norm))
        if normalized not in {_simplified_or_self(repr(out_a)), _simplified_or_self(repr(out_b))}:
            continue
        out.append(
            ProductionNode(
                "swap",
                _detail_or_self(normalized),
                (
                    ProductionNode("corner", _detail_or_self(left_norm), (), detail + "_left"),
                    ProductionNode("corner", _detail_or_self(right_norm), (), detail + "_right"),
                ),
                detail,
            )
        )
    return out


def _graph_score(node: ProductionNode) -> tuple[int, int, int, int, int, str]:
    quality = graph_quality_stats(node)
    ops = dict(quality["ops"])
    useful_ops = sum(
        int(count)
        for op, count in ops.items()
        if op in {"stack", "swap", "cut_east"} or op.startswith("crystal_generator ")
        or op in {"pin_push", "corner"}
    )
    return (
        int(quality["complex_input_leaves"]),
        int(quality["shallow_input_leaves"]),
        int(quality["input_leaves"]),
        int(quality["nodes"]),
        -useful_ops,
        node.op,
    )


def _shallow_progress_score(node: ProductionNode) -> tuple[int, int, tuple[int, int], int, int, int, str]:
    quality = graph_quality_stats(node)
    ops = dict(quality["ops"])
    useful_ops = sum(
        int(count)
        for op, count in ops.items()
        if op in {"stack", "swap", "cut_east"} or op.startswith("crystal_generator ") or op in {"pin_push", "corner"}
    )
    return (
        int(quality["complex_input_leaves"]),
        int(quality["shallow_input_leaves"]),
        _max_shallow_leaf_size(node),
        int(quality["input_leaves"]),
        int(quality["nodes"]),
        -useful_ops,
        node.op,
    )


def _max_shallow_leaf_size(node: ProductionNode) -> tuple[int, int]:
    sizes: list[tuple[int, int]] = []

    def walk(current: ProductionNode) -> None:
        if current.op == "input":
            if _input_leaf_kind(current.shape) in SHALLOW_INPUT_KINDS:
                try:
                    sizes.append(_shape_size(Shape.from_string(current.shape)))
                except Exception:
                    sizes.append((9999, 9999))
            return
        for child in current.children:
            walk(child)

    walk(node)
    return max(sizes) if sizes else (0, 0)


def _shape_size(shape: Shape) -> tuple[int, int]:
    occupied = sum(1 for layer in shape.layers for quadrant in layer.quadrants if quadrant is not None)
    return (len(shape.layers), occupied)


def _stack_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    out: list[ProductionNode] = []
    out.extend(_direct_stack_split_candidates(shape, normalized, depth, max_depth, seen))
    for _op, pair in ReverseTracer.inverse_stack(shape, 1):
        bottom, top = pair
        if _simplified_or_self(repr(Shape.stack(bottom, top))) != normalized:
            continue
        out.append(
            ProductionNode(
                "stack",
                _detail_or_self(normalized),
                (
                    _build_shape_graph(repr(bottom), depth + 1, max_depth, seen),
                    _build_shape_graph(repr(top), depth + 1, max_depth, seen),
                ),
            )
        )
        if len(out) >= 4:
            break
    return out


def _direct_stack_split_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    out: list[ProductionNode] = []
    if len(shape.layers) < 2:
        return out
    for split in range(1, len(shape.layers)):
        bottom = Shape(shape.layers[:split])
        top = Shape(shape.layers[split:])
        bottom.max_layers = shape.max_layers
        top.max_layers = shape.max_layers
        if any(q and q.shape == "c" for layer in top.layers for q in layer.quadrants):
            continue
        if _simplified_or_self(repr(Shape.stack(bottom, top))) != normalized:
            continue
        bottom_norm = _simplified_or_self(repr(bottom))
        top_norm = _simplified_or_self(repr(top))
        if bottom_norm == normalized or top_norm == normalized:
            continue
        out.append(
            ProductionNode(
                "stack",
                _detail_or_self(normalized),
                (
                    _build_shape_graph(repr(bottom), depth + 1, max_depth, seen),
                    _build_shape_graph(repr(top), depth + 1, max_depth, seen),
                ),
                "direct_split",
            )
        )
        if len(out) >= 4:
            break
    return out


def _swap_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    out: list[ProductionNode] = []
    seen_pairs: set[tuple[str, str]] = set()
    for _op, pair in ReverseTracer.inverse_swap(shape, 0, 1):
        left, right = pair
        if not repr(left) or not repr(right):
            continue
        pair_key = (repr(left), repr(right))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        out_a, out_b = Shape.swap(left, right)
        if _simplified_or_self(repr(out_a)) != normalized and _simplified_or_self(repr(out_b)) != normalized:
            continue
        out.append(
            ProductionNode(
                "swap",
                _detail_or_self(normalized),
                (
                    _build_shape_graph(repr(left), depth + 1, max_depth, seen),
                    _build_shape_graph(repr(right), depth + 1, max_depth, seen),
                ),
            )
        )
        if len(out) >= 4:
            break
    return out


def _simple_cut_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    out: list[ProductionNode] = []
    for turns in range(4):
        cut_source = shape.copy()
        for _ in range(turns):
            cut_source = cut_source.rotate(False)
        _west, east = cut_source.simple_cutter(False)
        if _simplified_or_self(repr(east)) != _simplified_or_self(repr(cut_source)):
            continue
        restored = east.copy()
        for _ in range(turns):
            restored = restored.rotate(True)
        if _simplified_or_self(repr(restored)) != normalized:
            continue

        cut_source_norm = _simplified_or_self(repr(cut_source))
        source_options = []
        mirrored = _mirrored_west_cut_source(cut_source)
        if _simplified_or_self(repr(mirrored)) != cut_source_norm:
            source_options.append(mirrored)
        for source_candidate in source_options:
            _west_check, east_check = source_candidate.simple_cutter(False)
            if _simplified_or_self(repr(east_check)) != cut_source_norm:
                continue
            source_norm = _simplified_or_self(repr(source_candidate))
            if source_norm != cut_source_norm and source_norm not in seen:
                child = _build_shape_graph(repr(source_candidate), depth + 1, max_depth, seen)
            else:
                child = ProductionNode("input", _detail_or_self(repr(source_candidate)))
            cut_node = ProductionNode("cut_east", _detail_or_self(repr(cut_source)), (child,))
            out.append(
                ProductionNode(f"rotate_cw {turns}", _detail_or_self(normalized), (cut_node,))
                if turns
                else cut_node
            )
            if len(out) >= 4:
                return out
    return out


def _destroy_cut_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    out: list[ProductionNode] = []
    for turns in range(4):
        rotated_target = shape.copy()
        for _ in range(turns):
            rotated_target = rotated_target.rotate(False)
        for _op, origin in ReverseTracer.inverse_destroy_half(rotated_target, turns, 1):
            candidate = origin.copy()
            for _ in range(turns):
                candidate = candidate.rotate(True)
            if _simplified_or_self(repr(candidate.destroy_half())) != normalized:
                continue
            child = _build_shape_graph(repr(candidate), depth + 1, max_depth, seen)
            out.append(
                ProductionNode(f"rotate_cw {turns}", _detail_or_self(normalized), (child,))
                if turns
                else ProductionNode("cut_east", _detail_or_self(normalized), (child,))
            )
            if len(out) >= 4:
                return out
    return out


def _crystal_generator_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    out: list[ProductionNode] = []
    seen_sources: set[str] = set()
    for _op, origin in ReverseTracer.inverse_crystal_generator(shape, 1):
        source_norm = _simplified_or_self(repr(origin))
        if not source_norm or source_norm in seen_sources:
            continue
        seen_sources.add(source_norm)
        color = _crystal_generator_color(origin, shape, normalized)
        if color is None:
            continue
        child = _build_shape_graph(repr(origin), depth + 1, max_depth, seen)
        out.append(ProductionNode(f"crystal_generator {color}", _detail_or_self(normalized), (child,)))
        if len(out) >= 4:
            break
    return out


def _pin_push_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    layers = max(6, len(shape.layers))
    out: list[ProductionNode] = []
    seen_predecessors: set[str] = set()
    for predecessor in (
        sfa.bitmask_inverse_push_pin_candidates(normalized, layers)
        + sfa.bitmask_bridge_inverse_push_pin_candidates(normalized, layers)
    ):
        predecessor_norm = _simplified_or_self(predecessor)
        if (
            not predecessor_norm
            or predecessor_norm == normalized
            or predecessor_norm in seen
            or predecessor_norm in seen_predecessors
        ):
            continue
        seen_predecessors.add(predecessor_norm)
        if sfa.bitmask_push_pin(predecessor_norm, layers) != normalized:
            continue
        out.append(
            ProductionNode(
                "pin_push",
                _detail_or_self(normalized),
                (_build_shape_graph(predecessor_norm, depth + 1, max_depth, seen),),
                "inverse_predecessor",
            )
        )
        if len(out) >= 2:
            break
    return out


def _refine_shallow_pin_push_leaves(
    node: ProductionNode | None,
    layers: int,
    remaining_depth: int,
    seen: set[str] | None = None,
) -> ProductionNode | None:
    if node is None:
        return None
    if remaining_depth <= 0:
        return node
    if seen is None:
        seen = set()
    if node.op == "input":
        normalized = _simplified_or_self(node.shape)
        if _input_leaf_kind(normalized) not in SHALLOW_INPUT_KINDS or normalized in seen:
            return node
        refined = _shallow_pin_push_leaf_refinement(node, layers, remaining_depth, seen)
        if refined is not None:
            return refined
        terminal = _legacy_possible_terminal_node(node, layers)
        return terminal or node
    refined_children = tuple(
        _refine_shallow_pin_push_leaves(child, layers, remaining_depth, seen) or child
        for child in node.children
    )
    if refined_children == node.children:
        return node
    return ProductionNode(node.op, node.shape, refined_children, node.note)


def _shallow_pin_push_leaf_refinement(
    node: ProductionNode,
    layers: int,
    remaining_depth: int,
    seen: set[str],
) -> ProductionNode | None:
    normalized = _simplified_or_self(node.shape)
    try:
        source_shape = Shape.from_string(node.shape)
    except Exception:
        return None
    source_size = _shape_size(source_shape)
    candidates: list[ProductionNode] = []
    for predecessor in (
        sfa.bitmask_inverse_push_pin_candidates(normalized, layers)
        + sfa.bitmask_bridge_inverse_push_pin_candidates(normalized, layers)
    ):
        predecessor_norm = _simplified_or_self(predecessor)
        if not predecessor_norm or predecessor_norm == normalized or predecessor_norm in seen:
            continue
        try:
            predecessor_size = _shape_size(Shape.from_string(predecessor_norm))
        except Exception:
            continue
        if predecessor_size >= source_size:
            continue
        if sfa.bitmask_push_pin(predecessor_norm, layers) != normalized:
            continue
        child_seen = set(seen)
        child_seen.add(normalized)
        child = _build_shape_graph(predecessor_norm, max_depth=max(1, remaining_depth - 1), seen=child_seen)
        child = _refine_shallow_pin_push_leaves(child, layers, remaining_depth - 1, child_seen) or child
        candidate = ProductionNode("pin_push", _detail_or_self(normalized), (child,), "shallow_leaf_refinement")
        quality = graph_quality_stats(candidate)
        if int(quality["complex_input_leaves"]):
            continue
        candidates.append(candidate)
    if not candidates:
        return None
    return min(candidates, key=_shallow_progress_score)


def _legacy_possible_terminal_node(node: ProductionNode, layers: int) -> ProductionNode | None:
    try:
        shape = Shape.from_string(node.shape)
    except Exception:
        return None
    hint = _shallow_terminal_hint(node.shape, shape)
    if not hint:
        return None
    closed_decomposition = _closed_symbolic_decomposition_node(node.shape, layers)
    if closed_decomposition is not None:
        return closed_decomposition
    suffix = hint.removeprefix("legacy_possible_").removesuffix("_terminal_no_pinpush_predecessor")
    if suffix not in {"swap_limited", "swappable"}:
        return None
    return ProductionNode(f"terminal_legacy_possible_{suffix}", node.shape, (), hint)


def _closed_symbolic_decomposition_node(code: str, layers: int) -> ProductionNode | None:
    if not _could_have_closed_symbolic_decomposition(code):
        return None
    try:
        explanation = _explain_shape_dict_cached(_simplified_or_self(code), layers)
    except Exception:
        return None
    tree = explanation.get("decomposition_tree") if isinstance(explanation, dict) else None
    if not isinstance(tree, dict):
        return None
    if _decomposition_open_leaf_keys_from_dict(tree):
        return None
    if _decomposition_unexpanded_leaf_keys_from_dict(tree):
        return None
    try:
        return _from_decomposition_tree(tree, layers, max_depth=3, seen={_simplified_or_self(code)})
    except Exception:
        return None


def _could_have_closed_symbolic_decomposition(code: str) -> bool:
    normalized = _simplified_or_self(code)
    return bool(normalized and "c" in normalized and "P" not in normalized)


def _crystal_generator_color(origin: Shape, target: Shape, target_normalized: str) -> str | None:
    target_detail = repr(target)
    for color in (color for color in Quadrant.VALID_COLORS if color != "u"):
        generated = origin.crystal_generator(color)
        if repr(generated) == target_detail or _simplified_or_self(repr(generated)) == target_normalized:
            return color
    return None


def _rotate_candidates(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> list[ProductionNode]:
    out: list[ProductionNode] = []
    for turns in (1, 2, 3):
        source = shape.copy()
        for _ in range(turns):
            source = source.rotate(False)
        restored = source.copy()
        for _ in range(turns):
            restored = restored.rotate(True)
        if _simplified_or_self(repr(restored)) != normalized:
            continue
        source_norm = _simplified_or_self(repr(source))
        if source_norm in seen:
            continue
        child = _build_shape_graph(repr(source), depth + 1, max_depth, seen)
        if child.op != "input":
            out.append(ProductionNode(f"rotate_cw {turns}", _detail_or_self(normalized), (child,)))
    return out


def _try_stack(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> ProductionNode | None:
    direct = _try_direct_stack_split(shape, normalized, depth, max_depth, seen)
    if direct is not None:
        return direct
    for _op, pair in ReverseTracer.inverse_stack(shape, 1):
        bottom, top = pair
        if _simplified_or_self(repr(Shape.stack(bottom, top))) != normalized:
            continue
        return ProductionNode(
            "stack",
            _detail_or_self(normalized),
            (
                _build_shape_graph(repr(bottom), depth + 1, max_depth, seen),
                _build_shape_graph(repr(top), depth + 1, max_depth, seen),
            ),
        )
    return None


def _try_direct_stack_split(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> ProductionNode | None:
    if len(shape.layers) < 2:
        return None
    for split in range(1, len(shape.layers)):
        bottom = Shape(shape.layers[:split])
        top = Shape(shape.layers[split:])
        bottom.max_layers = shape.max_layers
        top.max_layers = shape.max_layers
        if any(q and q.shape == "c" for layer in top.layers for q in layer.quadrants):
            continue
        if _simplified_or_self(repr(Shape.stack(bottom, top))) != normalized:
            continue
        bottom_norm = _simplified_or_self(repr(bottom))
        top_norm = _simplified_or_self(repr(top))
        if bottom_norm == normalized or top_norm == normalized:
            continue
        return ProductionNode(
            "stack",
            _detail_or_self(normalized),
            (
                _build_shape_graph(repr(bottom), depth + 1, max_depth, seen),
                _build_shape_graph(repr(top), depth + 1, max_depth, seen),
            ),
            "direct_split",
        )
    return None


def _try_swap(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> ProductionNode | None:
    for _op, pair in ReverseTracer.inverse_swap(shape, 0, 1):
        left, right = pair
        if not repr(left) or not repr(right):
            continue
        out_a, out_b = Shape.swap(left, right)
        if _simplified_or_self(repr(out_a)) != normalized and _simplified_or_self(repr(out_b)) != normalized:
            continue
        return ProductionNode(
            "swap",
            _detail_or_self(normalized),
            (
                _build_shape_graph(repr(left), depth + 1, max_depth, seen),
                _build_shape_graph(repr(right), depth + 1, max_depth, seen),
            ),
        )
    return None


def _try_simple_cut(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> ProductionNode | None:
    for turns in range(4):
        cut_source = shape.copy()
        for _ in range(turns):
            cut_source = cut_source.rotate(False)
        _west, east = cut_source.simple_cutter(False)
        if _simplified_or_self(repr(east)) != _simplified_or_self(repr(cut_source)):
            continue
        restored = east.copy()
        for _ in range(turns):
            restored = restored.rotate(True)
        if _simplified_or_self(repr(restored)) != normalized:
            continue
        source_candidate = _mirrored_west_cut_source(cut_source)
        _west_check, east_check = source_candidate.simple_cutter(False)
        cut_source_norm = _simplified_or_self(repr(cut_source))
        if (
            _simplified_or_self(repr(east_check)) != cut_source_norm
            or _simplified_or_self(repr(source_candidate)) == cut_source_norm
        ):
            continue
        source_norm = _simplified_or_self(repr(source_candidate))
        if source_norm != cut_source_norm and source_norm not in seen:
            child = _build_shape_graph(repr(source_candidate), depth + 1, max_depth, seen)
        else:
            child = ProductionNode("input", _detail_or_self(repr(source_candidate)))
        cut_node = ProductionNode("cut_east", _detail_or_self(repr(cut_source)), (child,))
        if turns:
            return ProductionNode(f"rotate_cw {turns}", _detail_or_self(normalized), (cut_node,))
        return cut_node
    return None


def _mirrored_west_cut_source(east_shape: Shape) -> Shape:
    source = east_shape.copy()
    for layer in source.layers:
        if layer.quadrants[0] is not None and layer.quadrants[3] is None:
            layer.quadrants[3] = layer.quadrants[0].copy()
        if layer.quadrants[1] is not None and layer.quadrants[2] is None:
            layer.quadrants[2] = layer.quadrants[1].copy()
    return source


def _try_destroy_cut(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> ProductionNode | None:
    for turns in range(4):
        rotated_target = shape.copy()
        for _ in range(turns):
            rotated_target = rotated_target.rotate(False)
        for _op, origin in ReverseTracer.inverse_destroy_half(rotated_target, turns, 1):
            candidate = origin.copy()
            for _ in range(turns):
                candidate = candidate.rotate(True)
            if _simplified_or_self(repr(candidate.destroy_half())) != normalized:
                continue
            child = _build_shape_graph(repr(candidate), depth + 1, max_depth, seen)
            if turns:
                return ProductionNode(f"rotate_cw {turns}", _detail_or_self(normalized), (child,))
            return ProductionNode("cut_east", _detail_or_self(normalized), (child,))
    return None


def _try_rotate(shape: Shape, normalized: str, depth: int, max_depth: int, seen: set[str]) -> ProductionNode | None:
    for turns in (1, 2, 3):
        source = shape.copy()
        for _ in range(turns):
            source = source.rotate(False)
        restored = source.copy()
        for _ in range(turns):
            restored = restored.rotate(True)
        if _simplified_or_self(repr(restored)) != normalized:
            continue
        source_norm = _simplified_or_self(repr(source))
        if source_norm in seen:
            continue
        child = _build_shape_graph(repr(source), depth + 1, max_depth, seen)
        if child.op != "input":
            return ProductionNode(f"rotate_cw {turns}", _detail_or_self(normalized), (child,))
    return None


def _simplified_or_self(code: str) -> str:
    try:
        return simplify_shape(repr(Shape.from_string(code)))
    except Exception:
        pass
    try:
        return simplify_shape(code)
    except Exception:
        return code


def _detail_or_self(code: str) -> str:
    try:
        return repr(Shape.from_string(code))
    except Exception:
        return str(code)
