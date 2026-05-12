from __future__ import annotations

import argparse
import struct
import time
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.symbolic_frontier_automaton import bitmask_apply_physics, normalize_code  # noqa: E402

ALPHABET = tuple((a, b) for a in range(4) for b in range(4))
CHARS = "-PSc"
REFERENCE_CPCP_DIR = PROJECT_ROOT / "reference_projects" / "shapez2-cpcp1998"


@lru_cache(maxsize=8)
def load_cpcp_dump(layers: int) -> tuple[frozenset[int], frozenset[int]]:
    dump = REFERENCE_CPCP_DIR / f"dump{layers}.bin"
    data = dump.read_bytes()
    width = 4 if layers <= 4 else 8
    fmt = "<I" if width == 4 else "<Q"
    pos = 0
    half_count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    halves = frozenset(struct.unpack_from(fmt, data, pos + i * width)[0] for i in range(half_count))
    pos += half_count * width
    shape_count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    shapes = frozenset(struct.unpack_from(fmt, data, pos + i * width)[0] for i in range(shape_count))
    return halves, shapes


def encode_half_word(bits: int, layers: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (
            (bits >> (2 * (layer * 4))) & 3,
            (bits >> (2 * (layer * 4 + 1))) & 3,
        )
        for layer in range(layers)
    )


def word_to_code(word: tuple[tuple[int, int], ...]) -> str:
    layers = [CHARS[a] + CHARS[b] + "--" for a, b in word]
    while layers and layers[-1] == "----":
        layers.pop()
    return ":".join(layers)


def load_reference_half_words(layers: int) -> set[tuple[tuple[int, int], ...]]:
    halves, _shapes = load_cpcp_dump(layers)
    return {encode_half_word(bits, layers) for bits in halves}


def build_min_dfa(accepted: set[tuple[tuple[int, int], ...]], layers: int) -> tuple[int, dict[int, dict[tuple[int, int], int]], set[int]]:
    signatures: dict[tuple, int] = {}
    transitions: dict[int, dict[tuple[int, int], int]] = {}
    accepting_states: set[int] = set()

    @lru_cache(maxsize=None)
    def state_for(prefix: tuple[tuple[int, int], ...]) -> int:
        depth = len(prefix)
        if depth == layers:
            signature = ("leaf", prefix in accepted)
        else:
            child_states = tuple(state_for(prefix + (symbol,)) for symbol in ALPHABET)
            signature = ("node", child_states)
        if signature in signatures:
            return signatures[signature]
        state_id = len(signatures)
        signatures[signature] = state_id
        if depth == layers:
            if prefix in accepted:
                accepting_states.add(state_id)
            transitions[state_id] = {}
        else:
            transitions[state_id] = {symbol: child for symbol, child in zip(ALPHABET, signature[1])}
        return state_id

    start = state_for(())
    return start, transitions, accepting_states


def accepts(word: tuple[tuple[int, int], ...], start: int, transitions: dict[int, dict[tuple[int, int], int]], accepting: set[int]) -> bool:
    state = start
    for symbol in word:
        state = transitions[state][symbol]
    return state in accepting


def compile_dense_dfa(
    transitions: dict[int, dict[tuple[int, int], int]],
    accepting: set[int],
) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    rows = []
    for state in range(len(transitions)):
        rows.append(tuple(transitions[state].get(symbol, -1) for symbol in ALPHABET))
    accept = tuple(state in accepting for state in range(len(transitions)))
    return tuple(rows), accept


def accepts_dense(word: tuple[tuple[int, int], ...], start: int, dense: tuple[tuple[int, ...], ...], accepting: tuple[bool, ...]) -> bool:
    state = start
    for a, b in word:
        state = dense[state][a * 4 + b]
    return accepting[state]


def accepts_bits_dense(bits: int, layers: int, start: int, dense: tuple[tuple[int, ...], ...], accepting: tuple[bool, ...]) -> bool:
    state = start
    for layer in range(layers):
        a = (bits >> (2 * (layer * 4))) & 3
        b = (bits >> (2 * (layer * 4 + 1))) & 3
        state = dense[state][a * 4 + b]
    return accepting[state]


def enumerate_all_words(layers: int):
    def rec(prefix: tuple[tuple[int, int], ...]):
        if len(prefix) == layers:
            yield prefix
            return
        for symbol in ALPHABET:
            yield from rec(prefix + (symbol,))

    yield from rec(())


def load_stable_half_words(layers: int) -> set[tuple[tuple[int, int], ...]]:
    accepted = set()
    for word in enumerate_all_words(layers):
        code = word_to_code(word)
        if bitmask_apply_physics(code) == normalize_code(code):
            accepted.add(word)
    return accepted


def load_stable_reference_gap_words(layers: int) -> set[tuple[tuple[int, int], ...]]:
    stable = load_stable_half_words(layers)
    reference = load_reference_half_words(layers)
    return stable - reference


def summarize_states(
    start: int,
    transitions: dict[int, dict[tuple[int, int], int]],
    accepting: set[int],
    layers: int,
    limit: int,
) -> None:
    depths: dict[int, set[int]] = {start: {0}}
    frontier = [(start, 0)]
    while frontier:
        state, depth = frontier.pop()
        if depth >= layers:
            continue
        for child in transitions[state].values():
            known = depths.setdefault(child, set())
            if depth + 1 not in known:
                known.add(depth + 1)
                frontier.append((child, depth + 1))

    @lru_cache(maxsize=None)
    def accepted_suffixes(state: int, remaining: int) -> int:
        if remaining == 0:
            return int(state in accepting)
        return sum(accepted_suffixes(child, remaining - 1) for child in transitions[state].values())

    rows = []
    for state, ds in depths.items():
        best_depth = min(ds)
        remaining = layers - best_depth
        rows.append((best_depth, -accepted_suffixes(state, remaining), state, sorted(ds), accepted_suffixes(state, remaining)))
    rows.sort()
    print("state_summary:")
    for depth, _neg_count, state, all_depths, count in rows[:limit]:
        print(f"  state={state} depths={','.join(map(str, all_depths))} first_depth={depth} accepted_suffixes={count}")


def summarize_depth_profile(
    start: int,
    transitions: dict[int, dict[tuple[int, int], int]],
    accepting: set[int],
    layers: int,
) -> None:
    depth_states: list[set[int]] = [set() for _ in range(layers + 1)]
    depth_states[0].add(start)
    for depth in range(layers):
        for state in depth_states[depth]:
            depth_states[depth + 1].update(transitions[state].values())

    @lru_cache(maxsize=None)
    def accepted_suffixes(state: int, remaining: int) -> int:
        if remaining == 0:
            return int(state in accepting)
        return sum(accepted_suffixes(child, remaining - 1) for child in transitions[state].values())

    print("depth_profile:")
    for depth, states in enumerate(depth_states):
        remaining = layers - depth
        nonzero = sum(1 for state in states if accepted_suffixes(state, remaining) > 0)
        total_suffixes = sum(accepted_suffixes(state, remaining) for state in states)
        print(f"  depth={depth} states={len(states)} nonzero_states={nonzero} accepted_suffixes_sum={total_suffixes}")


def summarize_prefix_transitions(
    start: int,
    transitions: dict[int, dict[tuple[int, int], int]],
    accepting: set[int],
    layers: int,
    depth: int,
    limit: int,
) -> None:
    @lru_cache(maxsize=None)
    def accepted_suffixes(state: int, remaining: int) -> int:
        if remaining == 0:
            return int(state in accepting)
        return sum(accepted_suffixes(child, remaining - 1) for child in transitions[state].values())

    rows = []

    def rec(prefix: tuple[tuple[int, int], ...], state: int) -> None:
        if len(prefix) == depth:
            rows.append((accepted_suffixes(state, layers - depth), prefix, state))
            return
        for symbol, child in transitions[state].items():
            rec(prefix + (symbol,), child)

    rec((), start)
    rows.sort(reverse=True)
    print(f"prefix_summary_depth{depth}:")
    for count, prefix, state in rows[:limit]:
        print(f"  accepted_suffixes={count} state={state} prefix={word_to_code(prefix)}")


def emit_python_constant(start: int, transitions: dict[int, dict[tuple[int, int], int]], accepting: set[int]) -> None:
    rows = []
    for state in range(len(transitions)):
        row = [transitions[state].get(symbol, -1) for symbol in ALPHABET]
        rows.append(row)
    print("HALF_DFA_ALPHABET = " + repr(ALPHABET))
    print("HALF_DFA_START = " + repr(start))
    print("HALF_DFA_ACCEPTING = " + repr(tuple(sorted(accepting))))
    print("HALF_DFA_TRANSITIONS = (")
    for row in rows:
        print("    " + repr(tuple(row)) + ",")
    print(")")


def benchmark_membership(
    accepted: set[tuple[tuple[int, int], ...]],
    start: int,
    transitions: dict[int, dict[tuple[int, int], int]],
    accepting: set[int],
    layers: int,
    rounds: int,
) -> None:
    words = list(enumerate_all_words(layers))
    bit_words = []
    for word in words:
        bits = 0
        for layer, (a, b) in enumerate(word):
            bits |= a << (2 * (layer * 4))
            bits |= b << (2 * (layer * 4 + 1))
        bit_words.append(bits)
    started = time.perf_counter()
    set_hits = 0
    for _ in range(rounds):
        for word in words:
            set_hits += int(word in accepted)
    set_time = time.perf_counter() - started

    started = time.perf_counter()
    dfa_hits = 0
    for _ in range(rounds):
        for word in words:
            dfa_hits += int(accepts(word, start, transitions, accepting))
    dfa_time = time.perf_counter() - started

    dense, dense_accepting = compile_dense_dfa(transitions, accepting)
    started = time.perf_counter()
    dense_hits = 0
    for _ in range(rounds):
        for word in words:
            dense_hits += int(accepts_dense(word, start, dense, dense_accepting))
    dense_time = time.perf_counter() - started

    started = time.perf_counter()
    dense_bits_hits = 0
    for _ in range(rounds):
        for bits in bit_words:
            dense_bits_hits += int(accepts_bits_dense(bits, layers, start, dense, dense_accepting))
    dense_bits_time = time.perf_counter() - started

    print("benchmark:")
    print(f"  words={len(words)}")
    print(f"  rounds={rounds}")
    print(f"  set_hits={set_hits}")
    print(f"  dfa_hits={dfa_hits}")
    print(f"  dense_hits={dense_hits}")
    print(f"  dense_bits_hits={dense_bits_hits}")
    print(f"  set_time={set_time:.6f}s")
    print(f"  dfa_time={dfa_time:.6f}s")
    print(f"  dense_time={dense_time:.6f}s")
    print(f"  dense_bits_time={dense_bits_time:.6f}s")
    print(f"  dfa_vs_set={(set_time / dfa_time) if dfa_time else 0:.3f}x")
    print(f"  dense_vs_set={(set_time / dense_time) if dense_time else 0:.3f}x")
    print(f"  dense_bits_vs_set={(set_time / dense_bits_time) if dense_bits_time else 0:.3f}x")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a minimal acyclic DFA for cpcp half-set membership.")
    parser.add_argument("--layers", type=int, default=4)
    parser.add_argument("--source", choices=("reference", "stable", "stable-gap"), default="reference")
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--state-summary", action="store_true")
    parser.add_argument("--depth-profile", action="store_true")
    parser.add_argument("--state-limit", type=int, default=80)
    parser.add_argument("--prefix-depth", type=int, default=0)
    parser.add_argument("--prefix-limit", type=int, default=40)
    parser.add_argument("--emit-python-constant", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--benchmark-rounds", type=int, default=5)
    args = parser.parse_args()

    if args.source == "reference":
        accepted = load_reference_half_words(args.layers)
    elif args.source == "stable":
        accepted = load_stable_half_words(args.layers)
    else:
        accepted = load_stable_reference_gap_words(args.layers)
    start, transitions, accepting = build_min_dfa(accepted, args.layers)

    mismatches = []
    total = 0
    for word in enumerate_all_words(args.layers):
        total += 1
        expected = word in accepted
        got = accepts(word, start, transitions, accepting)
        if expected != got and len(mismatches) < args.samples:
            mismatches.append((word, expected, got))

    edge_count = sum(len(row) for row in transitions.values())
    if args.emit_python_constant and not mismatches:
        emit_python_constant(start, transitions, accepting)
        return 0
    print(f"layers={args.layers}")
    print(f"alphabet={len(ALPHABET)}")
    print(f"accepted_halves={len(accepted)}")
    print(f"total_words={total}")
    print(f"dfa_states={len(transitions)}")
    print(f"accepting_states={len(accepting)}")
    print(f"edges={edge_count}")
    print(f"mismatches={len(mismatches)}")
    if args.state_summary:
        summarize_states(start, transitions, accepting, args.layers, args.state_limit)
    if args.depth_profile:
        summarize_depth_profile(start, transitions, accepting, args.layers)
    if args.prefix_depth:
        summarize_prefix_transitions(start, transitions, accepting, args.layers, args.prefix_depth, args.prefix_limit)
    if args.benchmark:
        benchmark_membership(accepted, start, transitions, accepting, args.layers, args.benchmark_rounds)
    if mismatches:
        for word, expected, got in mismatches:
            print(f"mismatch\t{word_to_code(word)}\texpected={expected}\tgot={got}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
