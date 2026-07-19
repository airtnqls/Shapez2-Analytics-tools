from pathlib import Path
from argparse import Namespace
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from data_operations import simplify_shape
import symbolic_frontier_automaton as sfa
from claw_production_graph import (
    assess_production_graph,
    bounded_forward_probe,
    build_claw_pinpush_graph,
    build_shape_production_graph,
    diagnose_complex_inputs,
    diagnose_shallow_inputs,
    diagnose_terminal_leaves,
    graph_quality_stats,
    input_leaf_examples,
    input_leaf_kinds,
    is_impossible_rule_closed_complex_diagnostic,
    is_impossible_rule_closed_shallow_diagnostic,
    is_known_unsupported_complex_diagnostic,
    pinpush_overall_verdict,
    render_graph,
    validate_graph,
)
from audit_claw_production_graph import audit, _apply_gate_profile
import audit_claw_production_graph as audit_module
import claw_production_graph as graph_module


class ClawPinPushCounterexampleTests(unittest.TestCase):
    def test_audit_gate_profiles_enable_expected_fail_flags(self) -> None:
        flag_names = (
            "fail_on_validation_failure",
            "fail_on_complex_input",
            "fail_on_actionable_complex_input",
            "fail_on_unknown_complex_class",
            "fail_on_truncated_probe",
            "fail_on_unresolved_possible",
            "fail_on_structural_unresolved_possible",
            "fail_on_strict_unresolved_possible",
            "fail_on_terminal_boundary",
            "fail_on_shallow_possible",
            "fail_on_actionable_shallow_possible",
            "fail_on_reachable_shallow_probe",
            "fail_on_reachable_terminal_probe",
            "fail_on_truncated_terminal_probe",
            "fail_on_unknown_shallow_class",
            "fail_on_shallow_input",
            "probe_shallow_leaves",
            "probe_terminal_boundaries",
        )

        def profile_flags(profile: str) -> dict[str, bool]:
            args = Namespace(gate_profile=profile, **{name: False for name in flag_names})
            _apply_gate_profile(args)
            return {name: bool(getattr(args, name)) for name in flag_names}

        known = profile_flags("known")
        self.assertTrue(known["fail_on_validation_failure"])
        self.assertTrue(known["fail_on_unknown_complex_class"])
        self.assertTrue(known["fail_on_unknown_shallow_class"])
        self.assertTrue(known["fail_on_reachable_terminal_probe"])
        self.assertTrue(known["fail_on_truncated_terminal_probe"])
        self.assertTrue(known["probe_shallow_leaves"])
        self.assertTrue(known["probe_terminal_boundaries"])
        self.assertFalse(known["fail_on_unresolved_possible"])
        self.assertFalse(known["fail_on_complex_input"])
        self.assertFalse(known["fail_on_shallow_input"])

        structural = profile_flags("possible-structural")
        self.assertTrue(structural["fail_on_unresolved_possible"])
        self.assertTrue(structural["fail_on_structural_unresolved_possible"])
        self.assertFalse(structural["fail_on_strict_unresolved_possible"])

        strict = profile_flags("strict")
        self.assertTrue(strict["fail_on_complex_input"])
        self.assertTrue(strict["fail_on_shallow_input"])
        self.assertTrue(strict["fail_on_terminal_boundary"])
        self.assertTrue(strict["fail_on_strict_unresolved_possible"])

        args = Namespace(
            gate_profile="known",
            complex_probe_pair_limit=None,
            terminal_probe_pair_limit=None,
            **{name: False for name in flag_names},
        )
        _apply_gate_profile(args)
        self.assertEqual(args.complex_probe_pair_limit, 60)
        self.assertEqual(args.terminal_probe_pair_limit, 60)
        explicit_args = Namespace(
            gate_profile="known",
            complex_probe_pair_limit=120,
            terminal_probe_pair_limit=77,
            **{name: False for name in flag_names},
        )
        _apply_gate_profile(explicit_args)
        self.assertEqual(explicit_args.complex_probe_pair_limit, 120)
        self.assertEqual(explicit_args.terminal_probe_pair_limit, 77)

    def test_detailed_six_layer_target_has_pinpush_predecessor(self) -> None:
        target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        target_simple = "PSPP:SSS-:P-P-:P-S-:P---:ScS-"
        predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"

        self.assertEqual(simplify_shape(target), target_simple)
        self.assertEqual(sfa.normalize_code(target), target_simple)
        self.assertEqual(sfa.bitmask_push_pin(predecessor, 6), target_simple)

        candidates = sfa.bitmask_claw_delta_grammar_inverse_push_pin_candidates(target, 6)
        self.assertIn(predecessor, candidates)
        self.assertEqual(sfa.claw_verify_status(target), (True, "claw_possible"))

    def test_counterexample_production_graph_is_generated_and_validated(self) -> None:
        target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"
        explanation = sfa.explain_shape_dict(target, 6)

        graph = build_claw_pinpush_graph(
            target,
            predecessor,
            6,
            explanation["decomposition_tree"] if explanation else None,
        )
        valid, reason = validate_graph(graph, 6)
        rendered = "\n".join(render_graph(graph))

        self.assertTrue(valid, reason)
        self.assertIn("[pin_push]", rendered)
        self.assertIn("[swap]", rendered)
        self.assertIn("[cut_east]", rendered)
        self.assertNotIn("graph_for_predecessor", rendered)
        self.assertGreaterEqual(graph_quality_stats(graph)["input_leaves"], 1)
        self.assertEqual(graph_quality_stats(graph)["complex_input_leaves"], 0)
        self.assertLessEqual(graph_quality_stats(graph)["shallow_input_leaves"], 2)

    def test_counterexample_production_graph_is_deterministic_across_depths(self) -> None:
        target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"
        shallow = graph_quality_stats(build_claw_pinpush_graph(target, predecessor, 6, max_depth=5))
        first = graph_quality_stats(build_claw_pinpush_graph(target, predecessor, 6, max_depth=6))
        second = graph_quality_stats(build_claw_pinpush_graph(target, predecessor, 6, max_depth=6))

        self.assertEqual(first, second)
        self.assertGreater(first["nodes"], shallow["nodes"])
        self.assertGreater(first["max_depth"], shallow["max_depth"])
        self.assertGreater(first["max_input_leaf_depth"], shallow["max_input_leaf_depth"])
        self.assertEqual(first["complex_input_leaves"], 0)

    def test_shape_production_graph_uses_real_stack_operation(self) -> None:
        graph = build_shape_production_graph("P---:S---", max_depth=4)
        valid, reason = validate_graph(graph, 6)
        rendered = "\n".join(render_graph(graph))

        self.assertTrue(valid, reason)
        self.assertIn("[stack]", rendered)
        self.assertIn("[input]", rendered)

    def test_shape_production_graph_uses_crystal_generator_operation(self) -> None:
        graph = build_shape_production_graph("cccc", max_depth=4)
        valid, reason = validate_graph(graph, 6)
        rendered = "\n".join(render_graph(graph))

        self.assertTrue(valid, reason)
        self.assertIn("[crystal_generator", rendered)
        self.assertEqual(graph_quality_stats(graph)["complex_input_leaves"], 0)

    def test_closed_corner_swap_decomposition_becomes_production_graph(self) -> None:
        graph = build_shape_production_graph("S--S:S--S:S--S:c--c:c--c", max_depth=8)
        valid, reason = validate_graph(graph, 6)
        quality = graph_quality_stats(graph)
        rendered = "\n".join(render_graph(graph))

        self.assertTrue(valid, reason)
        self.assertEqual(quality["terminal_leaves"], 0, rendered)
        self.assertEqual(quality["input_leaves"], 0, rendered)
        self.assertIn("[swap]", rendered)
        self.assertIn("[corner]", rendered)
        self.assertEqual(diagnose_terminal_leaves(graph), [])

    def test_quality_regressions_for_known_complex_shapes(self) -> None:
        for code in ("cScP", "-PSS", "cccc:cc-c", "-cPc:----", "PcPc:PPSc:----"):
            with self.subTest(code=code):
                graph = build_shape_production_graph(code, max_depth=5)
                valid, reason = validate_graph(graph, 6)
                quality = graph_quality_stats(graph)
                rendered = "\n".join(render_graph(graph))

                self.assertTrue(valid, reason)
                self.assertEqual(quality["complex_input_leaves"], 0, rendered)

    def test_unresolved_complex_inputs_are_diagnosed(self) -> None:
        graph = build_shape_production_graph("-c-S:SPSc", max_depth=6)
        diagnostics = diagnose_complex_inputs(graph)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["reason"], "no_supported_reverse_candidate")
        self.assertEqual(diagnostics[0]["kind"], "complex")
        self.assertEqual(diagnostics[0]["unsupported_class"], "unsupported_crystal_solid_entangled")
        self.assertIn("extended_reverse_candidate_counts", diagnostics[0])
        self.assertIn("leaf_features", diagnostics[0])
        self.assertIn("bounded_forward_probe", diagnostics[0])
        self.assertEqual(diagnostics[0]["legacy_strict_verdict"], "impossible")
        self.assertEqual(diagnostics[0]["legacy_reason"], "Claw Rule1. 1F: P<2")
        self.assertTrue(is_impossible_rule_closed_complex_diagnostic(diagnostics[0]))
        self.assertIn(diagnostics[0]["bounded_forward_probe"]["status"], {"not_found_complete", "not_found_truncated"})
        if diagnostics[0]["bounded_forward_probe"]["status"] == "not_found_complete":
            self.assertFalse(is_known_unsupported_complex_diagnostic(diagnostics[0]))

    def test_legacy_impossible_entangled_complex_cases_are_closed(self) -> None:
        cases = {
            "-P--:ScSS:PccP": "Claw Rule1. 1F: P<2",
            "-cc-:SPcS:cSc-": "Claw Rule1. 1F: P<2",
            "-S--:-cSc": "Quadrant 4: Corner Rule2. ^P*-+c violated",
            "---S:S-Sc": "Claw Rule1. 1F: P<2",
            "c-SS:P--P:PcSS": "Quadrant 2: Corner Rule2. ^P*-+c violated",
            "S-cc:PcP-:ccPS": "Quadrant 1: Corner Rule3. [^P]P.*c violated",
            "P-c-:SS-c": "Quadrant 4: Corner Rule2. ^P*-+c violated",
        }

        for code, reason in cases.items():
            with self.subTest(code=code):
                self.assertEqual(sfa.legacy_verdict(code)[1], "impossible")
                self.assertEqual(sfa.legacy_verdict(code)[3], reason)
                graph = build_shape_production_graph(code, max_depth=6)
                diagnostics = diagnose_complex_inputs(graph)
                closed = [
                    diagnostic
                    for diagnostic in diagnostics
                    if diagnostic.get("unsupported_class") == "unsupported_crystal_solid_entangled"
                ]
                self.assertTrue(closed)
                self.assertTrue(all(is_impossible_rule_closed_complex_diagnostic(diagnostic) for diagnostic in closed))
                self.assertTrue(all(diagnostic["legacy_reason"] == reason for diagnostic in closed))

    def test_representative_six_layer_claw_target_remains_possible(self) -> None:
        target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"

        self.assertEqual(sfa.claw_verify_status(target), (True, "claw_possible"))
        self.assertEqual(sfa.strict_legacy_verdict_to_symbolic(target)[0], "unknown")

    def test_bounded_forward_probe_finds_simple_crystal_generator_target(self) -> None:
        probe = bounded_forward_probe("cccc", max_steps=1)

        self.assertTrue(probe["reachable"])
        self.assertEqual(probe["status"], "reachable")
        self.assertLessEqual(probe["steps"], 1)
        self.assertIn("op_counts", probe)
        self.assertGreater(probe["op_counts"].get("crystal_generator r", 0), 0)

    def test_bounded_forward_probe_returns_independent_cached_results(self) -> None:
        first = bounded_forward_probe("cccc", max_steps=1)
        first["status"] = "mutated"

        second = bounded_forward_probe("cccc", max_steps=1)

        self.assertEqual(second["status"], "reachable")

    def test_known_unsupported_complex_rejects_reachable_or_truncated_probe(self) -> None:
        base = {
            "reason": "no_supported_reverse_candidate",
            "unsupported_class": "unsupported_crystal_solid_entangled",
        }

        self.assertTrue(
            is_known_unsupported_complex_diagnostic(
                {**base, "bounded_forward_probe": {"status": "not_found_complete"}}
            )
        )
        self.assertFalse(
            is_known_unsupported_complex_diagnostic(
                {**base, "bounded_forward_probe": {"status": "reachable"}}
            )
        )
        self.assertFalse(
            is_known_unsupported_complex_diagnostic(
                {**base, "bounded_forward_probe": {"status": "not_found_truncated"}}
            )
        )

    def test_explicit_predecessor_graph_is_not_hidden_by_impossible_target_tree(self) -> None:
        target = "-PPP:--PS:--PS:--cS:-ScP:Sc--"
        predecessor = "--PS:--PS:-PcS:-ScP:Sc-c:---c"
        explanation = sfa.explain_shape_dict(target, 6)

        graph = build_claw_pinpush_graph(
            target,
            predecessor,
            6,
            explanation["decomposition_tree"] if explanation else None,
            max_depth=6,
        )
        rendered = "\n".join(render_graph(graph))
        quality = graph_quality_stats(graph)

        self.assertIn("[pin_push]", rendered)
        self.assertNotIn("[impossible:", rendered)
        self.assertEqual(quality["complex_input_leaves"], 1)

    def test_unsupported_symbolic_tree_does_not_validate_as_production(self) -> None:
        target = "-PPP:--PS:--PS:--cS:-ScP:Sc--"
        explanation = sfa.explain_shape_dict(target, 6)
        graph = build_claw_pinpush_graph(
            target,
            "",
            6,
            explanation["decomposition_tree"] if explanation else None,
            max_depth=6,
        )

        valid, reason = validate_graph(graph, 6)
        self.assertFalse(valid)
        self.assertIn("unsupported production op", reason)

    def test_input_leaf_kinds_are_reported(self) -> None:
        graph = build_shape_production_graph("P---:S---", max_depth=4)
        kinds = input_leaf_kinds(graph)
        examples = input_leaf_examples(graph)
        quality = graph_quality_stats(graph)

        self.assertEqual(sum(kinds.values()), quality["input_leaves"])
        self.assertGreaterEqual(kinds.get("single_column", 0) + kinds.get("single_cell", 0), 1)
        self.assertIn("input_leaf_kinds", quality)
        self.assertTrue(any(examples.values()))
        shallow_diagnostics = diagnose_shallow_inputs(graph)
        self.assertTrue(all(item["kind"] != "complex" for item in shallow_diagnostics))

    def test_shallow_diagnostics_distinguish_no_quality_gain(self) -> None:
        graph = build_shape_production_graph("cS--:cP--:cP--:cP--:cS--:c---", max_depth=6)
        diagnostics = diagnose_shallow_inputs(graph)
        quality = graph_quality_stats(graph)
        rendered = "\n".join(render_graph(graph))

        self.assertEqual(diagnostics, [])
        self.assertEqual(quality["shallow_input_leaves"], 0)
        self.assertEqual(quality["complex_input_leaves"], 0)
        self.assertIn("[corner]", rendered)

    def test_legacy_impossible_shallow_leaf_is_rule_closed(self) -> None:
        graph = build_shape_production_graph("--P-:--cc", max_depth=8)
        diagnostics = diagnose_shallow_inputs(graph, include_probe=True)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["kind"], "west_half")
        self.assertEqual(diagnostics[0]["legacy_strict_verdict"], "impossible")
        self.assertEqual(diagnostics[0]["legacy_reason"], "Quadrant 4: Corner Rule2. ^P*-+c violated")
        self.assertTrue(is_impossible_rule_closed_shallow_diagnostic(diagnostics[0]))

    def test_shallow_leaf_pinpush_refinement_pushes_low_depth_leaf_deeper(self) -> None:
        graph = build_shape_production_graph("--P-----:--P-----:Sucw----:Su------:cw------", max_depth=8)
        valid, reason = validate_graph(graph, 6)
        rendered = "\n".join(render_graph(graph))
        quality = graph_quality_stats(graph)

        self.assertTrue(valid, reason)
        self.assertIn("[pin_push]", rendered)
        self.assertEqual(quality["complex_input_leaves"], 0)
        self.assertEqual(quality["shallow_input_leaves"], 0)
        self.assertEqual(quality["terminal_leaves"], 1)

    def test_common_assessment_controls_pinpush_verdict(self) -> None:
        resolved_graph = build_claw_pinpush_graph(
            "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--",
            "S-Sc:PScc:PSPc:P-Sc:ScSc:---c",
            6,
            max_depth=8,
        )
        unresolved_graph = build_claw_pinpush_graph(
            "-PPP:--PS:--PS:--cS:-ScP:Sc--",
            "--PS:--PS:-PcS:-ScP:Sc-c:---c",
            6,
            max_depth=6,
        )

        resolved = assess_production_graph(resolved_graph, 6)
        unresolved = assess_production_graph(unresolved_graph, 6)

        self.assertTrue(resolved["resolved"])
        self.assertTrue(resolved["structural_resolved"])
        self.assertFalse(resolved["strict_resolved"])
        self.assertFalse(unresolved["resolved"])
        self.assertFalse(unresolved["structural_resolved"])
        self.assertFalse(unresolved["strict_resolved"])
        self.assertEqual(
            pinpush_overall_verdict(True, True, True, "possible", "possible"),
            "possible",
        )
        self.assertEqual(
            pinpush_overall_verdict(False, True, False, "unknown", "unknown"),
            "unknown",
        )

    def test_audit_writes_summary_and_filtered_pairs_for_possible_targets(self) -> None:
        possible_target = "--PP:--PS:--PS:-ScS:-S--:Sc--"
        possible_predecessor = "--PS:--PS:-ScS:-S-c:Sc-c:---c"
        impossible_target = "-PPP:--PS:--PS:--cS:-ScP:Sc--"
        impossible_predecessor = "--PS:--PS:-PcS:-ScP:Sc-c:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            pairs_file = temp_dir / "pairs.tsv"
            summary_file = temp_dir / "summary.json"
            filtered_file = temp_dir / "filtered.tsv"
            pairs_file.write_text(
                "\n".join(
                    (
                        f"{possible_target}\t{possible_predecessor}",
                        f"{impossible_target}\t{impossible_predecessor}",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=8,
                max_examples=2,
                max_leaf_examples=2,
                graph_lines=4,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=filtered_file,
                write_summary_json=summary_file,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
        fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            filtered_lines = filtered_file.read_text(encoding="utf-8").splitlines()

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["loaded_samples"], 2)
        self.assertEqual(summary["filtered_samples"], 1)
        self.assertEqual(summary["probe_config"]["probe_pair_limit"], 180)
        self.assertEqual(summary["probe_config"]["complex_probe_max_steps"], 3)
        self.assertEqual(summary["probe_config"]["complex_probe_max_states"], 12000)
        self.assertEqual(summary["probe_config"]["complex_probe_pair_limit"], 180)
        self.assertEqual(summary["probe_config"]["shallow_probe_pair_limit"], 180)
        self.assertFalse(summary["probe_config"]["probe_shallow_leaves"])
        self.assertEqual(summary["totals"]["shallow_input_leaves"], 0)
        self.assertGreater(summary["totals"]["terminal_leaves"], 0)
        self.assertEqual(summary["totals"]["terminal_leaves"], summary["totals"]["legacy_possible_terminal_leaves"])
        self.assertGreaterEqual(summary["totals"]["max_depth"], 1)
        if summary["totals"]["input_leaves"]:
            self.assertGreaterEqual(summary["totals"]["max_input_leaf_depth"], 1)
        self.assertEqual(summary["actionable_complex_cases"], 0)
        self.assertEqual(summary["actionable_complex_leaves"], 0)
        self.assertEqual(summary["truncated_probe_cases"], 0)
        self.assertEqual(summary["unsupported_classes"], {})
        self.assertEqual(summary["bounded_forward_probe"], {})
        self.assertEqual(summary["bounded_forward_probe_ops"], {})
        self.assertEqual(summary["bounded_forward_probe_pruned_ops"], {})
        self.assertEqual(summary["totals"]["structural_resolved_graphs"], 1)
        self.assertEqual(summary["totals"]["structural_unresolved_graphs"], 0)
        self.assertEqual(summary["totals"]["strict_resolved_graphs"], 0)
        self.assertEqual(summary["unresolved_possible_cases"], 0)
        self.assertEqual(summary["structural_unresolved_possible_cases"], 0)
        self.assertEqual(summary["strict_unresolved_possible_cases"], 1)
        self.assertEqual(summary["terminal_boundary_cases"], 1)
        self.assertEqual(summary["known_terminal_boundary_cases"], 0)
        self.assertEqual(summary["actionable_terminal_boundary_cases"], 0)
        self.assertEqual(summary["unprobed_terminal_boundary_cases"], 1)
        self.assertEqual(summary["terminal_unique_shapes"], 2)
        self.assertEqual(len(summary["terminal_shape_counts"]), 2)
        self.assertEqual(
            sum(int(count) for count in summary["terminal_feature_signatures"].values()),
            summary["totals"]["terminal_leaves"],
        )
        self.assertEqual(
            sum(int(count) for count in summary["terminal_unique_feature_signatures"].values()),
            summary["terminal_unique_shapes"],
        )
        self.assertEqual(summary["shallow_possible_cases"], 0)
        self.assertEqual(summary["shallow_possible_leaves"], summary["totals"]["shallow_input_leaves"])
        self.assertEqual(summary["actionable_shallow_possible_cases"], 0)
        self.assertEqual(summary["actionable_shallow_possible_leaves"], 0)
        self.assertEqual(summary["unknown_shallow_cases"], 0)
        self.assertEqual(summary["target_verdict_resolution"], {"claw_possible:claw_possible|resolved": 1})
        self.assertEqual(
            summary["target_verdict_structural_resolution"],
            {"claw_possible:claw_possible|structural_resolved": 1},
        )
        self.assertEqual(
            summary["target_verdict_strict_resolution"],
            {"claw_possible:claw_possible|strict_unresolved": 1},
        )
        self.assertEqual(summary["strict_gap_resolutions"], {"terminal_unprobed": 1})
        self.assertEqual(
            summary["target_verdict_strict_gap_resolution"],
            {"claw_possible:claw_possible|terminal_unprobed": 1},
        )
        self.assertIn("input_leaf_kind_examples", summary)
        self.assertEqual(summary["actionable_complex_examples"], [])
        self.assertEqual(summary["shallow_possible_examples"], [])
        self.assertEqual(summary["actionable_shallow_possible_examples"], [])
        self.assertIn("shallow_diagnostic_reasons", summary)
        self.assertIn("shallow_classes", summary)
        self.assertEqual(summary["shallow_resolutions"], {})
        self.assertEqual(summary["shallow_feature_signatures"], {})
        self.assertIn("shallow_leaf_depths", summary)
        self.assertEqual(sum(int(count) for count in summary["shallow_leaf_depths"].values()), 0)
        self.assertIn("shallow_best_candidate_ops", summary)
        self.assertIn("shallow_candidate_preserves_leaf", summary)
        self.assertIn("shallow_terminal_hints", summary)
        self.assertEqual(sum(int(count) for count in summary["terminal_ops"].values()), summary["totals"]["terminal_leaves"])
        self.assertEqual(
            sum(int(count) for count in summary["terminal_explain_reasons"].values()),
            summary["totals"]["terminal_leaves"],
        )
        self.assertEqual(
            sum(int(count) for count in summary["terminal_open_leaf_keys"].values()),
            summary["totals"]["terminal_leaves"],
        )
        self.assertEqual(summary["terminal_self_open_leaf_cases"], 1)
        self.assertEqual(summary["terminal_self_unexpanded_leaf_cases"], 1)
        self.assertEqual(
            sum(int(count) for count in summary["terminal_cycle_categories"].values()),
            summary["totals"]["terminal_leaves"],
        )
        self.assertEqual(
            sum(int(count) for count in summary["terminal_resolutions"].values()),
            summary["totals"]["terminal_leaves"],
        )
        self.assertEqual(summary["terminal_cycle_categories"]["self_open_leaf_cycle"], 1)
        self.assertEqual(summary["terminal_cycle_categories"]["self_unexpanded_leaf_cycle"], 1)
        self.assertEqual(summary["terminal_resolutions"]["self_open_leaf_cycle"], 1)
        self.assertEqual(summary["terminal_resolutions"]["self_unexpanded_leaf_cycle"], 1)
        self.assertIn("terminal_legacy_possible_swap_limited", summary["terminal_ops"])
        self.assertIn("swap_limited", summary["terminal_explain_reasons"])
        self.assertTrue(
            {
                '{"stack_input:swap_cut_12_34_left": 1}',
                '{"stack_input:swap_cut_12_34_right": 1}',
            }
            & set(summary["terminal_open_leaf_keys"])
        )
        self.assertTrue(
            {
                '{"stack_input:swap_cut_12_34_left": 1}',
                '{"stack_input:swap_cut_12_34_right": 1}',
            }
            & set(summary["terminal_self_open_leaf_keys"])
        )
        self.assertIn('{"swap:swap_cut_12_34_right_swappable_input": 1}', summary["terminal_unexpanded_leaf_keys"])
        self.assertIn(
            '{"swap:swap_cut_12_34_right_swappable_input": 1}',
            summary["terminal_self_unexpanded_leaf_keys"],
        )
        self.assertIn("complex_leaf_depths", summary)
        self.assertEqual(summary["strict_unresolved_possible_examples"][0]["strict_reason"], "legacy_possible_terminal")
        self.assertEqual(summary["terminal_boundary_examples"][0]["quality"]["terminal_leaves"], 2)
        self.assertEqual(filtered_lines, [f"{possible_target}\t{possible_predecessor}"])

    def test_audit_can_fail_on_structural_unresolved_possible_targets(self) -> None:
        possible_target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        possible_predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            summary_file = Path(temp_dir_name) / "summary.json"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                probe_shallow_leaves=False,
                dedupe_samples=False,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_structural_unresolved_possible=True,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_input=False,
            )
            fake_assessment = {
                "valid": (True, "ok"),
                "quality": {
                    "nodes": 1,
                    "input_leaves": 1,
                    "complex_input_leaves": 0,
                    "shallow_input_leaves": 1,
                    "complex_input_shapes": [],
                    "shallow_input_shapes": ["Sc--:c---"],
                    "input_leaf_kinds": {"east_half": 1},
                    "ops": {"input": 1},
                },
                "diagnostics": [],
                "shallow_diagnostics": [{"reason": "candidate_exists_but_not_selected"}],
                "unknown_shallow_diagnostics": [{"reason": "candidate_exists_but_not_selected"}],
                "resolved": True,
                "structural_resolved": False,
                "strict_resolved": False,
            }

            with (
                mock.patch.object(audit_module, "assess_production_graph", return_value=fake_assessment),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["structural_unresolved_possible_cases"], 1)
        self.assertEqual(
            summary["target_verdict_structural_resolution"],
            {"claw_possible:claw_possible|structural_unresolved": 1},
        )

    def test_audit_keeps_bounded_probe_ops_separate_from_graph_ops(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )
            truncated_probe = {
                "reachable": False,
                "steps": 3,
                "steps_completed": 2,
                "states": 12000,
                "frontier": 9000,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {"stack": 10},
                "pruned_counts": {"pair_pre": 3},
                "target_features": {},
                "truncated": True,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("c-SS:P--P:PcSS", "")]),
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=truncated_probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["ops"], {"input": 1})
        self.assertEqual(summary["bounded_forward_probe"], {"not_found_truncated": 1})
        self.assertEqual(summary["truncated_probe_cases"], 1)
        self.assertGreater(summary["bounded_forward_probe_ops"]["stack"], 0)
        self.assertIn("bounded_forward_probe_pruned_ops", summary)
        self.assertIn("truncated_probe_examples", summary)

    def test_audit_writes_unsupported_leaf_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            unsupported_file = Path(temp_dir_name) / "unsupported.tsv"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                write_unsupported_leaves=unsupported_file,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )
            probe = {
                "reachable": False,
                "steps": 3,
                "steps_completed": 3,
                "states": 10,
                "frontier": 0,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {},
                "pruned_counts": {},
                "target_features": {},
                "truncated": False,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("-c-S:SPSc", "")]),
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            rows = unsupported_file.read_text(encoding="utf-8").splitlines()

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(len(rows), 2)
        self.assertIn("unsupported_class", rows[0])
        self.assertIn("unsupported_crystal_solid_entangled", rows[1])
        self.assertIn("not_found_complete", rows[1])

    def test_audit_reads_unsupported_leaf_corpus_as_shapes_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            shapes_file = Path(temp_dir_name) / "unsupported.tsv"
            summary_file = Path(temp_dir_name) / "summary.json"
            shapes_file.write_text(
                "\n".join(
                    (
                        "sample\ttarget\tpredecessor\tleaf_shape\tleaf_detail\tkind\treason\tunsupported_class",
                        "-c-S:SPSc\t-c-S:SPSc\t\t-c-S:SPSc\t--cw--Su:SuP-Sucw\tcomplex\tno_supported_reverse_candidate\tunsupported_crystal_solid_entangled",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            args = Namespace(
                pairs_file=None,
                shapes_file=shapes_file,
                target_verdict="all",
                samples=0,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["mode"], "shapes")
        self.assertEqual(summary["loaded_samples"], 1)
        self.assertEqual(summary["unsupported_classes"], {"unsupported_crystal_solid_entangled": 1})
        self.assertEqual(summary["complex_resolutions"], {"impossible_rule_closed": 1})
        self.assertEqual(summary["impossible_rule_closed_reasons"], {"Claw Rule1. 1F: P<2": 1})

    def test_audit_can_fail_on_unknown_complex_class(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                probe_shallow_leaves=False,
                dedupe_samples=False,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=True,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_input=False,
            )
            fake_graph = graph_module.ProductionNode("input", "ScSP")
            fake_assessment = {
                "valid": (True, "ok"),
                "quality": {
                    "nodes": 1,
                    "input_leaves": 1,
                    "complex_input_leaves": 1,
                    "shallow_input_leaves": 0,
                    "complex_input_shapes": ["ScSP"],
                    "shallow_input_shapes": [],
                    "input_leaf_kinds": {"complex": 1},
                    "ops": {"input": 1},
                },
                "diagnostics": [
                    {
                        "shape": "ScSP",
                        "detail": "ScSP",
                        "kind": "complex",
                        "reason": "no_supported_reverse_candidate",
                        "unsupported_class": "new_unknown_complex_class",
                    }
                ],
                "shallow_diagnostics": [],
                "unknown_shallow_diagnostics": [],
                "resolved": False,
                "structural_resolved": False,
                "strict_resolved": False,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("ScSP", "")]),
                mock.patch.object(audit_module, "build_shape_production_graph", return_value=fake_graph),
                mock.patch.object(audit_module, "assess_production_graph", return_value=fake_assessment),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["complex_resolutions"], {"unknown_or_actionable": 1})
        self.assertEqual(summary["unknown_complex_cases"], 1)

    def test_audit_counts_impossible_rule_closed_separately_from_unknown_complex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                write_low_depth_shallow_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=True,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_input=False,
            )
            fake_graph = graph_module.ProductionNode("input", "-P--:ScSS:PccP")
            fake_assessment = {
                "valid": (True, "ok"),
                "quality": {
                    "nodes": 1,
                    "max_depth": 0,
                    "input_leaves": 1,
                    "max_input_leaf_depth": 0,
                    "max_shallow_input_leaf_depth": 0,
                    "max_complex_input_leaf_depth": 0,
                    "complex_input_leaves": 1,
                    "shallow_input_leaves": 0,
                    "complex_input_shapes": ["-P--:ScSS:PccP"],
                    "shallow_input_shapes": [],
                    "input_leaf_kinds": {"complex": 1},
                    "ops": {"input": 1},
                },
                "diagnostics": [
                    {
                        "shape": "-P--:ScSS:PccP",
                        "detail": "-P--:ScSS:PccP",
                        "kind": "complex",
                        "reason": "no_supported_reverse_candidate",
                        "unsupported_class": "unsupported_crystal_solid_entangled",
                        "legacy_strict_verdict": "impossible",
                        "legacy_reason": "Claw Rule1. 1F: P<2",
                    }
                ],
                "shallow_diagnostics": [],
                "unknown_shallow_diagnostics": [],
                "resolved": False,
                "structural_resolved": False,
                "strict_resolved": False,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("-P--:ScSS:PccP", "")]),
                mock.patch.object(audit_module, "build_shape_production_graph", return_value=fake_graph),
                mock.patch.object(audit_module, "assess_production_graph", return_value=fake_assessment),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["complex_resolutions"], {"impossible_rule_closed": 1})
        self.assertEqual(summary["impossible_rule_closed_reasons"], {"Claw Rule1. 1F: P<2": 1})
        self.assertEqual(summary["unknown_complex_cases"], 0)

    def test_audit_can_dedupe_shape_corpus_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            shapes_file = Path(temp_dir_name) / "shapes.tsv"
            summary_file = Path(temp_dir_name) / "summary.json"
            shapes_file.write_text(
                "\n".join(
                    (
                        "leaf_shape\tleaf_detail",
                        "Sc--:c---\tSucw----:cw------",
                        "Sc--:c---\tSucw----:cw------",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            args = Namespace(
                pairs_file=None,
                shapes_file=shapes_file,
                target_verdict="all",
                samples=0,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                probe_shallow_leaves=False,
                dedupe_samples=True,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["loaded_samples"], 2)
        self.assertEqual(summary["filtered_samples"], 2)
        self.assertEqual(summary["deduped_samples"], 1)
        self.assertEqual(summary["samples"], 1)

    def test_audit_can_fail_on_unknown_shallow_class(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                probe_shallow_leaves=False,
                dedupe_samples=False,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_unknown_shallow_class=True,
                fail_on_shallow_input=False,
            )
            unknown_diagnostic = {
                "shape": "Sc--:c---",
                "detail": "Sucw----:cw------",
                "kind": "east_half",
                "reason": "candidate_exists_but_no_quality_gain",
                "shallow_class": "new_unknown_shallow_class",
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("Sc--:c---", "")]),
                mock.patch.object(audit_module, "diagnose_shallow_inputs", return_value=[unknown_diagnostic]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["shallow_resolutions"], {"unknown_or_actionable": 1})
        self.assertEqual(summary["unknown_shallow_cases"], 1)

    def test_audit_counts_impossible_rule_closed_shallow_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=8,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                probe_shallow_leaves=True,
                dedupe_samples=False,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                write_low_depth_shallow_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_terminal_boundary=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_reachable_terminal_probe=False,
                fail_on_truncated_terminal_probe=False,
                fail_on_unknown_shallow_class=True,
                fail_on_shallow_depth_below=None,
                fail_on_shallow_input=False,
            )

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("--P-:--cc", "")]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["shallow_resolutions"], {"impossible_rule_closed": 1})
        self.assertEqual(summary["strict_gap_resolutions"], {"shallow_impossible_rule_closed": 1})
        self.assertEqual(
            summary["shallow_impossible_rule_closed_reasons"],
            {"Quadrant 4: Corner Rule2. ^P*-+c violated": 1},
        )
        self.assertEqual(summary["unknown_shallow_cases"], 0)

    def test_audit_can_fail_on_shallow_leaf_below_depth_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_depth_below=6,
                fail_on_shallow_input=False,
            )
            fake_assessment = {
                "valid": (True, "ok"),
                "quality": {
                    "nodes": 1,
                    "max_depth": 4,
                    "input_leaves": 1,
                    "max_input_leaf_depth": 4,
                    "max_shallow_input_leaf_depth": 4,
                    "max_complex_input_leaf_depth": 0,
                    "complex_input_leaves": 0,
                    "shallow_input_leaves": 1,
                    "complex_input_shapes": [],
                    "shallow_input_shapes": ["Sc--:c---"],
                    "input_leaf_kinds": {"east_half": 1},
                    "ops": {"input": 1},
                },
                "diagnostics": [],
                "shallow_diagnostics": [
                    {
                        "shape": "Sc--:c---",
                        "detail": "Sucw----:cw------",
                        "kind": "east_half",
                        "leaf_depth": 4,
                        "reason": "candidate_exists_but_no_quality_gain",
                        "shallow_class": "multi_cell_half_with_crystal_requires_lateral_merge",
                    }
                ],
                "unknown_shallow_diagnostics": [],
                "resolved": True,
                "structural_resolved": True,
                "strict_resolved": False,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("Sc--:c---", "")]),
                mock.patch.object(audit_module, "assess_production_graph", return_value=fake_assessment),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["shallow_low_depth_cases"], 1)
        self.assertEqual(summary["shallow_depth_floor"], 6)
        self.assertEqual(summary["low_depth_shallow_threshold"], 6)
        self.assertEqual(summary["low_depth_shallow_leaves"], 1)

    def test_audit_writes_shallow_leaf_corpus(self) -> None:
        possible_target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        possible_predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            shallow_file = Path(temp_dir_name) / "shallow.tsv"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                write_unsupported_leaves=None,
                write_shallow_leaves=shallow_file,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

            rows = shallow_file.read_text(encoding="utf-8").splitlines()

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("leaf_shape", rows[0])
        self.assertIn("leaf_class", rows[0])
        self.assertIn("leaf_depth", rows[0])
        self.assertIn("shallow_terminal_hint", rows[0])
        self.assertIn("shallow_feature_signature", rows[0])

    def test_audit_writes_low_depth_shallow_leaf_corpus(self) -> None:
        possible_target = "--PP:--PS:--PS:-ScS:-S--:Sc--"
        possible_predecessor = "--PS:--PS:-ScS:-S-c:Sc-c:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            low_depth_file = Path(temp_dir_name) / "low_depth.tsv"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=8,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                write_low_depth_shallow_leaves=low_depth_file,
                low_depth_shallow_threshold=9,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_depth_below=None,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

            rows = low_depth_file.read_text(encoding="utf-8").splitlines()

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(rows), 1)
        self.assertIn("leaf_depth", rows[0])
        self.assertIn("shallow_terminal_hint", rows[0])

    def test_audit_writes_terminal_boundary_corpus(self) -> None:
        possible_target = "--PP:--PS:--PS:-ScS:-S--:Sc--"
        possible_predecessor = "--PS:--PS:-ScS:-S-c:Sc-c:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            terminal_file = Path(temp_dir_name) / "terminal.tsv"
            unique_terminal_file = Path(temp_dir_name) / "terminal_unique.tsv"
            terminal_signatures_file = Path(temp_dir_name) / "terminal_signatures.tsv"
            summary_file = Path(temp_dir_name) / "summary.json"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=8,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                write_low_depth_shallow_leaves=None,
                write_terminal_boundaries=terminal_file,
                write_unique_terminal_boundaries=unique_terminal_file,
                write_terminal_signatures=terminal_signatures_file,
                probe_terminal_boundaries=True,
                terminal_probe_pair_limit=77,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_terminal_boundary=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_reachable_terminal_probe=False,
                fail_on_truncated_terminal_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_depth_below=None,
                fail_on_shallow_input=False,
            )

            terminal_probe = {
                "reachable": False,
                "status": "not_found_complete",
                "steps": 3,
                "steps_completed": 3,
                "states": 9,
                "frontier": 0,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {"swap": 2},
                "pruned_counts": {"pair_pre": 1},
                "target_features": {},
                "truncated": False,
            }

            with (
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=terminal_probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            rows = terminal_file.read_text(encoding="utf-8").splitlines()
            unique_rows = unique_terminal_file.read_text(encoding="utf-8").splitlines()
            signature_rows = terminal_signatures_file.read_text(encoding="utf-8").splitlines()
            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(len(rows), 2)
        self.assertIn("terminal_shape", rows[0])
        self.assertIn("terminal_op", rows[0])
        self.assertIn("explain_reason", rows[0])
        self.assertIn("terminal_cycle_category", rows[0])
        self.assertIn("terminal_resolution", rows[0])
        self.assertIn("terminal_feature_signature", rows[0])
        self.assertIn("open_leaf_keys", rows[0])
        self.assertIn("open_leaf_descriptions", rows[0])
        self.assertIn("open_leaf_shapes", rows[0])
        self.assertIn("self_open_leaf_keys", rows[0])
        self.assertIn("self_open_leaf_count", rows[0])
        self.assertIn("unexpanded_leaf_keys", rows[0])
        self.assertIn("self_unexpanded_leaf_keys", rows[0])
        self.assertIn("self_unexpanded_leaf_count", rows[0])
        self.assertIn("probe_status", rows[0])
        self.assertIn("probe_states", rows[0])
        self.assertIn("probe_frontier", rows[0])
        self.assertIn("legacy_strict_verdict", rows[0])
        self.assertIn("terminal_legacy_possible_swap_limited", "\n".join(rows[1:]))
        self.assertIn("swap_limited", "\n".join(rows[1:]))
        self.assertIn("stack_input:swap_cut_12_34", "\n".join(rows[1:]))
        self.assertIn("not_found_complete", "\n".join(rows[1:]))
        self.assertIn("\tpossible\t", "\n".join(rows[1:]))
        self.assertTrue(summary["probe_config"]["probe_terminal_boundaries"])
        self.assertEqual(summary["probe_config"]["terminal_probe_pair_limit"], 77)
        self.assertEqual(summary["terminal_unique_shapes"], 2)
        self.assertEqual(summary["terminal_probe_unique_shapes"], 2)
        self.assertEqual(summary["terminal_bounded_forward_probe"], {"not_found_complete": 2})
        self.assertEqual(summary["terminal_resolutions"], {"self_open_leaf_cycle_probe_closed": 1, "self_unexpanded_leaf_cycle_probe_closed": 1})
        self.assertEqual(summary["strict_gap_resolutions"], {"terminal_known_closed": 1})
        self.assertEqual(summary["known_terminal_boundary_cases"], 1)
        self.assertEqual(summary["actionable_terminal_boundary_cases"], 0)
        self.assertEqual(summary["unprobed_terminal_boundary_cases"], 0)
        self.assertEqual(summary["terminal_bounded_forward_probe_ops"], {"swap": 4})
        self.assertEqual(summary["terminal_bounded_forward_probe_pruned_ops"], {"pair_pre": 2})
        self.assertEqual(len(unique_rows), 3)
        self.assertIn("occurrence_count", unique_rows[0])
        self.assertIn("terminal_feature_signature", unique_rows[0])
        self.assertIn("terminal_resolution", unique_rows[0])
        self.assertIn("samples", unique_rows[0])
        self.assertIn("not_found_complete", "\n".join(unique_rows[1:]))
        self.assertGreaterEqual(len(signature_rows), 2)
        self.assertIn("terminal_feature_signature", signature_rows[0])
        self.assertIn("unique_shape_count", signature_rows[0])
        self.assertIn("terminal_resolution", signature_rows[0])
        self.assertIn("probe_statuses", signature_rows[0])
        self.assertIn("not_found_complete", "\n".join(signature_rows[1:]))

    def test_terminal_boundary_real_probe_is_known_closed(self) -> None:
        possible_target = "--PP:--PS:--PS:-ScS:-S--:Sc--"
        possible_predecessor = "--PS:--PS:-ScS:-S-c:Sc-c:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            summary_file = Path(temp_dir_name) / "summary.json"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=8,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                write_low_depth_shallow_leaves=None,
                write_terminal_boundaries=None,
                write_unique_terminal_boundaries=None,
                write_terminal_signatures=None,
                probe_terminal_boundaries=True,
                terminal_probe_pair_limit=60,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_terminal_boundary=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_reachable_terminal_probe=True,
                fail_on_truncated_terminal_probe=True,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_depth_below=None,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["terminal_boundary_cases"], 1)
        self.assertEqual(summary["known_terminal_boundary_cases"], 1)
        self.assertEqual(summary["strict_gap_resolutions"], {"terminal_known_closed": 1})
        self.assertEqual(summary["actionable_terminal_boundary_cases"], 0)
        self.assertEqual(summary["unprobed_terminal_boundary_cases"], 0)
        self.assertEqual(summary["terminal_bounded_forward_probe"], {"not_found_complete": 2})
        self.assertEqual(summary["reachable_terminal_probe_cases"], 0)
        self.assertEqual(summary["truncated_terminal_probe_cases"], 0)

    def test_terminal_probe_unique_shapes_counts_only_reported_possible_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            summary_file = Path(temp_dir_name) / "summary.json"
            pairs_file.write_text("S---\tS---\n-S--\t-S--\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="all",
                samples=0,
                validate_layers=6,
                max_depth=8,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                write_low_depth_shallow_leaves=None,
                write_terminal_boundaries=None,
                write_unique_terminal_boundaries=None,
                write_terminal_signatures=None,
                probe_terminal_boundaries=True,
                terminal_probe_pair_limit=60,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_terminal_boundary=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_reachable_terminal_probe=False,
                fail_on_truncated_terminal_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_depth_below=None,
                fail_on_shallow_input=False,
            )
            fake_quality = {
                "nodes": 1,
                "input_leaves": 0,
                "complex_input_leaves": 0,
                "shallow_input_leaves": 0,
                "terminal_leaves": 1,
                "legacy_possible_terminal_leaves": 1,
                "complex_input_shapes": [],
                "shallow_input_shapes": [],
                "terminal_shapes": ["S---"],
                "input_leaf_kinds": {},
                "ops": {"terminal_legacy_possible_swap_limited": 1},
            }
            fake_assessment = {
                "valid": (True, "ok"),
                "quality": fake_quality,
                "diagnostics": [],
                "shallow_diagnostics": [],
                "unknown_shallow_diagnostics": [],
                "resolved": True,
                "structural_resolved": True,
                "strict_resolved": False,
            }
            terminal_diagnostics = [
                {
                    "shape": "S---",
                    "detail": "S---",
                    "op": "terminal_legacy_possible_swap_limited",
                    "note": "legacy_possible_swap_limited_terminal_no_pinpush_predecessor",
                    "leaf_depth": 1,
                    "explain_reason": "swap_limited",
                    "open_leaf_keys": {},
                    "self_open_leaf_keys": {"stack_input:swap_cut_12_34_left": 1},
                    "self_open_leaf_count": 1,
                    "unexpanded_leaf_keys": {},
                    "self_unexpanded_leaf_keys": {},
                    "self_unexpanded_leaf_count": 0,
                    "legacy_verdict": "possible",
                    "legacy_strict_verdict": "possible",
                    "legacy_class": "Simple",
                    "legacy_reason": "test",
                    "leaf_features": {"layers": 1, "occupied": 1, "crystals": 0, "pins": 0, "solids": 1},
                },
                {
                    "shape": "-S--",
                    "detail": "-S--",
                    "op": "terminal_legacy_possible_swap_limited",
                    "note": "legacy_possible_swap_limited_terminal_no_pinpush_predecessor",
                    "leaf_depth": 1,
                    "explain_reason": "swap_limited",
                    "open_leaf_keys": {},
                    "self_open_leaf_keys": {"stack_input:swap_cut_12_34_left": 1},
                    "self_open_leaf_count": 1,
                    "unexpanded_leaf_keys": {},
                    "self_unexpanded_leaf_keys": {},
                    "self_unexpanded_leaf_count": 0,
                    "legacy_verdict": "possible",
                    "legacy_strict_verdict": "possible",
                    "legacy_class": "Simple",
                    "legacy_reason": "test",
                    "leaf_features": {"layers": 1, "occupied": 1, "crystals": 0, "pins": 0, "solids": 1},
                },
            ]
            terminal_probe = {
                "reachable": False,
                "status": "not_found_complete",
                "steps": 3,
                "steps_completed": 3,
                "states": 3,
                "frontier": 0,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {},
                "pruned_counts": {},
                "target_features": {},
                "truncated": False,
            }

            with (
                mock.patch.object(audit_module, "build_claw_pinpush_graph", return_value=object()),
                mock.patch.object(audit_module, "assess_production_graph", return_value=fake_assessment),
                mock.patch.object(audit_module, "render_graph", return_value=["[terminal]"]),
                mock.patch.object(audit_module, "input_leaf_examples", return_value={}),
                mock.patch.object(audit_module, "diagnose_terminal_leaves", side_effect=[
                    [terminal_diagnostics[0]],
                    [terminal_diagnostics[1]],
                ]),
                mock.patch.object(audit_module, "_target_verdict_key", side_effect=[
                    "claw_not_possible:mock",
                    "claw_possible:claw_possible",
                ]),
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=terminal_probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["terminal_boundary_cases"], 1)
        self.assertEqual(summary["terminal_bounded_forward_probe"], {"not_found_complete": 1})
        self.assertEqual(summary["strict_gap_resolutions"], {"terminal_known_closed": 2})
        self.assertEqual(
            summary["target_verdict_strict_gap_resolution"],
            {
                "claw_not_possible:mock|terminal_known_closed": 1,
                "claw_possible:claw_possible|terminal_known_closed": 1,
            },
        )
        self.assertEqual(summary["terminal_probe_unique_shapes"], 1)
        self.assertEqual(summary["known_terminal_boundary_cases"], 1)

    def test_audit_can_fail_on_reachable_terminal_probe(self) -> None:
        possible_target = "--PP:--PS:--PS:-ScS:-S--:Sc--"
        possible_predecessor = "--PS:--PS:-ScS:-S-c:Sc-c:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            summary_file = Path(temp_dir_name) / "summary.json"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                shapes_file=None,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=8,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                terminal_probe_pair_limit=60,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                write_low_depth_shallow_leaves=None,
                write_terminal_boundaries=None,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_unknown_complex_class=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_structural_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_terminal_boundary=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_reachable_terminal_probe=True,
                fail_on_truncated_terminal_probe=False,
                fail_on_unknown_shallow_class=False,
                fail_on_shallow_depth_below=None,
                fail_on_shallow_input=False,
            )
            reachable_probe = {
                "reachable": True,
                "status": "reachable",
                "steps": 2,
                "steps_completed": 2,
                "states": 7,
                "frontier": 1,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {"stack": 1},
                "pruned_counts": {},
                "target_features": {},
                "truncated": False,
            }

            with (
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=reachable_probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertTrue(summary["probe_config"]["probe_terminal_boundaries"])
        self.assertEqual(summary["terminal_probe_unique_shapes"], 2)
        self.assertEqual(summary["terminal_bounded_forward_probe"], {"reachable": 2})
        self.assertEqual(summary["reachable_terminal_probe_cases"], 1)
        self.assertEqual(summary["strict_gap_resolutions"], {"terminal_actionable": 1})
        self.assertEqual(summary["known_terminal_boundary_cases"], 0)
        self.assertEqual(summary["actionable_terminal_boundary_cases"], 1)
        self.assertIn("reachable_terminal_probe_examples", summary)

    def test_audit_can_probe_shallow_leaves_for_missing_reverse_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=0,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                probe_shallow_leaves=True,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=True,
                fail_on_shallow_input=False,
            )
            reachable_probe = {
                "reachable": True,
                "status": "reachable",
                "steps": 2,
                "steps_completed": 2,
                "states": 42,
                "frontier": 5,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {"swap": 1},
                "pruned_counts": {},
                "target_features": {},
                "truncated": False,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("Sc--:c---", "")]),
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=reachable_probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["shallow_bounded_forward_probe"], {"reachable": 1})
        self.assertEqual(summary["reachable_shallow_probe_cases"], 1)
        diagnostic = summary["reachable_shallow_probe_examples"][0]["reachable_shallow_diagnostics"][0]
        self.assertTrue(diagnostic["probe_actionable"])

    def test_audit_can_fail_on_truncated_shallow_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            summary_file = Path(temp_dir_name) / "summary.json"
            args = Namespace(
                pairs_file=None,
                shapes_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=0,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                probe_shallow_leaves=True,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=summary_file,
                write_unsupported_leaves=None,
                write_shallow_leaves=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=True,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_reachable_shallow_probe=False,
                fail_on_shallow_input=False,
            )
            truncated_probe = {
                "reachable": False,
                "status": "not_found_truncated",
                "steps": 3,
                "steps_completed": 2,
                "states": 12000,
                "frontier": 9000,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {"stack": 10},
                "pruned_counts": {},
                "target_features": {},
                "truncated": True,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("Sc--:c---", "")]),
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=truncated_probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

            summary = json.loads(summary_file.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["shallow_bounded_forward_probe"], {"not_found_truncated": 1})
        self.assertEqual(summary["truncated_shallow_probe_cases"], 1)
        self.assertIn("truncated_shallow_probe_examples", summary)

    def test_audit_can_fail_on_shallow_possible_targets(self) -> None:
        possible_target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        possible_predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=8,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=2,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=True,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

        self.assertEqual(exit_code, 0)

    def test_audit_can_fail_on_truncated_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            args = Namespace(
                pairs_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=True,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )
            truncated_probe = {
                "reachable": False,
                "steps": 3,
                "steps_completed": 2,
                "states": 12000,
                "frontier": 9000,
                "max_steps": 3,
                "max_states": 12000,
                "op_counts": {"stack": 10},
                "pruned_counts": {},
                "target_features": {},
                "truncated": True,
            }

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("c-SS:P--P:PcSS", "")]),
                mock.patch.object(graph_module, "bounded_forward_probe", return_value=truncated_probe),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

        self.assertEqual(exit_code, 1)

    def test_audit_probe_budget_options_reach_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            args = Namespace(
                pairs_file=None,
                target_verdict="all",
                samples=1,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=1,
                probe_max_steps=3,
                probe_max_states=1800,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                fail_on_validation_failure=False,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=True,
                fail_on_unresolved_possible=False,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )

            with (
                mock.patch.object(audit_module, "_random_shape_samples", return_value=[("---c:cccS:PSPc", "")]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

        self.assertEqual(exit_code, 1)

    def test_audit_can_fail_on_strict_unresolved_possible_targets(self) -> None:
        possible_target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        possible_predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=2,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_strict_unresolved_possible=True,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

        self.assertEqual(exit_code, 1)

    def test_audit_can_fail_on_terminal_boundary(self) -> None:
        possible_target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        possible_predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=2,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_strict_unresolved_possible=False,
                fail_on_terminal_boundary=True,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=False,
                fail_on_shallow_input=False,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = audit(args)

        self.assertEqual(exit_code, 1)

    def test_audit_can_fail_on_actionable_shallow_possible_targets(self) -> None:
        possible_target = "P-CuP-P-:CuCuCu--:P---P---:P---Cu--:P-------:CucrCu--"
        possible_predecessor = "S-Sc:PScc:PSPc:P-Sc:ScSc:---c"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            pairs_file = Path(temp_dir_name) / "pairs.tsv"
            pairs_file.write_text(f"{possible_target}\t{possible_predecessor}\n", encoding="utf-8")
            args = Namespace(
                pairs_file=pairs_file,
                target_verdict="possible",
                samples=0,
                validate_layers=6,
                max_depth=6,
                max_examples=1,
                max_leaf_examples=1,
                graph_lines=2,
                probe_max_steps=3,
                probe_max_states=12000,
                probe_pair_limit=180,
                seed=123,
                alphabet="SPc-",
                min_layers=1,
                max_layers=3,
                stable_only=False,
                write_filtered_pairs=None,
                write_summary_json=None,
                fail_on_validation_failure=True,
                fail_on_complex_input=False,
                fail_on_actionable_complex_input=False,
                fail_on_truncated_probe=False,
                fail_on_unresolved_possible=True,
                fail_on_strict_unresolved_possible=False,
                fail_on_shallow_possible=False,
                fail_on_actionable_shallow_possible=True,
                fail_on_shallow_input=False,
            )
            actionable_diagnostics = [
                {
                    "shape": "Cu------",
                    "detail": "Cu------",
                    "kind": "east_half",
                    "reason": "candidate_exists_but_not_selected",
                }
            ]

            with (
                mock.patch.object(audit_module, "diagnose_shallow_inputs", return_value=actionable_diagnostics),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = audit(args)

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
