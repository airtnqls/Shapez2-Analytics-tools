from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import resource
import statistics
import subprocess
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack_pp import (
    LegacyStackClosureAutomaton,
    RowInfo,
    StackClosureAutomaton,
    compile_complete_minimized,
)
from stack_pp.row_table import ROW_SIGNATURES
from stack_pp.rows import CRYSTAL, EMPTY, NORMAL, PIN


class AllFamily:
    name = "all-stable-base"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        del row_signature
        return state

    def accepts(self, state):
        return state == 0


ALPHABET = tuple(ROW_SIGNATURES)


def _legacy_worker(depth: int) -> dict:
    automaton = LegacyStackClosureAutomaton(AllFamily())
    tracemalloc.start()
    started = time.perf_counter()
    levels = automaton.reachable_states(ALPHABET, depth)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    subset = []
    for level in levels:
        sizes = [len(state.product_states) for state in level]
        subset.append(
            {
                "min": min(sizes, default=0),
                "max": max(sizes, default=0),
                "mean": statistics.fmean(sizes) if sizes else 0.0,
                "sum": sum(sizes),
            }
        )
    return {
        "variant": "legacy",
        "status": "completed",
        "depth": depth,
        "states_per_exact_depth": [len(level) for level in levels],
        "subset_per_depth": subset,
        "transition_entries": len(automaton._transition_cache),
        "seconds": elapsed,
        "tracemalloc_peak_bytes": peak,
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def _optimized_worker(depth: int, subsumption: bool) -> dict:
    automaton = StackClosureAutomaton(
        AllFamily(), enable_subsumption=subsumption
    )
    tracemalloc.start()
    started = time.perf_counter()
    exploration = automaton.explore(depth)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    metrics_before_release = automaton.metrics()
    automaton.release_build_caches()
    metrics_after_release = automaton.metrics()
    return {
        "variant": "optimized" if subsumption else "compact_no_subsumption",
        "status": "completed",
        "depth": depth,
        "states_per_exact_depth": list(exploration.states_per_exact_depth),
        "cumulative_states_per_depth": list(exploration.cumulative_states_per_depth),
        "transitions_per_depth": list(exploration.transitions_per_depth),
        "seconds_per_depth": list(exploration.seconds_per_depth),
        "seconds": elapsed,
        "metrics_before_release": asdict(metrics_before_release),
        "metrics_after_release": asdict(metrics_after_release),
        "tracemalloc_peak_bytes": peak,
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def _minimized_worker() -> dict:
    source = StackClosureAutomaton(AllFamily())
    tracemalloc.start()
    started = time.perf_counter()
    minimized = compile_complete_minimized(source)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "variant": "complete_minimized",
        "status": "completed",
        "seconds": elapsed,
        "metrics": asdict(minimized.metrics()),
        "source_metrics_after_release": asdict(source.metrics()),
        "tracemalloc_peak_bytes": peak,
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def _worker_main(args) -> int:
    if args.variant == "legacy":
        report = _legacy_worker(args.depth)
    elif args.variant == "compact-no-subsumption":
        report = _optimized_worker(args.depth, False)
    elif args.variant == "optimized":
        report = _optimized_worker(args.depth, True)
    elif args.variant == "minimized":
        report = _minimized_worker()
    else:
        raise ValueError(args.variant)
    print(json.dumps(report))
    return 0


def run_worker(variant: str, depth: int, timeout_seconds: float) -> dict:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--variant",
        variant,
        "--depth",
        str(depth),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "variant": variant,
            "status": "diagnostic_timeout",
            "depth": depth,
            "budget_seconds": timeout_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "semantic_meaning": (
                "none: this is not rejection, impossibility, or an automaton "
                "state cap; only the comparative benchmark process was stopped"
            ),
        }
    if completed.returncode != 0:
        return {
            "variant": variant,
            "status": "worker_error",
            "depth": depth,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    return json.loads(completed.stdout.strip().splitlines()[-1])


def percentile_ns(values: list[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(fraction * (len(ordered) - 1))
    return ordered[index] / 1000.0


def single_target_benchmark(cases_per_layer: int = 600) -> dict:
    rng = random.Random(0x57AC20260717)
    corpora = {
        layers: [
            tuple(rng.randrange(256) for _ in range(layers))
            for _ in range(cases_per_layer)
        ]
        for layers in range(1, 6)
    }
    legacy = LegacyStackClosureAutomaton(AllFamily())
    optimized = StackClosureAutomaton(AllFamily())
    minimized = compile_complete_minimized(StackClosureAutomaton(AllFamily()))

    def legacy_accept(rows) -> bool:
        state = legacy.start_state()
        for row_id in rows:
            state = legacy.advance(state, ROW_SIGNATURES[row_id])
            if state is None:
                return False
        return legacy.accepts(state)

    report = {}
    for layers, corpus in corpora.items():
        legacy_times: list[int] = []
        optimized_times: list[int] = []
        minimized_times: list[int] = []
        witness_times: list[int] = []
        accepted = 0
        for rows in corpus:
            t0 = time.perf_counter_ns()
            old = legacy_accept(rows)
            legacy_times.append(time.perf_counter_ns() - t0)

            t0 = time.perf_counter_ns()
            new = optimized.accepts_rows(rows)
            optimized_times.append(time.perf_counter_ns() - t0)

            t0 = time.perf_counter_ns()
            compact = minimized.accepts_rows(rows)
            minimized_times.append(time.perf_counter_ns() - t0)

            t0 = time.perf_counter_ns()
            witness = optimized.witness(rows)
            witness_times.append(time.perf_counter_ns() - t0)

            if old != new or old != compact or old != (witness is not None):
                raise AssertionError((layers, rows, old, new, compact, witness))
            accepted += int(old)

        def summarize(values):
            return {
                "mean_us": statistics.fmean(values) / 1000.0,
                "median_us": percentile_ns(values, 0.50),
                "p95_us": percentile_ns(values, 0.95),
                "max_us": max(values) / 1000.0,
            }

        report[str(layers)] = {
            "cases": len(corpus),
            "accepted": accepted,
            "legacy_membership": summarize(legacy_times),
            "optimized_membership": summarize(optimized_times),
            "minimized_membership": summarize(minimized_times),
            "optimized_witness": summarize(witness_times),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument(
        "--variant",
        choices=("legacy", "compact-no-subsumption", "optimized", "minimized"),
        default="optimized",
    )
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "stack_automaton_benchmark.json",
    )
    args = parser.parse_args()
    if args.worker:
        return _worker_main(args)

    print("[benchmark] legacy L2", file=sys.stderr, flush=True)
    legacy_l2 = run_worker("legacy", 2, 180.0)
    legacy_l3 = {
        "variant": "legacy",
        "status": "not_repeated_after_prior_300s_diagnostic_noncompletion",
        "depth": 3,
        "semantic_meaning": "none; no membership answer was inferred",
    }
    legacy_depths = {"1-2": legacy_l2, "3": legacy_l3}
    for depth in (4, 5):
        legacy_depths[str(depth)] = {
            "variant": "legacy",
            "status": "not_started_after_depth3_diagnostic_budget",
            "depth": depth,
            "semantic_meaning": "none; no membership answer was inferred",
        }

    print("[benchmark] compact no-subsumption", file=sys.stderr, flush=True)
    no_sub = run_worker("compact-no-subsumption", 3, 180.0)
    print("[benchmark] optimized L5", file=sys.stderr, flush=True)
    optimized = run_worker("optimized", 5, 300.0)
    print("[benchmark] complete minimized", file=sys.stderr, flush=True)
    minimized = run_worker("minimized", 0, 300.0)
    print("[benchmark] single-target L1-L5", file=sys.stderr, flush=True)
    single = single_target_benchmark()
    report = {
        "environment": {
            "python": sys.version,
            "platform": sys.platform,
            "cpu_count": os.cpu_count(),
        },
        "full_reachable_build": {
            "legacy": legacy_depths,
            "compact_no_subsumption": no_sub,
            "optimized": optimized,
            "complete_minimized": minimized,
        },
        "single_target_L1_to_L5": single,
        "interpretation": {
            "timeouts": (
                "benchmark-only diagnostic stops; never used as IMPOSSIBLE"
            ),
            "full_dfa": (
                "optimized L1-L5 uses all 256 rows at every reachable state"
            ),
            "witness": (
                "reconstructed separately; membership stores no parent history"
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
