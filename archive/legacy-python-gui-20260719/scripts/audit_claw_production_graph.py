from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from itertools import product
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from claw_production_graph import (
    assess_production_graph,
    build_claw_pinpush_graph,
    build_shape_production_graph,
    diagnose_terminal_leaves,
    input_leaf_examples,
    diagnose_shallow_inputs,
    is_impossible_rule_closed_complex_diagnostic,
    is_impossible_rule_closed_shallow_diagnostic,
    is_known_unsupported_complex_diagnostic,
    is_known_structural_shallow_diagnostic,
    render_graph,
)
import claw_production_graph as production_graph
from data_operations import simplify_shape
from shape import Shape
import symbolic_frontier_automaton as sfa


def audit(args: argparse.Namespace) -> int:
    loaded_samples = (
        _load_pair_samples(args)
        if args.pairs_file
        else _load_shape_samples(args.shapes_file)
        if getattr(args, "shapes_file", None)
        else _random_shape_samples(args)
    )
    verdict_cache: dict[str, tuple[bool, str]] = {}
    filtered_samples = _filter_samples(args, loaded_samples, verdict_cache)
    samples = _dedupe_samples(filtered_samples) if getattr(args, "dedupe_samples", False) else filtered_samples
    if args.pairs_file and args.samples:
        samples = samples[: args.samples]
    if args.write_filtered_pairs:
        args.write_filtered_pairs.parent.mkdir(parents=True, exist_ok=True)
        args.write_filtered_pairs.write_text(
            "\n".join(f"{target}\t{predecessor}" for target, predecessor in filtered_samples) + "\n",
            encoding="utf-8",
        )
        print(f"filtered_pairs_written={args.write_filtered_pairs}")
        print(f"filtered_pairs_written_count={len(filtered_samples)}")

    failures: list[tuple[str, str, list[str]]] = []
    complex_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    totals = {
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
        "resolved_graphs": 0,
        "unresolved_graphs": 0,
        "structural_resolved_graphs": 0,
        "structural_unresolved_graphs": 0,
        "strict_resolved_graphs": 0,
        "strict_unresolved_graphs": 0,
    }
    op_counts: dict[str, int] = {}
    verdict_counts: Counter[str] = Counter()
    verdict_resolution_counts: Counter[str] = Counter()
    verdict_structural_resolution_counts: Counter[str] = Counter()
    verdict_strict_resolution_counts: Counter[str] = Counter()
    strict_gap_resolution_counts: Counter[str] = Counter()
    verdict_strict_gap_resolution_counts: Counter[str] = Counter()
    diagnostic_reason_counts: Counter[str] = Counter()
    unsupported_class_counts: Counter[str] = Counter()
    complex_resolution_counts: Counter[str] = Counter()
    impossible_rule_closed_reason_counts: Counter[str] = Counter()
    complex_leaf_depth_counts: Counter[str] = Counter()
    complex_best_candidate_op_counts: Counter[str] = Counter()
    complex_candidate_preserves_leaf_counts: Counter[str] = Counter()
    bounded_forward_probe_counts: Counter[str] = Counter()
    bounded_forward_probe_op_counts: Counter[str] = Counter()
    bounded_forward_probe_pruned_counts: Counter[str] = Counter()
    shallow_diagnostic_reason_counts: Counter[str] = Counter()
    shallow_class_counts: Counter[str] = Counter()
    shallow_terminal_hint_counts: Counter[str] = Counter()
    shallow_probe_counts: Counter[str] = Counter()
    shallow_resolution_counts: Counter[str] = Counter()
    shallow_impossible_rule_closed_reason_counts: Counter[str] = Counter()
    shallow_feature_signature_counts: Counter[str] = Counter()
    shallow_feature_signature_shapes: dict[str, set[str]] = {}
    shallow_leaf_depth_counts: Counter[str] = Counter()
    shallow_best_candidate_op_counts: Counter[str] = Counter()
    shallow_candidate_preserves_leaf_counts: Counter[str] = Counter()
    terminal_op_counts: Counter[str] = Counter()
    terminal_explain_reason_counts: Counter[str] = Counter()
    terminal_open_leaf_key_counts: Counter[str] = Counter()
    terminal_self_open_leaf_key_counts: Counter[str] = Counter()
    terminal_unexpanded_leaf_key_counts: Counter[str] = Counter()
    terminal_self_unexpanded_leaf_key_counts: Counter[str] = Counter()
    terminal_cycle_category_counts: Counter[str] = Counter()
    terminal_resolution_counts: Counter[str] = Counter()
    terminal_shape_counts: Counter[str] = Counter()
    terminal_feature_signature_counts: Counter[str] = Counter()
    terminal_feature_signature_shapes: dict[str, set[str]] = {}
    terminal_probe_counts: Counter[str] = Counter()
    terminal_probe_op_counts: Counter[str] = Counter()
    terminal_probe_pruned_counts: Counter[str] = Counter()
    terminal_probe_shape_keys: set[str] = set()
    terminal_self_open_leaf_cases = 0
    terminal_self_unexpanded_leaf_cases = 0
    reachable_terminal_probe_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    truncated_terminal_probe_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    terminal_probe_cache: dict[tuple[str, int, int, int], dict[str, object]] = {}
    input_leaf_kind_counts: Counter[str] = Counter()
    input_leaf_kind_examples: dict[str, list[str]] = {}
    unresolved_possible_cases: list[tuple[str, str, list[dict[str, object]], list[str]]] = []
    structural_unresolved_possible_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    strict_unresolved_possible_cases: list[tuple[str, str, dict[str, object], list[str]]] = []
    terminal_boundary_cases: list[tuple[str, dict[str, object], list[str]]] = []
    known_terminal_boundary_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    actionable_terminal_boundary_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    unprobed_terminal_boundary_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    shallow_possible_cases: list[tuple[str, dict[str, object], dict[str, list[str]], list[dict[str, object]], list[str]]] = []
    actionable_shallow_possible_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    unknown_shallow_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    shallow_low_depth_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    actionable_complex_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    unknown_complex_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    truncated_probe_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    truncated_shallow_probe_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    reachable_shallow_probe_cases: list[tuple[str, dict[str, object], list[dict[str, object]], list[str]]] = []
    unsupported_leaf_rows: list[dict[str, object]] = []
    shallow_leaf_rows: list[dict[str, object]] = []
    low_depth_shallow_leaf_rows: list[dict[str, object]] = []
    terminal_boundary_rows: list[dict[str, object]] = []
    low_depth_shallow_leaves = 0
    shallow_possible_leaves = 0
    actionable_shallow_possible_leaves = 0
    actionable_complex_leaves = 0
    low_depth_shallow_threshold = _low_depth_shallow_threshold(args)

    for sample in samples:
        code, predecessor = sample
        shallow_depth_floor = getattr(args, "fail_on_shallow_depth_below", None)
        complex_probe_max_steps = _int_arg(args, "complex_probe_max_steps", args.probe_max_steps)
        complex_probe_max_states = _int_arg(args, "complex_probe_max_states", args.probe_max_states)
        complex_probe_pair_limit = _int_arg(args, "complex_probe_pair_limit", args.probe_pair_limit)
        terminal_probe_pair_limit = _int_arg(args, "terminal_probe_pair_limit", args.probe_pair_limit)
        probe_shallow = (
            bool(getattr(args, "probe_shallow_leaves", False))
            or bool(getattr(args, "fail_on_reachable_shallow_probe", False))
            or bool(getattr(args, "fail_on_actionable_shallow_possible", False))
            or bool(getattr(args, "fail_on_unknown_shallow_class", False))
        )
        probe_terminal = (
            bool(getattr(args, "probe_terminal_boundaries", False))
            or bool(getattr(args, "fail_on_reachable_terminal_probe", False))
            or bool(getattr(args, "fail_on_truncated_terminal_probe", False))
        )
        shallow_probe_pair_limit = _int_arg(args, "shallow_probe_pair_limit", args.probe_pair_limit)
        graph = (
            build_claw_pinpush_graph(code, predecessor, args.validate_layers, max_depth=args.max_depth)
            if predecessor
            else build_shape_production_graph(code, max_depth=args.max_depth)
        )
        assessment = assess_production_graph(
            graph,
            args.validate_layers,
            probe_max_steps=complex_probe_max_steps,
            probe_max_states=complex_probe_max_states,
            probe_pair_limit=complex_probe_pair_limit,
        )
        valid = assessment["valid"]
        assert isinstance(valid, tuple)
        reason = str(valid[1])
        rendered = render_graph(graph)
        quality = assessment["quality"]
        assert isinstance(quality, dict)
        diagnostics = assessment["diagnostics"]
        assert isinstance(diagnostics, list)
        resolved = bool(assessment["resolved"])
        strict_resolved = bool(assessment["strict_resolved"])
        leaf_examples = input_leaf_examples(graph, args.max_leaf_examples)
        terminal_diagnostics = diagnose_terminal_leaves(graph)
        if probe_terminal:
            for diagnostic in terminal_diagnostics:
                _attach_terminal_probe(
                    diagnostic,
                    cache=terminal_probe_cache,
                    max_steps=args.probe_max_steps,
                    max_states=args.probe_max_states,
                    pair_limit=terminal_probe_pair_limit,
                )
        if probe_shallow:
            shallow_diagnostics = diagnose_shallow_inputs(
                graph,
                include_probe=True,
                probe_max_steps=args.probe_max_steps,
                probe_max_states=args.probe_max_states,
                probe_pair_limit=shallow_probe_pair_limit,
            )
        else:
            shallow_diagnostics = assessment["shallow_diagnostics"]
            assert isinstance(shallow_diagnostics, list)
        unknown_shallow_diagnostics = [
            diagnostic
            for diagnostic in shallow_diagnostics
            if _shallow_resolution(diagnostic) == "unknown_or_actionable"
        ]
        structural_resolved = (
            bool(graph)
            and bool(valid[0])
            and not int(quality["complex_input_leaves"])
            and not unknown_shallow_diagnostics
        )
        strict_gap_resolution = _strict_gap_resolution(
            strict_resolved,
            quality,
            diagnostics,
            shallow_diagnostics,
            terminal_diagnostics,
        )
        strict_gap_resolution_counts[strict_gap_resolution] += 1
        totals["resolved_graphs" if resolved else "unresolved_graphs"] += 1
        totals["structural_resolved_graphs" if structural_resolved else "structural_unresolved_graphs"] += 1
        totals["strict_resolved_graphs" if strict_resolved else "strict_unresolved_graphs"] += 1
        if predecessor:
            verdict_key = _target_verdict_key(code, verdict_cache)
            verdict_counts[verdict_key] += 1
            verdict_resolution_counts[f"{verdict_key}|{'resolved' if resolved else 'unresolved'}"] += 1
            verdict_structural_resolution_counts[
                f"{verdict_key}|{'structural_resolved' if structural_resolved else 'structural_unresolved'}"
            ] += 1
            verdict_strict_resolution_counts[
                f"{verdict_key}|{'strict_resolved' if strict_resolved else 'strict_unresolved'}"
            ] += 1
            verdict_strict_gap_resolution_counts[f"{verdict_key}|{strict_gap_resolution}"] += 1
            if verdict_key.startswith("claw_possible:") and not resolved:
                unresolved_possible_cases.append((
                    _sample_label(code, predecessor),
                    reason if not valid else "complex_input",
                    diagnostics,
                    rendered[: args.graph_lines],
                ))
            if verdict_key.startswith("claw_possible:") and not structural_resolved:
                structural_unresolved_possible_cases.append((
                    _sample_label(code, predecessor),
                    quality,
                    list(assessment.get("unknown_shallow_diagnostics", [])),
                    rendered[: args.graph_lines],
                ))
            if verdict_key.startswith("claw_possible:") and not strict_resolved:
                strict_unresolved_possible_cases.append((
                    _sample_label(code, predecessor),
                    _strict_unresolved_reason(quality),
                    quality,
                    rendered[: args.graph_lines],
                ))
            if verdict_key.startswith("claw_possible:") and int(quality.get("terminal_leaves", 0)):
                terminal_boundary_cases.append((
                    _sample_label(code, predecessor),
                    quality,
                    rendered[: args.graph_lines],
                ))
                for diagnostic in terminal_diagnostics:
                    terminal_shape = str(diagnostic.get("shape", ""))
                    terminal_signature = _terminal_feature_signature(diagnostic)
                    terminal_shape_counts[terminal_shape] += 1
                    terminal_feature_signature_counts[terminal_signature] += 1
                    terminal_feature_signature_shapes.setdefault(terminal_signature, set()).add(terminal_shape)
                    terminal_cycle_category_counts[_terminal_cycle_category(diagnostic)] += 1
                    terminal_resolution_counts[_terminal_resolution(diagnostic)] += 1
                    terminal_op_counts[str(diagnostic.get("op", ""))] += 1
                    terminal_explain_reason_counts[str(diagnostic.get("explain_reason", ""))] += 1
                    terminal_open_leaf_key_counts[_terminal_open_leaf_key(diagnostic)] += 1
                    self_open_leaf_count = int(diagnostic.get("self_open_leaf_count", 0))
                    if self_open_leaf_count:
                        terminal_self_open_leaf_cases += 1
                        terminal_self_open_leaf_key_counts[_terminal_self_open_leaf_key(diagnostic)] += 1
                    unexpanded_leaf_key = _terminal_unexpanded_leaf_key(diagnostic)
                    if unexpanded_leaf_key != "{}":
                        terminal_unexpanded_leaf_key_counts[unexpanded_leaf_key] += 1
                    self_unexpanded_leaf_count = int(diagnostic.get("self_unexpanded_leaf_count", 0))
                    if self_unexpanded_leaf_count:
                        terminal_self_unexpanded_leaf_cases += 1
                        terminal_self_unexpanded_leaf_key_counts[
                            _terminal_self_unexpanded_leaf_key(diagnostic)
                        ] += 1
                    terminal_probe = diagnostic.get("bounded_forward_probe")
                    if isinstance(terminal_probe, dict):
                        probe_key = _probe_key(terminal_probe)
                        terminal_probe_counts[probe_key] += 1
                        terminal_probe_shape_keys.add(terminal_shape)
                        for op, count in dict(terminal_probe.get("op_counts", {})).items():
                            terminal_probe_op_counts[str(op)] += int(count)
                        for op, count in dict(terminal_probe.get("pruned_counts", {})).items():
                            terminal_probe_pruned_counts[str(op)] += int(count)
                if probe_terminal:
                    reachable_terminal_diagnostics = [
                        diagnostic
                        for diagnostic in terminal_diagnostics
                        if isinstance(diagnostic.get("bounded_forward_probe"), dict)
                        and _probe_key(diagnostic["bounded_forward_probe"]) == "reachable"
                    ]
                    truncated_terminal_diagnostics = [
                        diagnostic
                        for diagnostic in terminal_diagnostics
                        if isinstance(diagnostic.get("bounded_forward_probe"), dict)
                        and _probe_key(diagnostic["bounded_forward_probe"]) == "not_found_truncated"
                    ]
                    if reachable_terminal_diagnostics:
                        reachable_terminal_probe_cases.append((
                            _sample_label(code, predecessor),
                            quality,
                            reachable_terminal_diagnostics[: args.max_leaf_examples],
                            rendered[: args.graph_lines],
                        ))
                    if truncated_terminal_diagnostics:
                        truncated_terminal_probe_cases.append((
                            _sample_label(code, predecessor),
                            quality,
                            truncated_terminal_diagnostics[: args.max_leaf_examples],
                            rendered[: args.graph_lines],
                        ))
                terminal_boundary_resolution = _terminal_boundary_resolution(terminal_diagnostics)
                if terminal_boundary_resolution == "known_closed":
                    known_terminal_boundary_cases.append((
                        _sample_label(code, predecessor),
                        quality,
                        terminal_diagnostics[: args.max_leaf_examples],
                        rendered[: args.graph_lines],
                    ))
                elif terminal_boundary_resolution == "actionable":
                    actionable_terminal_boundary_cases.append((
                        _sample_label(code, predecessor),
                        quality,
                        terminal_diagnostics[: args.max_leaf_examples],
                        rendered[: args.graph_lines],
                    ))
                else:
                    unprobed_terminal_boundary_cases.append((
                        _sample_label(code, predecessor),
                        quality,
                        terminal_diagnostics[: args.max_leaf_examples],
                        rendered[: args.graph_lines],
                    ))
                terminal_boundary_rows.extend(
                    _terminal_leaf_row(code, predecessor, diagnostic) for diagnostic in terminal_diagnostics
                )
            if verdict_key.startswith("claw_possible:") and int(quality["shallow_input_leaves"]):
                actionable_shallow_diagnostics = _actionable_shallow_diagnostics(shallow_diagnostics)
                shallow_possible_leaves += int(quality["shallow_input_leaves"])
                shallow_possible_cases.append((
                    _sample_label(code, predecessor),
                    quality,
                    {
                        kind: examples
                        for kind, examples in leaf_examples.items()
                        if kind not in {"empty", "single_cell", "complex"}
                    },
                    shallow_diagnostics[: args.max_leaf_examples],
                    rendered[: args.graph_lines],
                ))
                if actionable_shallow_diagnostics:
                    actionable_shallow_possible_leaves += len(actionable_shallow_diagnostics)
                    actionable_shallow_possible_cases.append((
                        _sample_label(code, predecessor),
                        quality,
                        actionable_shallow_diagnostics[: args.max_leaf_examples],
                        rendered[: args.graph_lines],
                    ))
        if diagnostics:
            for diagnostic in diagnostics:
                diagnostic_reason_counts[str(diagnostic.get("reason", "diagnostic_error"))] += 1
                complex_leaf_depth_counts[_leaf_depth_key(diagnostic)] += 1
                _record_candidate_summary(
                    diagnostic,
                    complex_best_candidate_op_counts,
                    complex_candidate_preserves_leaf_counts,
                )
                unsupported_class = diagnostic.get("unsupported_class")
                if unsupported_class:
                    unsupported_class_counts[str(unsupported_class)] += 1
                    unsupported_leaf_rows.append(_unsupported_leaf_row(code, predecessor, diagnostic))
                complex_resolution = _complex_resolution(diagnostic)
                complex_resolution_counts[complex_resolution] += 1
                if complex_resolution == "impossible_rule_closed":
                    impossible_rule_closed_reason_counts[str(diagnostic.get("legacy_reason", "unknown"))] += 1
                if complex_resolution not in {"known_unsupported", "impossible_rule_closed"}:
                    unknown_complex_cases.append((
                        _sample_label(code, predecessor),
                        quality,
                        [diagnostic],
                        rendered[: args.graph_lines],
                    ))
                probe = diagnostic.get("bounded_forward_probe")
                if isinstance(probe, dict):
                    if bool(probe.get("reachable")):
                        probe_key = "reachable"
                    elif bool(probe.get("truncated")):
                        probe_key = "not_found_truncated"
                        truncated_probe_cases.append((
                            _sample_label(code, predecessor),
                            quality,
                            [diagnostic],
                            rendered[: args.graph_lines],
                        ))
                    else:
                        probe_key = "not_found_complete"
                    bounded_forward_probe_counts[probe_key] += 1
                    probe_op_counts = probe.get("op_counts")
                    if isinstance(probe_op_counts, dict):
                        for op, count in probe_op_counts.items():
                            bounded_forward_probe_op_counts[str(op)] += int(count)
                    pruned_counts = probe.get("pruned_counts")
                    if isinstance(pruned_counts, dict):
                        for op, count in pruned_counts.items():
                            bounded_forward_probe_pruned_counts[str(op)] += int(count)
        for diagnostic in shallow_diagnostics:
            shallow_diagnostic_reason_counts[str(diagnostic.get("reason", "diagnostic_error"))] += 1
            shallow_signature = _shallow_feature_signature(diagnostic)
            shallow_feature_signature_counts[shallow_signature] += 1
            shallow_feature_signature_shapes.setdefault(shallow_signature, set()).add(
                str(diagnostic.get("shape", ""))
            )
            shallow_leaf_depth_counts[_leaf_depth_key(diagnostic)] += 1
            _record_candidate_summary(
                diagnostic,
                shallow_best_candidate_op_counts,
                shallow_candidate_preserves_leaf_counts,
            )
            if shallow_depth_floor is not None and _diagnostic_leaf_depth(diagnostic) < int(shallow_depth_floor):
                shallow_low_depth_cases.append((
                    _sample_label(code, predecessor),
                    quality,
                    [diagnostic],
                    rendered[: args.graph_lines],
                ))
            if low_depth_shallow_threshold is not None and _diagnostic_leaf_depth(diagnostic) < int(low_depth_shallow_threshold):
                low_depth_shallow_leaves += 1
                low_depth_shallow_leaf_rows.append(_shallow_leaf_row(code, predecessor, diagnostic))
            shallow_class = diagnostic.get("shallow_class")
            if shallow_class:
                shallow_class_counts[str(shallow_class)] += 1
            shallow_terminal_hint = diagnostic.get("shallow_terminal_hint")
            if shallow_terminal_hint:
                shallow_terminal_hint_counts[str(shallow_terminal_hint)] += 1
            shallow_resolution = _shallow_resolution(diagnostic)
            shallow_resolution_counts[shallow_resolution] += 1
            if shallow_resolution == "impossible_rule_closed":
                shallow_impossible_rule_closed_reason_counts[
                    str(diagnostic.get("legacy_reason", "unknown"))
                ] += 1
            if shallow_resolution == "unknown_or_actionable":
                unknown_shallow_cases.append((
                    _sample_label(code, predecessor),
                    quality,
                    [diagnostic],
                    rendered[: args.graph_lines],
                ))
            shallow_probe = diagnostic.get("bounded_forward_probe")
            if isinstance(shallow_probe, dict):
                shallow_probe_key = _probe_key(shallow_probe)
                shallow_probe_counts[shallow_probe_key] += 1
                if shallow_probe_key == "reachable":
                    reachable_shallow_probe_cases.append((
                        _sample_label(code, predecessor),
                        quality,
                        [diagnostic],
                        rendered[: args.graph_lines],
                    ))
                elif shallow_probe_key == "not_found_truncated":
                    truncated_shallow_probe_cases.append((
                        _sample_label(code, predecessor),
                        quality,
                        [diagnostic],
                        rendered[: args.graph_lines],
                    ))
            shallow_leaf_rows.append(_shallow_leaf_row(code, predecessor, diagnostic))
        for key in (
            "nodes",
            "input_leaves",
            "complex_input_leaves",
            "shallow_input_leaves",
            "terminal_leaves",
            "legacy_possible_terminal_leaves",
        ):
            totals[key] += int(quality.get(key, 0))
        for key in ("max_depth", "max_input_leaf_depth", "max_shallow_input_leaf_depth", "max_complex_input_leaf_depth"):
            totals[key] = max(int(totals[key]), int(quality.get(key, 0)))
        for kind, count in dict(quality["input_leaf_kinds"]).items():
            input_leaf_kind_counts[str(kind)] += int(count)
        for kind, examples in leaf_examples.items():
            values = input_leaf_kind_examples.setdefault(kind, [])
            for example in examples:
                if len(values) >= args.max_leaf_examples:
                    break
                if example not in values:
                    values.append(example)
        for op, count in dict(quality["ops"]).items():
            op_counts[op] = op_counts.get(op, 0) + int(count)
        if not bool(valid[0]):
            failures.append((_sample_label(code, predecessor), reason, rendered[: args.graph_lines]))
        if int(quality["complex_input_leaves"]):
            actionable_complex_diagnostics = _actionable_diagnostics(diagnostics)
            complex_cases.append((
                _sample_label(code, predecessor),
                quality,
                diagnostics,
                rendered[: args.graph_lines],
            ))
            if actionable_complex_diagnostics:
                actionable_complex_leaves += len(actionable_complex_diagnostics)
                actionable_complex_cases.append((
                    _sample_label(code, predecessor),
                    quality,
                    actionable_complex_diagnostics[: args.max_leaf_examples],
                    rendered[: args.graph_lines],
                ))

    print(f"samples={len(samples)}")
    print(f"loaded_samples={len(loaded_samples)}")
    print(f"filtered_samples={len(filtered_samples)}")
    if getattr(args, "dedupe_samples", False):
        print(f"deduped_samples={len(samples)}")
    print(f"target_verdict_filter={args.target_verdict}")
    print(f"mode={_audit_mode(args)}")
    print(f"failures={len(failures)}")
    print(f"complex_cases={len(complex_cases)}")
    print("totals:")
    for key, value in totals.items():
        print(f"  {key}: {value}")
    print("ops:")
    for op, count in sorted(op_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {op}: {count}")
    if verdict_counts:
        print("target_verdicts:")
        for verdict, count in verdict_counts.most_common():
            print(f"  {verdict}: {count}")
        print("target_verdict_resolution:")
        for verdict, count in verdict_resolution_counts.most_common():
            print(f"  {verdict}: {count}")
        print("target_verdict_structural_resolution:")
        for verdict, count in verdict_structural_resolution_counts.most_common():
            print(f"  {verdict}: {count}")
        print("target_verdict_strict_resolution:")
        for verdict, count in verdict_strict_resolution_counts.most_common():
            print(f"  {verdict}: {count}")
    if strict_gap_resolution_counts:
        print("strict_gap_resolutions:")
        for resolution, count in strict_gap_resolution_counts.most_common():
            print(f"  {resolution}: {count}")
    if verdict_strict_gap_resolution_counts:
        print("target_verdict_strict_gap_resolution:")
        for resolution, count in verdict_strict_gap_resolution_counts.most_common():
            print(f"  {resolution}: {count}")
    if diagnostic_reason_counts:
        print("diagnostic_reasons:")
        for reason, count in diagnostic_reason_counts.most_common():
            print(f"  {reason}: {count}")
    if unsupported_class_counts:
        print("unsupported_classes:")
        for unsupported_class, count in unsupported_class_counts.most_common():
            print(f"  {unsupported_class}: {count}")
    if complex_resolution_counts:
        print("complex_resolutions:")
        for resolution, count in complex_resolution_counts.most_common():
            print(f"  {resolution}: {count}")
    if impossible_rule_closed_reason_counts:
        print("impossible_rule_closed_reasons:")
        for reason, count in impossible_rule_closed_reason_counts.most_common():
            print(f"  {reason}: {count}")
    if complex_leaf_depth_counts:
        print("complex_leaf_depths:")
        for depth, count in sorted(complex_leaf_depth_counts.items(), key=lambda item: _depth_sort_key(item[0])):
            print(f"  {depth}: {count}")
    if complex_best_candidate_op_counts:
        print("complex_best_candidate_ops:")
        for op, count in complex_best_candidate_op_counts.most_common():
            print(f"  {op}: {count}")
    if complex_candidate_preserves_leaf_counts:
        print("complex_candidate_preserves_leaf:")
        for key, count in complex_candidate_preserves_leaf_counts.most_common():
            print(f"  {key}: {count}")
    if bounded_forward_probe_counts:
        print("bounded_forward_probe:")
        for probe_key, count in bounded_forward_probe_counts.most_common():
            print(f"  {probe_key}: {count}")
    if bounded_forward_probe_op_counts:
        print("bounded_forward_probe_ops:")
        for op, count in bounded_forward_probe_op_counts.most_common():
            print(f"  {op}: {count}")
    if bounded_forward_probe_pruned_counts:
        print("bounded_forward_probe_pruned_ops:")
        for op, count in bounded_forward_probe_pruned_counts.most_common():
            print(f"  {op}: {count}")
    if input_leaf_kind_counts:
        print("input_leaf_kinds:")
        for kind, count in input_leaf_kind_counts.most_common():
            print(f"  {kind}: {count}")
        print("input_leaf_kind_examples:")
        for kind, _count in input_leaf_kind_counts.most_common():
            examples = input_leaf_kind_examples.get(kind, [])
            if examples:
                print(f"  {kind}:")
                for example in examples:
                    print(f"    {example}")
    if shallow_diagnostic_reason_counts:
        print("shallow_diagnostic_reasons:")
        for reason, count in shallow_diagnostic_reason_counts.most_common():
            print(f"  {reason}: {count}")
    if shallow_class_counts:
        print("shallow_classes:")
        for shallow_class, count in shallow_class_counts.most_common():
            print(f"  {shallow_class}: {count}")
    if shallow_terminal_hint_counts:
        print("shallow_terminal_hints:")
        for hint, count in shallow_terminal_hint_counts.most_common():
            print(f"  {hint}: {count}")
    if shallow_resolution_counts:
        print("shallow_resolutions:")
        for resolution, count in shallow_resolution_counts.most_common():
            print(f"  {resolution}: {count}")
    if shallow_impossible_rule_closed_reason_counts:
        print("shallow_impossible_rule_closed_reasons:")
        for reason, count in shallow_impossible_rule_closed_reason_counts.most_common():
            print(f"  {reason}: {count}")
    if shallow_feature_signature_counts:
        print("shallow_feature_signatures:")
        for signature, count in shallow_feature_signature_counts.most_common(10):
            unique_count = len(shallow_feature_signature_shapes.get(signature, set()))
            print(f"  {signature}: {count} occurrence(s), {unique_count} unique shape(s)")
    if shallow_leaf_depth_counts:
        print("shallow_leaf_depths:")
        for depth, count in sorted(shallow_leaf_depth_counts.items(), key=lambda item: _depth_sort_key(item[0])):
            print(f"  {depth}: {count}")
    if shallow_best_candidate_op_counts:
        print("shallow_best_candidate_ops:")
        for op, count in shallow_best_candidate_op_counts.most_common():
            print(f"  {op}: {count}")
    if shallow_candidate_preserves_leaf_counts:
        print("shallow_candidate_preserves_leaf:")
        for key, count in shallow_candidate_preserves_leaf_counts.most_common():
            print(f"  {key}: {count}")
    if shallow_probe_counts:
        print("shallow_bounded_forward_probe:")
        for probe_key, count in shallow_probe_counts.most_common():
            print(f"  {probe_key}: {count}")
    if terminal_op_counts:
        print("terminal_ops:")
        for op, count in terminal_op_counts.most_common():
            print(f"  {op}: {count}")
    if terminal_shape_counts:
        print(f"terminal_unique_shapes={len(terminal_shape_counts)}")
        print("terminal_shape_counts:")
        for shape, count in terminal_shape_counts.most_common(10):
            print(f"  {shape}: {count}")
    if terminal_feature_signature_counts:
        print("terminal_feature_signatures:")
        for signature, count in terminal_feature_signature_counts.most_common(10):
            unique_count = len(terminal_feature_signature_shapes.get(signature, set()))
            print(f"  {signature}: {count} occurrence(s), {unique_count} unique shape(s)")
    if terminal_explain_reason_counts:
        print("terminal_explain_reasons:")
        for reason, count in terminal_explain_reason_counts.most_common():
            print(f"  {reason}: {count}")
    if terminal_open_leaf_key_counts:
        print("terminal_open_leaf_keys:")
        for key, count in terminal_open_leaf_key_counts.most_common():
            print(f"  {key}: {count}")
    if terminal_cycle_category_counts:
        print("terminal_cycle_categories:")
        for key, count in terminal_cycle_category_counts.most_common():
            print(f"  {key}: {count}")
    if terminal_resolution_counts:
        print("terminal_resolutions:")
        for key, count in terminal_resolution_counts.most_common():
            print(f"  {key}: {count}")
    if terminal_self_open_leaf_key_counts:
        print(f"terminal_self_open_leaf_cases={terminal_self_open_leaf_cases}")
        print("terminal_self_open_leaf_keys:")
        for key, count in terminal_self_open_leaf_key_counts.most_common():
            print(f"  {key}: {count}")
    if terminal_unexpanded_leaf_key_counts:
        print("terminal_unexpanded_leaf_keys:")
        for key, count in terminal_unexpanded_leaf_key_counts.most_common():
            print(f"  {key}: {count}")
    if terminal_self_unexpanded_leaf_key_counts:
        print(f"terminal_self_unexpanded_leaf_cases={terminal_self_unexpanded_leaf_cases}")
        print("terminal_self_unexpanded_leaf_keys:")
        for key, count in terminal_self_unexpanded_leaf_key_counts.most_common():
            print(f"  {key}: {count}")
    if terminal_probe_counts:
        print(f"terminal_probe_unique_shapes={len(terminal_probe_shape_keys)}")
        print("terminal_bounded_forward_probe:")
        for probe_key, count in terminal_probe_counts.most_common():
            print(f"  {probe_key}: {count}")
    if terminal_probe_op_counts:
        print("terminal_bounded_forward_probe_ops:")
        for op, count in terminal_probe_op_counts.most_common():
            print(f"  {op}: {count}")
    if terminal_probe_pruned_counts:
        print("terminal_bounded_forward_probe_pruned_ops:")
        for op, count in terminal_probe_pruned_counts.most_common():
            print(f"  {op}: {count}")

    if failures:
        print("failure_examples:")
        for code, reason, graph in failures[: args.max_examples]:
            print(f"- code={code}")
            print(f"  reason={reason}")
            for line in graph:
                print(f"  {line}")

    if complex_cases:
        print(f"actionable_complex_leaves={actionable_complex_leaves}")
        print(f"actionable_complex_cases={len(actionable_complex_cases)}")
        print("complex_input_examples:")
        for code, quality, diagnostics, graph in complex_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  quality={quality}")
            print(f"  diagnostics={diagnostics}")
            for line in graph:
                print(f"  {line}")
    if actionable_complex_cases:
        print("actionable_complex_examples:")
        for code, quality, diagnostics, graph in actionable_complex_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  complex_input_leaves={quality['complex_input_leaves']}")
            print(f"  actionable_complex_diagnostics={diagnostics}")
            for line in graph:
                print(f"  {line}")
    if unknown_complex_cases:
        print("unknown_complex_examples:")
        for code, quality, diagnostics, graph in unknown_complex_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  complex_input_leaves={quality['complex_input_leaves']}")
            print(f"  unknown_complex_diagnostics={diagnostics}")
            for line in graph:
                print(f"  {line}")
    if truncated_probe_cases:
        print("truncated_probe_examples:")
        for code, quality, diagnostics, graph in truncated_probe_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  complex_input_leaves={quality['complex_input_leaves']}")
            print(f"  truncated_probe_diagnostics={diagnostics}")
            for line in graph:
                print(f"  {line}")
    if truncated_shallow_probe_cases:
        print("truncated_shallow_probe_examples:")
        for code, quality, diagnostics, graph in truncated_shallow_probe_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  shallow_input_leaves={quality['shallow_input_leaves']}")
            print(f"  truncated_shallow_diagnostics={diagnostics}")
            for line in graph:
                print(f"  {line}")

    if unresolved_possible_cases:
        print("unresolved_possible_examples:")
        for code, reason, diagnostics, graph in unresolved_possible_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  reason={reason}")
            print(f"  diagnostics={diagnostics}")
            for line in graph:
                print(f"  {line}")
    if structural_unresolved_possible_cases:
        print("structural_unresolved_possible_examples:")
        for code, quality, unknown_shallow_diagnostics, graph in structural_unresolved_possible_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  structural_reason=complex_or_unknown_shallow")
            print(f"  quality={quality}")
            print(f"  unknown_shallow_diagnostics={unknown_shallow_diagnostics}")
            for line in graph:
                print(f"  {line}")
    if strict_unresolved_possible_cases:
        print("strict_unresolved_possible_examples:")
        for code, strict_reason, quality, graph in strict_unresolved_possible_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  strict_reason={strict_reason}")
            print(f"  quality={quality}")
            for line in graph:
                print(f"  {line}")
    if terminal_boundary_cases:
        print(f"terminal_boundary_cases={len(terminal_boundary_cases)}")
        print(f"known_terminal_boundary_cases={len(known_terminal_boundary_cases)}")
        print(f"actionable_terminal_boundary_cases={len(actionable_terminal_boundary_cases)}")
        print(f"unprobed_terminal_boundary_cases={len(unprobed_terminal_boundary_cases)}")
        print("terminal_boundary_examples:")
        for code, quality, graph in terminal_boundary_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  terminal_leaves={quality.get('terminal_leaves', 0)}")
            print(f"  terminal_shapes={quality.get('terminal_shapes', [])}")
            for line in graph:
                print(f"  {line}")
    if shallow_possible_cases:
        print(f"shallow_possible_leaves={shallow_possible_leaves}")
        print(f"actionable_shallow_possible_leaves={actionable_shallow_possible_leaves}")
        print(f"actionable_shallow_possible_cases={len(actionable_shallow_possible_cases)}")
        print("shallow_possible_examples:")
        for code, quality, examples, shallow_diagnostics, graph in shallow_possible_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  shallow_input_leaves={quality['shallow_input_leaves']}")
            print(f"  examples={examples}")
            print(f"  shallow_diagnostics={shallow_diagnostics}")
            for line in graph:
                print(f"  {line}")
    if reachable_terminal_probe_cases:
        print("reachable_terminal_probe_examples:")
        for code, quality, terminal_diagnostics, graph in reachable_terminal_probe_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  terminal_leaves={quality.get('terminal_leaves', 0)}")
            print(f"  reachable_terminal_diagnostics={terminal_diagnostics}")
            for line in graph:
                print(f"  {line}")
    if truncated_terminal_probe_cases:
        print("truncated_terminal_probe_examples:")
        for code, quality, terminal_diagnostics, graph in truncated_terminal_probe_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  terminal_leaves={quality.get('terminal_leaves', 0)}")
            print(f"  truncated_terminal_diagnostics={terminal_diagnostics}")
            for line in graph:
                print(f"  {line}")
    if actionable_shallow_possible_cases:
        print("actionable_shallow_possible_examples:")
        for code, quality, shallow_diagnostics, graph in actionable_shallow_possible_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  shallow_input_leaves={quality['shallow_input_leaves']}")
            print(f"  actionable_shallow_diagnostics={shallow_diagnostics}")
            for line in graph:
                print(f"  {line}")
    if unknown_shallow_cases:
        print("unknown_shallow_examples:")
        for code, quality, shallow_diagnostics, graph in unknown_shallow_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  shallow_input_leaves={quality['shallow_input_leaves']}")
            print(f"  unknown_shallow_diagnostics={shallow_diagnostics}")
            for line in graph:
                print(f"  {line}")
    if reachable_shallow_probe_cases:
        print("reachable_shallow_probe_examples:")
        for code, quality, shallow_diagnostics, graph in reachable_shallow_probe_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  shallow_input_leaves={quality['shallow_input_leaves']}")
            print(f"  reachable_shallow_diagnostics={shallow_diagnostics}")
            for line in graph:
                print(f"  {line}")
    if shallow_low_depth_cases:
        print("shallow_low_depth_examples:")
        for code, quality, shallow_diagnostics, graph in shallow_low_depth_cases[: args.max_examples]:
            print(f"- code={code}")
            print(f"  shallow_input_leaves={quality['shallow_input_leaves']}")
            print(f"  shallow_low_depth_diagnostics={shallow_diagnostics}")
            for line in graph:
                print(f"  {line}")

    if args.write_summary_json:
        summary = {
            "samples": len(samples),
            "loaded_samples": len(loaded_samples),
            "filtered_samples": len(filtered_samples),
            "deduped_samples": len(samples) if getattr(args, "dedupe_samples", False) else None,
            "target_verdict_filter": args.target_verdict,
            "mode": _audit_mode(args),
            "probe_config": {
                "probe_max_steps": args.probe_max_steps,
                "probe_max_states": args.probe_max_states,
                "probe_pair_limit": args.probe_pair_limit,
                "complex_probe_max_steps": _int_arg(args, "complex_probe_max_steps", args.probe_max_steps),
                "complex_probe_max_states": _int_arg(args, "complex_probe_max_states", args.probe_max_states),
                "complex_probe_pair_limit": _int_arg(args, "complex_probe_pair_limit", args.probe_pair_limit),
                "shallow_probe_pair_limit": _int_arg(args, "shallow_probe_pair_limit", args.probe_pair_limit),
                "probe_shallow_leaves": bool(getattr(args, "probe_shallow_leaves", False)),
                "probe_terminal_boundaries": bool(
                    getattr(args, "probe_terminal_boundaries", False)
                    or getattr(args, "fail_on_reachable_terminal_probe", False)
                    or getattr(args, "fail_on_truncated_terminal_probe", False)
                ),
                "terminal_probe_pair_limit": _int_arg(args, "terminal_probe_pair_limit", args.probe_pair_limit),
            },
            "failures": len(failures),
            "complex_cases": len(complex_cases),
            "actionable_complex_cases": len(actionable_complex_cases),
            "actionable_complex_leaves": actionable_complex_leaves,
            "unknown_complex_cases": len(unknown_complex_cases),
            "truncated_probe_cases": len(truncated_probe_cases),
            "truncated_shallow_probe_cases": len(truncated_shallow_probe_cases),
            "unresolved_possible_cases": len(unresolved_possible_cases),
            "structural_unresolved_possible_cases": len(structural_unresolved_possible_cases),
            "strict_unresolved_possible_cases": len(strict_unresolved_possible_cases),
            "terminal_boundary_cases": len(terminal_boundary_cases),
            "known_terminal_boundary_cases": len(known_terminal_boundary_cases),
            "actionable_terminal_boundary_cases": len(actionable_terminal_boundary_cases),
            "unprobed_terminal_boundary_cases": len(unprobed_terminal_boundary_cases),
            "terminal_unique_shapes": len(terminal_shape_counts),
            "terminal_self_open_leaf_cases": terminal_self_open_leaf_cases,
            "terminal_self_unexpanded_leaf_cases": terminal_self_unexpanded_leaf_cases,
            "terminal_probe_unique_shapes": len(terminal_probe_shape_keys),
            "reachable_terminal_probe_cases": len(reachable_terminal_probe_cases),
            "truncated_terminal_probe_cases": len(truncated_terminal_probe_cases),
            "shallow_possible_cases": len(shallow_possible_cases),
            "shallow_possible_leaves": shallow_possible_leaves,
            "actionable_shallow_possible_cases": len(actionable_shallow_possible_cases),
            "actionable_shallow_possible_leaves": actionable_shallow_possible_leaves,
            "unknown_shallow_cases": len(unknown_shallow_cases),
            "shallow_low_depth_cases": len(shallow_low_depth_cases),
            "low_depth_shallow_threshold": low_depth_shallow_threshold,
            "low_depth_shallow_leaves": low_depth_shallow_leaves,
            "totals": totals,
            "ops": dict(sorted(op_counts.items())),
            "target_verdicts": dict(verdict_counts),
            "target_verdict_resolution": dict(verdict_resolution_counts),
            "target_verdict_structural_resolution": dict(verdict_structural_resolution_counts),
            "target_verdict_strict_resolution": dict(verdict_strict_resolution_counts),
            "strict_gap_resolutions": dict(strict_gap_resolution_counts),
            "target_verdict_strict_gap_resolution": dict(verdict_strict_gap_resolution_counts),
            "diagnostic_reasons": dict(diagnostic_reason_counts),
            "unsupported_classes": dict(unsupported_class_counts),
            "complex_resolutions": dict(complex_resolution_counts),
            "impossible_rule_closed_reasons": dict(impossible_rule_closed_reason_counts),
            "complex_leaf_depths": dict(complex_leaf_depth_counts),
            "complex_best_candidate_ops": dict(complex_best_candidate_op_counts),
            "complex_candidate_preserves_leaf": dict(complex_candidate_preserves_leaf_counts),
            "bounded_forward_probe": dict(bounded_forward_probe_counts),
            "bounded_forward_probe_ops": dict(bounded_forward_probe_op_counts),
            "bounded_forward_probe_pruned_ops": dict(bounded_forward_probe_pruned_counts),
            "shallow_diagnostic_reasons": dict(shallow_diagnostic_reason_counts),
            "shallow_classes": dict(shallow_class_counts),
            "shallow_terminal_hints": dict(shallow_terminal_hint_counts),
            "shallow_resolutions": dict(shallow_resolution_counts),
            "shallow_impossible_rule_closed_reasons": dict(shallow_impossible_rule_closed_reason_counts),
            "shallow_feature_signatures": dict(shallow_feature_signature_counts),
            "shallow_unique_feature_signatures": {
                signature: len(shapes)
                for signature, shapes in sorted(shallow_feature_signature_shapes.items())
            },
            "shallow_leaf_depths": dict(shallow_leaf_depth_counts),
            "shallow_best_candidate_ops": dict(shallow_best_candidate_op_counts),
            "shallow_candidate_preserves_leaf": dict(shallow_candidate_preserves_leaf_counts),
            "shallow_bounded_forward_probe": dict(shallow_probe_counts),
            "terminal_ops": dict(terminal_op_counts),
            "terminal_shape_counts": dict(terminal_shape_counts),
            "terminal_feature_signatures": dict(terminal_feature_signature_counts),
            "terminal_unique_feature_signatures": {
                signature: len(shapes)
                for signature, shapes in sorted(terminal_feature_signature_shapes.items())
            },
            "terminal_explain_reasons": dict(terminal_explain_reason_counts),
            "terminal_open_leaf_keys": dict(terminal_open_leaf_key_counts),
            "terminal_cycle_categories": dict(terminal_cycle_category_counts),
            "terminal_resolutions": dict(terminal_resolution_counts),
            "terminal_self_open_leaf_keys": dict(terminal_self_open_leaf_key_counts),
            "terminal_unexpanded_leaf_keys": dict(terminal_unexpanded_leaf_key_counts),
            "terminal_self_unexpanded_leaf_keys": dict(terminal_self_unexpanded_leaf_key_counts),
            "terminal_bounded_forward_probe": dict(terminal_probe_counts),
            "terminal_bounded_forward_probe_ops": dict(terminal_probe_op_counts),
            "terminal_bounded_forward_probe_pruned_ops": dict(terminal_probe_pruned_counts),
            "reachable_shallow_probe_cases": len(reachable_shallow_probe_cases),
            "shallow_depth_floor": getattr(args, "fail_on_shallow_depth_below", None),
            "input_leaf_kinds": dict(input_leaf_kind_counts),
            "input_leaf_kind_examples": input_leaf_kind_examples,
            "failure_examples": [
                {"code": code, "reason": reason, "graph": graph}
                for code, reason, graph in failures[: args.max_examples]
            ],
            "complex_input_examples": [
                {"code": code, "quality": quality, "diagnostics": diagnostics, "graph": graph}
                for code, quality, diagnostics, graph in complex_cases[: args.max_examples]
            ],
            "actionable_complex_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "actionable_complex_diagnostics": diagnostics,
                    "graph": graph,
                }
                for code, quality, diagnostics, graph in actionable_complex_cases[: args.max_examples]
            ],
            "unknown_complex_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "unknown_complex_diagnostics": diagnostics,
                    "graph": graph,
                }
                for code, quality, diagnostics, graph in unknown_complex_cases[: args.max_examples]
            ],
            "truncated_probe_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "truncated_probe_diagnostics": diagnostics,
                    "graph": graph,
                }
                for code, quality, diagnostics, graph in truncated_probe_cases[: args.max_examples]
            ],
            "truncated_shallow_probe_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "truncated_shallow_diagnostics": diagnostics,
                    "graph": graph,
                }
                for code, quality, diagnostics, graph in truncated_shallow_probe_cases[: args.max_examples]
            ],
            "unresolved_possible_examples": [
                {"code": code, "reason": reason, "diagnostics": diagnostics, "graph": graph}
                for code, reason, diagnostics, graph in unresolved_possible_cases[: args.max_examples]
            ],
            "structural_unresolved_possible_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "unknown_shallow_diagnostics": unknown_shallow_diagnostics,
                    "graph": graph,
                }
                for code, quality, unknown_shallow_diagnostics, graph in structural_unresolved_possible_cases[
                    : args.max_examples
                ]
            ],
            "strict_unresolved_possible_examples": [
                {"code": code, "strict_reason": strict_reason, "quality": quality, "graph": graph}
                for code, strict_reason, quality, graph in strict_unresolved_possible_cases[: args.max_examples]
            ],
            "terminal_boundary_examples": [
                {"code": code, "quality": quality, "graph": graph}
                for code, quality, graph in terminal_boundary_cases[: args.max_examples]
            ],
            "known_terminal_boundary_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "terminal_diagnostics": terminal_diagnostics,
                    "graph": graph,
                }
                for code, quality, terminal_diagnostics, graph in known_terminal_boundary_cases[: args.max_examples]
            ],
            "actionable_terminal_boundary_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "terminal_diagnostics": terminal_diagnostics,
                    "graph": graph,
                }
                for code, quality, terminal_diagnostics, graph in actionable_terminal_boundary_cases[: args.max_examples]
            ],
            "reachable_terminal_probe_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "reachable_terminal_diagnostics": terminal_diagnostics,
                    "graph": graph,
                }
                for code, quality, terminal_diagnostics, graph in reachable_terminal_probe_cases[: args.max_examples]
            ],
            "truncated_terminal_probe_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "truncated_terminal_diagnostics": terminal_diagnostics,
                    "graph": graph,
                }
                for code, quality, terminal_diagnostics, graph in truncated_terminal_probe_cases[: args.max_examples]
            ],
            "shallow_possible_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "examples": examples,
                    "shallow_diagnostics": shallow_diagnostics,
                    "graph": graph,
                }
                for code, quality, examples, shallow_diagnostics, graph in shallow_possible_cases[: args.max_examples]
            ],
            "actionable_shallow_possible_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "actionable_shallow_diagnostics": shallow_diagnostics,
                    "graph": graph,
                }
                for code, quality, shallow_diagnostics, graph in actionable_shallow_possible_cases[: args.max_examples]
            ],
            "unknown_shallow_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "unknown_shallow_diagnostics": shallow_diagnostics,
                    "graph": graph,
                }
                for code, quality, shallow_diagnostics, graph in unknown_shallow_cases[: args.max_examples]
            ],
            "reachable_shallow_probe_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "reachable_shallow_diagnostics": shallow_diagnostics,
                    "graph": graph,
                }
                for code, quality, shallow_diagnostics, graph in reachable_shallow_probe_cases[: args.max_examples]
            ],
            "shallow_low_depth_examples": [
                {
                    "code": code,
                    "quality": quality,
                    "shallow_low_depth_diagnostics": shallow_diagnostics,
                    "graph": graph,
                }
                for code, quality, shallow_diagnostics, graph in shallow_low_depth_cases[: args.max_examples]
            ],
        }
        args.write_summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"summary_written={args.write_summary_json}")

    write_unsupported_leaves = getattr(args, "write_unsupported_leaves", None)
    if write_unsupported_leaves:
        write_unsupported_leaves.parent.mkdir(parents=True, exist_ok=True)
        _write_unsupported_leaf_rows(write_unsupported_leaves, unsupported_leaf_rows)
        print(f"unsupported_leaves_written={write_unsupported_leaves}")
        print(f"unsupported_leaves_written_count={len(unsupported_leaf_rows)}")

    write_shallow_leaves = getattr(args, "write_shallow_leaves", None)
    if write_shallow_leaves:
        write_shallow_leaves.parent.mkdir(parents=True, exist_ok=True)
        _write_leaf_rows(write_shallow_leaves, shallow_leaf_rows)
        print(f"shallow_leaves_written={write_shallow_leaves}")
        print(f"shallow_leaves_written_count={len(shallow_leaf_rows)}")

    write_low_depth_shallow_leaves = getattr(args, "write_low_depth_shallow_leaves", None)
    if write_low_depth_shallow_leaves:
        write_low_depth_shallow_leaves.parent.mkdir(parents=True, exist_ok=True)
        _write_leaf_rows(write_low_depth_shallow_leaves, low_depth_shallow_leaf_rows)
        print(f"low_depth_shallow_leaves_written={write_low_depth_shallow_leaves}")
        print(f"low_depth_shallow_leaves_written_count={len(low_depth_shallow_leaf_rows)}")

    write_terminal_boundaries = getattr(args, "write_terminal_boundaries", None)
    if write_terminal_boundaries:
        write_terminal_boundaries.parent.mkdir(parents=True, exist_ok=True)
        _write_terminal_rows(write_terminal_boundaries, terminal_boundary_rows)
        print(f"terminal_boundaries_written={write_terminal_boundaries}")
        print(f"terminal_boundaries_written_count={len(terminal_boundary_rows)}")

    write_unique_terminal_boundaries = getattr(args, "write_unique_terminal_boundaries", None)
    if write_unique_terminal_boundaries:
        write_unique_terminal_boundaries.parent.mkdir(parents=True, exist_ok=True)
        unique_terminal_rows = _unique_terminal_rows(terminal_boundary_rows)
        _write_unique_terminal_rows(write_unique_terminal_boundaries, unique_terminal_rows)
        print(f"unique_terminal_boundaries_written={write_unique_terminal_boundaries}")
        print(f"unique_terminal_boundaries_written_count={len(unique_terminal_rows)}")

    write_terminal_signatures = getattr(args, "write_terminal_signatures", None)
    if write_terminal_signatures:
        write_terminal_signatures.parent.mkdir(parents=True, exist_ok=True)
        signature_rows = _terminal_signature_rows(_unique_terminal_rows(terminal_boundary_rows))
        _write_terminal_signature_rows(write_terminal_signatures, signature_rows)
        print(f"terminal_signatures_written={write_terminal_signatures}")
        print(f"terminal_signatures_written_count={len(signature_rows)}")

    if args.fail_on_validation_failure and failures:
        return 1
    if args.fail_on_complex_input and complex_cases:
        return 1
    if args.fail_on_actionable_complex_input and actionable_complex_cases:
        return 1
    if getattr(args, "fail_on_unknown_complex_class", False) and unknown_complex_cases:
        return 1
    if args.fail_on_truncated_probe and (truncated_probe_cases or truncated_shallow_probe_cases):
        return 1
    if getattr(args, "fail_on_truncated_terminal_probe", False) and truncated_terminal_probe_cases:
        return 1
    if getattr(args, "fail_on_reachable_terminal_probe", False) and reachable_terminal_probe_cases:
        return 1
    if args.fail_on_unresolved_possible and unresolved_possible_cases:
        return 1
    if getattr(args, "fail_on_structural_unresolved_possible", False) and structural_unresolved_possible_cases:
        return 1
    if args.fail_on_strict_unresolved_possible and strict_unresolved_possible_cases:
        return 1
    if getattr(args, "fail_on_terminal_boundary", False) and terminal_boundary_cases:
        return 1
    if args.fail_on_shallow_possible and shallow_possible_cases:
        return 1
    if args.fail_on_actionable_shallow_possible and actionable_shallow_possible_cases:
        return 1
    if getattr(args, "fail_on_reachable_shallow_probe", False) and reachable_shallow_probe_cases:
        return 1
    if getattr(args, "fail_on_unknown_shallow_class", False) and unknown_shallow_cases:
        return 1
    if getattr(args, "fail_on_shallow_depth_below", None) is not None and shallow_low_depth_cases:
        return 1
    if args.fail_on_shallow_input and totals["shallow_input_leaves"]:
        return 1
    return 0


def _actionable_shallow_diagnostics(diagnostics: list[dict[str, object]]) -> list[dict[str, object]]:
    return _actionable_diagnostics(diagnostics)


def _actionable_diagnostics(diagnostics: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.get("reason") == "candidate_exists_but_not_selected" or diagnostic.get("probe_actionable")
    ]


def _record_candidate_summary(
    diagnostic: dict[str, object],
    best_candidate_op_counts: Counter[str],
    candidate_preserves_leaf_counts: Counter[str],
) -> None:
    candidate_quality = diagnostic.get("best_local_candidate_quality")
    if isinstance(candidate_quality, dict):
        best_candidate_op_counts[str(candidate_quality.get("op", "unknown"))] += 1
    candidate_preserves_leaf_counts[str(bool(diagnostic.get("candidate_preserves_leaf"))).lower()] += 1


def _probe_key(probe: dict[str, object]) -> str:
    status = probe.get("status")
    if status:
        return str(status)
    if bool(probe.get("reachable")):
        return "reachable"
    if bool(probe.get("truncated")):
        return "not_found_truncated"
    return "not_found_complete"


def _is_known_structural_shallow(diagnostic: dict[str, object]) -> bool:
    return is_known_structural_shallow_diagnostic(diagnostic)


def _shallow_resolution(diagnostic: dict[str, object]) -> str:
    if is_impossible_rule_closed_shallow_diagnostic(diagnostic):
        return "impossible_rule_closed"
    if _is_known_structural_shallow(diagnostic):
        return "known_structural"
    return "unknown_or_actionable"


def _is_known_unsupported_complex(diagnostic: dict[str, object]) -> bool:
    return is_known_unsupported_complex_diagnostic(diagnostic)


def _complex_resolution(diagnostic: dict[str, object]) -> str:
    if is_impossible_rule_closed_complex_diagnostic(diagnostic):
        return "impossible_rule_closed"
    if _is_known_unsupported_complex(diagnostic):
        return "known_unsupported"
    return "unknown_or_actionable"


def _strict_gap_resolution(
    strict_resolved: bool,
    quality: dict[str, object],
    diagnostics: list[dict[str, object]],
    shallow_diagnostics: list[dict[str, object]],
    terminal_diagnostics: list[dict[str, object]],
) -> str:
    if strict_resolved:
        return "strict_resolved"
    gaps: list[str] = []
    if int(quality.get("complex_input_leaves", 0)):
        complex_resolutions = {_complex_resolution(diagnostic) for diagnostic in diagnostics}
        if complex_resolutions == {"impossible_rule_closed"}:
            gaps.append("complex_impossible_rule_closed")
        elif complex_resolutions and complex_resolutions <= {"known_unsupported", "impossible_rule_closed"}:
            gaps.append("complex_known_closed")
        else:
            gaps.append("complex_unknown_or_actionable")
    if int(quality.get("shallow_input_leaves", 0)):
        shallow_resolutions = {_shallow_resolution(diagnostic) for diagnostic in shallow_diagnostics}
        if shallow_resolutions == {"impossible_rule_closed"}:
            gaps.append("shallow_impossible_rule_closed")
        elif shallow_resolutions and shallow_resolutions <= {"known_structural", "impossible_rule_closed"}:
            gaps.append("shallow_known_closed")
        else:
            gaps.append("shallow_unknown_or_actionable")
    if int(quality.get("terminal_leaves", 0)):
        terminal_resolution = _terminal_boundary_resolution(terminal_diagnostics)
        if terminal_resolution == "known_closed":
            gaps.append("terminal_known_closed")
        elif terminal_resolution == "actionable":
            gaps.append("terminal_actionable")
        else:
            gaps.append("terminal_unprobed")
    if int(quality.get("input_leaves", 0)) and not gaps:
        gaps.append("input_leaf")
    return "+".join(gaps) if gaps else "unknown_strict_gap"


def _strict_unresolved_reason(quality: dict[str, object]) -> str:
    reasons: list[str] = []
    if int(quality.get("complex_input_leaves", 0)):
        reasons.append("complex_input")
    if int(quality.get("shallow_input_leaves", 0)):
        reasons.append("shallow_input")
    if int(quality.get("terminal_leaves", 0)):
        reasons.append("legacy_possible_terminal")
    return "+".join(reasons) if reasons else "unknown_strict_gap"


def _int_arg(args: argparse.Namespace, name: str, default: int) -> int:
    value = getattr(args, name, None)
    return int(default if value is None else value)


def _leaf_depth_key(diagnostic: dict[str, object]) -> str:
    value = diagnostic.get("leaf_depth", "")
    return str(value) if value not in {"", None} else "unknown"


def _diagnostic_leaf_depth(diagnostic: dict[str, object]) -> int:
    try:
        return int(diagnostic.get("leaf_depth", 0))
    except (TypeError, ValueError):
        return 0


def _low_depth_shallow_threshold(args: argparse.Namespace) -> int | None:
    explicit = getattr(args, "low_depth_shallow_threshold", None)
    if explicit is not None:
        return int(explicit)
    floor = getattr(args, "fail_on_shallow_depth_below", None)
    if floor is not None:
        return int(floor)
    return None


def _depth_sort_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def _unsupported_leaf_row(code: str, predecessor: str, diagnostic: dict[str, object]) -> dict[str, object]:
    return _leaf_row(code, predecessor, diagnostic)


def _shallow_leaf_row(code: str, predecessor: str, diagnostic: dict[str, object]) -> dict[str, object]:
    return _leaf_row(code, predecessor, diagnostic)


def _terminal_leaf_row(code: str, predecessor: str, diagnostic: dict[str, object]) -> dict[str, object]:
    features = diagnostic.get("leaf_features")
    if not isinstance(features, dict):
        features = {}
    probe = diagnostic.get("bounded_forward_probe")
    probe_status = ""
    probe_states = ""
    probe_frontier = ""
    if isinstance(probe, dict):
        probe_status = _probe_key(probe)
        probe_states = str(probe.get("states", ""))
        probe_frontier = str(probe.get("frontier", ""))
    return {
        "sample": _sample_label(code, predecessor),
        "target": code,
        "predecessor": predecessor,
        "terminal_shape": str(diagnostic.get("shape", "")),
        "terminal_detail": str(diagnostic.get("detail", "")),
        "terminal_op": str(diagnostic.get("op", "")),
        "terminal_note": str(diagnostic.get("note", "")),
        "leaf_depth": str(diagnostic.get("leaf_depth", "")),
        "explain_reason": str(diagnostic.get("explain_reason", "")),
        "terminal_cycle_category": _terminal_cycle_category(diagnostic),
        "terminal_resolution": _terminal_resolution(diagnostic),
        "terminal_feature_signature": _terminal_feature_signature(diagnostic),
        "open_leaf_keys": json.dumps(diagnostic.get("open_leaf_keys", {}), ensure_ascii=False, sort_keys=True),
        "open_leaf_descriptions": "; ".join(str(item) for item in diagnostic.get("open_leaf_descriptions", ())),
        "open_leaf_shapes": "; ".join(str(item) for item in diagnostic.get("open_leaf_shapes", ())),
        "self_open_leaf_keys": json.dumps(
            diagnostic.get("self_open_leaf_keys", {}),
            ensure_ascii=False,
            sort_keys=True,
        ),
        "self_open_leaf_count": str(diagnostic.get("self_open_leaf_count", "")),
        "unexpanded_leaf_keys": json.dumps(
            diagnostic.get("unexpanded_leaf_keys", {}),
            ensure_ascii=False,
            sort_keys=True,
        ),
        "self_unexpanded_leaf_keys": json.dumps(
            diagnostic.get("self_unexpanded_leaf_keys", {}),
            ensure_ascii=False,
            sort_keys=True,
        ),
        "self_unexpanded_leaf_count": str(diagnostic.get("self_unexpanded_leaf_count", "")),
        "probe_status": probe_status,
        "probe_states": probe_states,
        "probe_frontier": probe_frontier,
        "legacy_verdict": str(diagnostic.get("legacy_verdict", "")),
        "legacy_strict_verdict": str(diagnostic.get("legacy_strict_verdict", "")),
        "legacy_class": str(diagnostic.get("legacy_class", "")),
        "legacy_reason": str(diagnostic.get("legacy_reason", "")),
        "layers": str(features.get("layers", "")),
        "occupied": str(features.get("occupied", "")),
        "crystals": str(features.get("crystals", "")),
        "pins": str(features.get("pins", "")),
        "solids": str(features.get("solids", "")),
    }


def _terminal_open_leaf_key(diagnostic: dict[str, object]) -> str:
    open_leaf_keys = diagnostic.get("open_leaf_keys")
    if not isinstance(open_leaf_keys, dict):
        open_leaf_keys = {}
    return json.dumps(open_leaf_keys, ensure_ascii=False, sort_keys=True)


def _terminal_cycle_category(diagnostic: dict[str, object]) -> str:
    if int(diagnostic.get("self_open_leaf_count", 0)):
        return "self_open_leaf_cycle"
    if int(diagnostic.get("self_unexpanded_leaf_count", 0)):
        return "self_unexpanded_leaf_cycle"
    open_leaf_keys = diagnostic.get("open_leaf_keys")
    if isinstance(open_leaf_keys, dict) and open_leaf_keys:
        return "external_open_leaf"
    unexpanded_leaf_keys = diagnostic.get("unexpanded_leaf_keys")
    if isinstance(unexpanded_leaf_keys, dict) and unexpanded_leaf_keys:
        return "external_unexpanded_leaf"
    return "closed_symbolic_terminal"


def _terminal_resolution(diagnostic: dict[str, object]) -> str:
    probe = diagnostic.get("bounded_forward_probe")
    if isinstance(probe, dict):
        probe_key = _probe_key(probe)
        if probe_key == "reachable":
            return "bounded_probe_reachable"
        if probe_key == "not_found_truncated":
            return "bounded_probe_truncated"
        if probe_key == "not_found_complete":
            return f"{_terminal_cycle_category(diagnostic)}_probe_closed"
    return _terminal_cycle_category(diagnostic)


def _terminal_boundary_resolution(diagnostics: list[dict[str, object]]) -> str:
    if not diagnostics:
        return "none"
    resolutions = {_terminal_resolution(diagnostic) for diagnostic in diagnostics}
    if resolutions & {"bounded_probe_reachable", "bounded_probe_truncated"}:
        return "actionable"
    if all(resolution.endswith("_probe_closed") for resolution in resolutions):
        return "known_closed"
    return "unprobed"


def _terminal_feature_signature(diagnostic: dict[str, object]) -> str:
    features = diagnostic.get("leaf_features")
    if not isinstance(features, dict):
        features = {}
    return "|".join(
        (
            f"cycle={_terminal_cycle_category(diagnostic)}",
            f"layers={features.get('layers', '')}",
            f"pins={features.get('pins', '')}",
            f"crystals={features.get('crystals', '')}",
            f"solids={features.get('solids', '')}",
        )
    )


def _shallow_feature_signature(diagnostic: dict[str, object]) -> str:
    features = diagnostic.get("leaf_features")
    if not isinstance(features, dict):
        features = {}
    probe = diagnostic.get("bounded_forward_probe")
    probe_key = _probe_key(probe) if isinstance(probe, dict) else ""
    return "|".join(
        (
            f"kind={diagnostic.get('kind', '')}",
            f"class={diagnostic.get('shallow_class', '')}",
            f"reason={diagnostic.get('reason', '')}",
            f"probe={probe_key}",
            f"layers={features.get('layers', '')}",
            f"pins={features.get('pins', '')}",
            f"crystals={features.get('crystals', '')}",
            f"solids={features.get('solids', '')}",
        )
    )


def _attach_terminal_probe(
    diagnostic: dict[str, object],
    cache: dict[tuple[str, int, int, int], dict[str, object]],
    max_steps: int,
    max_states: int,
    pair_limit: int,
) -> None:
    shape = str(diagnostic.get("shape") or diagnostic.get("detail") or "")
    if not shape:
        return
    key = (sfa.normalize_code(shape), max_steps, max_states, pair_limit)
    if key not in cache:
        cache[key] = production_graph.bounded_forward_probe(
            shape,
            max_steps=max_steps,
            max_states=max_states,
            pair_limit=pair_limit,
        )
    diagnostic["bounded_forward_probe"] = dict(cache[key])


def _terminal_self_open_leaf_key(diagnostic: dict[str, object]) -> str:
    self_open_leaf_keys = diagnostic.get("self_open_leaf_keys")
    if not isinstance(self_open_leaf_keys, dict):
        self_open_leaf_keys = {}
    return json.dumps(self_open_leaf_keys, ensure_ascii=False, sort_keys=True)


def _terminal_unexpanded_leaf_key(diagnostic: dict[str, object]) -> str:
    unexpanded_leaf_keys = diagnostic.get("unexpanded_leaf_keys")
    if not isinstance(unexpanded_leaf_keys, dict):
        unexpanded_leaf_keys = {}
    return json.dumps(unexpanded_leaf_keys, ensure_ascii=False, sort_keys=True)


def _terminal_self_unexpanded_leaf_key(diagnostic: dict[str, object]) -> str:
    self_unexpanded_leaf_keys = diagnostic.get("self_unexpanded_leaf_keys")
    if not isinstance(self_unexpanded_leaf_keys, dict):
        self_unexpanded_leaf_keys = {}
    return json.dumps(self_unexpanded_leaf_keys, ensure_ascii=False, sort_keys=True)


def _leaf_row(code: str, predecessor: str, diagnostic: dict[str, object]) -> dict[str, object]:
    probe = diagnostic.get("bounded_forward_probe")
    probe_status = ""
    probe_states = ""
    probe_frontier = ""
    if isinstance(probe, dict):
        probe_status = str(probe.get("status", ""))
        if not probe_status:
            if bool(probe.get("reachable")):
                probe_status = "reachable"
            elif bool(probe.get("truncated")):
                probe_status = "not_found_truncated"
            else:
                probe_status = "not_found_complete"
        probe_states = str(probe.get("states", ""))
        probe_frontier = str(probe.get("frontier", ""))
    features = diagnostic.get("leaf_features")
    if not isinstance(features, dict):
        try:
            features = _leaf_features_from_code(str(diagnostic.get("detail") or diagnostic.get("shape") or ""))
        except Exception:
            features = {}
    return {
        "sample": _sample_label(code, predecessor),
        "target": code,
        "predecessor": predecessor,
        "leaf_shape": str(diagnostic.get("shape", "")),
        "leaf_detail": str(diagnostic.get("detail", "")),
        "kind": str(diagnostic.get("kind", "")),
        "leaf_depth": str(diagnostic.get("leaf_depth", "")),
        "reason": str(diagnostic.get("reason", "")),
        "leaf_class": str(diagnostic.get("shallow_class") or diagnostic.get("unsupported_class") or ""),
        "unsupported_class": str(diagnostic.get("unsupported_class", "")),
        "resolution": (
            _complex_resolution(diagnostic)
            if diagnostic.get("kind") == "complex"
            else _shallow_resolution(diagnostic)
            if str(diagnostic.get("kind", "")) in production_graph.SHALLOW_INPUT_KINDS
            else ""
        ),
        "shallow_feature_signature": (
            _shallow_feature_signature(diagnostic)
            if str(diagnostic.get("kind", "")) in production_graph.SHALLOW_INPUT_KINDS
            else ""
        ),
        "legacy_strict_verdict": str(diagnostic.get("legacy_strict_verdict", "")),
        "legacy_reason": str(diagnostic.get("legacy_reason", "")),
        "shallow_terminal_hint": str(diagnostic.get("shallow_terminal_hint", "")),
        "probe_status": probe_status,
        "probe_states": probe_states,
        "probe_frontier": probe_frontier,
        "layers": str(features.get("layers", "")),
        "occupied": str(features.get("occupied", "")),
        "crystals": str(features.get("crystals", "")),
        "pins": str(features.get("pins", "")),
        "solids": str(features.get("solids", "")),
    }


def _write_unsupported_leaf_rows(path: Path, rows: list[dict[str, object]]) -> None:
    _write_leaf_rows(path, rows)


def _write_leaf_rows(path: Path, rows: list[dict[str, object]]) -> None:
    columns = (
        "sample",
        "target",
        "predecessor",
        "leaf_shape",
        "leaf_detail",
        "kind",
        "leaf_depth",
        "reason",
        "leaf_class",
        "unsupported_class",
        "resolution",
        "shallow_feature_signature",
        "legacy_strict_verdict",
        "legacy_reason",
        "shallow_terminal_hint",
        "probe_status",
        "probe_states",
        "probe_frontier",
        "layers",
        "occupied",
        "crystals",
        "pins",
        "solids",
    )
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(_tsv_cell(row.get(column, "")) for column in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_terminal_rows(path: Path, rows: list[dict[str, object]]) -> None:
    columns = (
        "sample",
        "target",
        "predecessor",
        "terminal_shape",
        "terminal_detail",
        "terminal_op",
        "terminal_note",
        "leaf_depth",
        "explain_reason",
        "terminal_cycle_category",
        "terminal_resolution",
        "terminal_feature_signature",
        "open_leaf_keys",
        "open_leaf_descriptions",
        "open_leaf_shapes",
        "self_open_leaf_keys",
        "self_open_leaf_count",
        "unexpanded_leaf_keys",
        "self_unexpanded_leaf_keys",
        "self_unexpanded_leaf_count",
        "probe_status",
        "probe_states",
        "probe_frontier",
        "legacy_verdict",
        "legacy_strict_verdict",
        "legacy_class",
        "legacy_reason",
        "layers",
        "occupied",
        "crystals",
        "pins",
        "solids",
    )
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(_tsv_cell(row.get(column, "")) for column in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _unique_terminal_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        terminal_shape = str(row.get("terminal_shape", ""))
        if terminal_shape not in grouped:
            unique_row = dict(row)
            unique_row["occurrence_count"] = 0
            unique_row["samples"] = []
            grouped[terminal_shape] = unique_row
        unique_row = grouped[terminal_shape]
        unique_row["occurrence_count"] = int(unique_row.get("occurrence_count", 0)) + 1
        samples = unique_row.get("samples")
        sample = str(row.get("sample", ""))
        if isinstance(samples, list) and sample and sample not in samples:
            samples.append(sample)
    out: list[dict[str, object]] = []
    for unique_row in grouped.values():
        samples = unique_row.get("samples")
        if isinstance(samples, list):
            unique_row["samples"] = "; ".join(str(sample) for sample in samples[:8])
        out.append(unique_row)
    return sorted(
        out,
        key=lambda row: (-int(row.get("occurrence_count", 0)), str(row.get("terminal_shape", ""))),
    )


def _write_unique_terminal_rows(path: Path, rows: list[dict[str, object]]) -> None:
    columns = (
        "terminal_shape",
        "occurrence_count",
        "terminal_detail",
        "terminal_op",
        "terminal_cycle_category",
        "terminal_resolution",
        "terminal_feature_signature",
        "explain_reason",
        "open_leaf_keys",
        "self_open_leaf_keys",
        "unexpanded_leaf_keys",
        "self_unexpanded_leaf_keys",
        "probe_status",
        "legacy_strict_verdict",
        "legacy_reason",
        "layers",
        "occupied",
        "crystals",
        "pins",
        "solids",
        "samples",
    )
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(_tsv_cell(row.get(column, "")) for column in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _terminal_signature_rows(unique_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in unique_rows:
        signature = str(row.get("terminal_feature_signature", ""))
        if signature not in grouped:
            grouped[signature] = {
                "terminal_feature_signature": signature,
                "occurrence_count": 0,
                "unique_shape_count": 0,
                "terminal_cycle_category": row.get("terminal_cycle_category", ""),
                "terminal_resolution": row.get("terminal_resolution", ""),
                "explain_reason": row.get("explain_reason", ""),
                "open_leaf_keys": row.get("open_leaf_keys", ""),
                "self_open_leaf_keys": row.get("self_open_leaf_keys", ""),
                "unexpanded_leaf_keys": row.get("unexpanded_leaf_keys", ""),
                "self_unexpanded_leaf_keys": row.get("self_unexpanded_leaf_keys", ""),
                "probe_statuses": set(),
                "terminal_shapes": [],
                "samples": [],
            }
        signature_row = grouped[signature]
        signature_row["occurrence_count"] = int(signature_row.get("occurrence_count", 0)) + int(
            row.get("occurrence_count", 0)
        )
        signature_row["unique_shape_count"] = int(signature_row.get("unique_shape_count", 0)) + 1
        probe_status = str(row.get("probe_status", ""))
        if probe_status:
            statuses = signature_row.get("probe_statuses")
            if isinstance(statuses, set):
                statuses.add(probe_status)
        shapes = signature_row.get("terminal_shapes")
        if isinstance(shapes, list):
            shapes.append(str(row.get("terminal_shape", "")))
        samples = signature_row.get("samples")
        if isinstance(samples, list):
            for sample in str(row.get("samples", "")).split("; "):
                if sample and sample not in samples:
                    samples.append(sample)
    out: list[dict[str, object]] = []
    for signature_row in grouped.values():
        statuses = signature_row.get("probe_statuses")
        if isinstance(statuses, set):
            signature_row["probe_statuses"] = ",".join(sorted(statuses))
        shapes = signature_row.get("terminal_shapes")
        if isinstance(shapes, list):
            signature_row["terminal_shapes"] = "; ".join(shapes[:8])
        samples = signature_row.get("samples")
        if isinstance(samples, list):
            signature_row["samples"] = "; ".join(samples[:8])
        out.append(signature_row)
    return sorted(
        out,
        key=lambda row: (
            -int(row.get("occurrence_count", 0)),
            -int(row.get("unique_shape_count", 0)),
            str(row.get("terminal_feature_signature", "")),
        ),
    )


def _write_terminal_signature_rows(path: Path, rows: list[dict[str, object]]) -> None:
    columns = (
        "terminal_feature_signature",
        "occurrence_count",
        "unique_shape_count",
        "terminal_cycle_category",
        "terminal_resolution",
        "explain_reason",
        "open_leaf_keys",
        "self_open_leaf_keys",
        "unexpanded_leaf_keys",
        "self_unexpanded_leaf_keys",
        "probe_statuses",
        "terminal_shapes",
        "samples",
    )
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(_tsv_cell(row.get(column, "")) for column in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _leaf_features_from_code(code: str) -> dict[str, int]:
    shape = Shape.from_string(code)
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


def _tsv_cell(value: object) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _random_shape_samples(args: argparse.Namespace) -> list[tuple[str, str]]:
    rng = random.Random(args.seed)
    layer_pool = ["".join(chars) for chars in product(args.alphabet, repeat=4)]
    samples: list[tuple[str, str]] = []
    attempts = 0
    while len(samples) < args.samples:
        attempts += 1
        if attempts > args.samples * 200:
            raise RuntimeError("could not collect enough samples")
        depth = rng.randint(args.min_layers, args.max_layers)
        code = ":".join(rng.choice(layer_pool) for _ in range(depth))
        if set(code.replace(":", "")) == {"-"}:
            continue
        if args.stable_only:
            try:
                shape = Shape.from_string(code)
                if simplify_shape(repr(shape.apply_physics())) != simplify_shape(repr(shape)):
                    continue
            except Exception:
                continue
        samples.append((code, ""))
    return samples


def _load_pair_samples(args: argparse.Namespace) -> list[tuple[str, str]]:
    samples: list[tuple[str, str]] = []
    for raw_line in args.pairs_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            left, right = line.split("\t", 1)
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            left, right = parts[0], parts[1]
        target = left.removeprefix("T=")
        predecessor = right.removeprefix("A=").removeprefix("P=")
        if sfa.bitmask_push_pin(sfa.normalize_code(predecessor), args.validate_layers) != sfa.normalize_code(target):
            print(f"pair_push_mismatch={target}\t{predecessor}")
            if args.fail_on_validation_failure:
                samples.append((target, predecessor))
            continue
        samples.append((target, predecessor))
    return samples


def _load_shape_samples(path: Path) -> list[tuple[str, str]]:
    rows = path.read_text(encoding="utf-8").splitlines()
    if not rows:
        return []
    header = rows[0].split("\t")
    preferred_columns = ("leaf_shape", "target", "shape", "code")
    column_index: int | None = None
    if len(header) > 1:
        for column in preferred_columns:
            if column in header:
                column_index = header.index(column)
                data_rows = rows[1:]
                break
        else:
            data_rows = rows
    else:
        data_rows = rows
    if column_index is None:
        column_index = 0

    samples: list[tuple[str, str]] = []
    for raw_line in data_rows:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) <= column_index:
            continue
        shape = parts[column_index].removeprefix("T=").removeprefix("shape=").removeprefix("code=")
        if shape:
            samples.append((shape, ""))
    return samples


def _audit_mode(args: argparse.Namespace) -> str:
    if args.pairs_file:
        return "pairs"
    if getattr(args, "shapes_file", None):
        return "shapes"
    return "random_shapes"


def _sample_label(code: str, predecessor: str) -> str:
    if predecessor:
        return f"T={code}\tP={predecessor}"
    return code


def _filter_samples(
    args: argparse.Namespace,
    samples: list[tuple[str, str]],
    verdict_cache: dict[str, tuple[bool, str]],
) -> list[tuple[str, str]]:
    if args.target_verdict == "all":
        return samples
    filtered: list[tuple[str, str]] = []
    for code, predecessor in samples:
        possible, _reason = _target_verdict(code, verdict_cache)
        if args.target_verdict == "possible" and possible:
            filtered.append((code, predecessor))
        elif args.target_verdict == "not-possible" and not possible:
            filtered.append((code, predecessor))
    return filtered


def _dedupe_samples(samples: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for code, predecessor in samples:
        try:
            code_key = simplify_shape(repr(Shape.from_string(code)))
        except Exception:
            code_key = code
        try:
            predecessor_key = sfa.normalize_code(predecessor) if predecessor else ""
        except Exception:
            predecessor_key = predecessor
        key = (code_key, predecessor_key)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((code, predecessor))
    return deduped


def _target_verdict(code: str, verdict_cache: dict[str, tuple[bool, str]]) -> tuple[bool, str]:
    normalized = sfa.normalize_code(code)
    if normalized not in verdict_cache:
        verdict_cache[normalized] = sfa.claw_verify_status(normalized)
    return verdict_cache[normalized]


def _target_verdict_key(code: str, verdict_cache: dict[str, tuple[bool, str]]) -> str:
    verdict, reason = _target_verdict(code, verdict_cache)
    return f"{'claw_possible' if verdict else 'claw_not_possible'}:{reason}"


def _apply_gate_profile(args: argparse.Namespace) -> argparse.Namespace:
    profile = getattr(args, "gate_profile", "none")
    if profile == "none":
        return args

    if getattr(args, "complex_probe_pair_limit", None) is None:
        args.complex_probe_pair_limit = 60

    for field in (
        "fail_on_validation_failure",
        "fail_on_actionable_complex_input",
        "fail_on_unknown_complex_class",
        "fail_on_truncated_probe",
        "fail_on_actionable_shallow_possible",
        "fail_on_reachable_shallow_probe",
        "fail_on_reachable_terminal_probe",
        "fail_on_truncated_terminal_probe",
        "fail_on_unknown_shallow_class",
    ):
        setattr(args, field, True)

    if profile in {"possible-structural", "strict"}:
        args.fail_on_unresolved_possible = True
        args.fail_on_structural_unresolved_possible = True

    if profile == "strict":
        args.fail_on_complex_input = True
        args.fail_on_shallow_input = True
        args.fail_on_terminal_boundary = True
        args.fail_on_strict_unresolved_possible = True

    args.probe_shallow_leaves = True
    args.probe_terminal_boundaries = True
    if getattr(args, "terminal_probe_pair_limit", None) is None:
        args.terminal_probe_pair_limit = 60

    return args


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit claw production graph generation quality.")
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--pairs-file", type=Path)
    parser.add_argument("--shapes-file", type=Path)
    parser.add_argument("--target-verdict", choices=("all", "possible", "not-possible"), default="all")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--alphabet", default="SPc-")
    parser.add_argument("--min-layers", type=int, default=1)
    parser.add_argument("--max-layers", type=int, default=3)
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--validate-layers", type=int, default=6)
    parser.add_argument("--max-examples", type=int, default=5)
    parser.add_argument("--max-leaf-examples", type=int, default=4)
    parser.add_argument("--graph-lines", type=int, default=15)
    parser.add_argument("--probe-max-steps", type=int, default=3)
    parser.add_argument("--probe-max-states", type=int, default=12000)
    parser.add_argument("--probe-pair-limit", type=int, default=180)
    parser.add_argument("--complex-probe-max-steps", type=int)
    parser.add_argument("--complex-probe-max-states", type=int)
    parser.add_argument("--complex-probe-pair-limit", type=int)
    parser.add_argument("--shallow-probe-pair-limit", type=int, default=60)
    parser.add_argument("--terminal-probe-pair-limit", type=int)
    parser.add_argument("--probe-shallow-leaves", action="store_true")
    parser.add_argument("--probe-terminal-boundaries", action="store_true")
    parser.add_argument("--dedupe-samples", action="store_true")
    parser.add_argument("--gate-profile", choices=("none", "known", "possible-structural", "strict"), default="none")
    parser.add_argument("--stable-only", action="store_true")
    parser.add_argument("--write-filtered-pairs", type=Path)
    parser.add_argument("--write-summary-json", type=Path)
    parser.add_argument("--write-unsupported-leaves", type=Path)
    parser.add_argument("--write-shallow-leaves", type=Path)
    parser.add_argument("--write-low-depth-shallow-leaves", type=Path)
    parser.add_argument("--write-terminal-boundaries", type=Path)
    parser.add_argument("--write-unique-terminal-boundaries", type=Path)
    parser.add_argument("--write-terminal-signatures", type=Path)
    parser.add_argument("--low-depth-shallow-threshold", type=int)
    parser.add_argument("--fail-on-validation-failure", action="store_true")
    parser.add_argument("--fail-on-complex-input", action="store_true")
    parser.add_argument("--fail-on-actionable-complex-input", action="store_true")
    parser.add_argument("--fail-on-unknown-complex-class", action="store_true")
    parser.add_argument("--fail-on-truncated-probe", action="store_true")
    parser.add_argument("--fail-on-unresolved-possible", action="store_true")
    parser.add_argument("--fail-on-structural-unresolved-possible", action="store_true")
    parser.add_argument("--fail-on-strict-unresolved-possible", action="store_true")
    parser.add_argument("--fail-on-terminal-boundary", action="store_true")
    parser.add_argument("--fail-on-shallow-possible", action="store_true")
    parser.add_argument("--fail-on-actionable-shallow-possible", action="store_true")
    parser.add_argument("--fail-on-reachable-shallow-probe", action="store_true")
    parser.add_argument("--fail-on-reachable-terminal-probe", action="store_true")
    parser.add_argument("--fail-on-truncated-terminal-probe", action="store_true")
    parser.add_argument("--fail-on-unknown-shallow-class", action="store_true")
    parser.add_argument("--fail-on-shallow-depth-below", type=int)
    parser.add_argument("--fail-on-shallow-input", action="store_true")
    return audit(_apply_gate_profile(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
