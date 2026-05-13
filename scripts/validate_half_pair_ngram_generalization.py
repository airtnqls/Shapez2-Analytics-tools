from __future__ import annotations

import argparse
import contextlib
import io
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import symbolic_frontier_automaton as sfa
from generate_zero_stack_half_pair_candidates import _mask_shape, _or_shape, _rotate_180


@dataclass(frozen=True)
class Record:
    target: str
    predecessor: str
    sequences: tuple[tuple[tuple[str, str], ...], ...]


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import claw_process
        from data_operations import simplify_shape
        from shape import Shape

        raw = claw_process(repr(Shape.from_string(code)))
        return sfa.normalize_code(simplify_shape(raw) if raw else "")


def _layer_at(code: str, index: int) -> str:
    parts = sfa.normalize_code(code).split(":") if sfa.normalize_code(code) else []
    return parts[index] if index < len(parts) else "----"


def _abstract_layer(layer: str, mode: str) -> str:
    if mode == "raw":
        return layer
    if mode == "counts":
        return f"P{layer.count('P')}S{layer.count('S')}c{layer.count('c')}"
    if mode == "mask_counts":
        occ = "".join("1" if ch != "-" else "0" for ch in layer)
        return f"{occ}|P{layer.count('P')}S{layer.count('S')}c{layer.count('c')}"
    if mode == "classes":
        return "".join("-" if ch == "-" else "X" if ch in {"S", "P"} else "c" for ch in layer)
    raise ValueError(mode)


def _sequence_for(predecessor: str, layers: int, angle: int, abstraction: str) -> tuple[tuple[str, str], ...]:
    rotated = predecessor
    for _ in range(angle):
        rotated = sfa.bitmask_rotate_clockwise(rotated)
    left = _mask_shape(rotated, 0b0011)
    right = _rotate_180(_mask_shape(rotated, 0b1100))
    return tuple(
        (_abstract_layer(_layer_at(left, index), abstraction), _abstract_layer(_layer_at(right, index), abstraction))
        for index in range(layers)
    )


def _collect(args: argparse.Namespace) -> list[Record]:
    started = time.perf_counter()
    records: list[Record] = []
    total = 0
    for code in sfa.iter_data_codes(args.data, max_layers=args.train_layers):
        if args.limit and total >= args.limit:
            break
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        target = sfa.normalize_code(code)
        if not target:
            continue
        total += 1
        predecessor = _claw_predecessor(target)
        if not predecessor or sfa.bitmask_push_pin(predecessor, args.train_layers) != target:
            continue
        subtype = sfa.pp_subtype_candidate(predecessor, args.train_layers).subtype
        if subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        records.append(
            Record(
                target=target,
                predecessor=predecessor,
                sequences=(
                    _sequence_for(predecessor, args.train_layers, 0, args.abstraction),
                    _sequence_for(predecessor, args.train_layers, 1, args.abstraction),
                ),
            )
        )
    return records


def _ngram_index(index: int, sequence_len: int, order: int, index_mode: str) -> int:
    if index_mode == "absolute":
        return index
    if index_mode == "none":
        return -1
    if index_mode == "top_relative":
        return index - (sequence_len - order)
    if index_mode == "top_relative_prefix":
        return index - (sequence_len - order)
    raise ValueError(index_mode)


def _ngrams(
    sequence: tuple[tuple[str, str], ...],
    order: int,
    index_mode: str = "absolute",
) -> set[tuple[int, tuple[tuple[str, str], ...]]]:
    return {
        (_ngram_index(index, len(sequence), order, index_mode), sequence[index : index + order])
        for index in range(len(sequence) - order + 1)
    }


def _train_ngrams(records: list[Record], order: int, index_mode: str = "absolute") -> set[tuple[int, tuple[tuple[str, str], ...]]]:
    out: set[tuple[int, tuple[tuple[str, str], ...]]] = set()
    for record in records:
        for sequence in record.sequences:
            out.update(_ngrams(sequence, order, index_mode=index_mode))
            if index_mode == "top_relative_prefix":
                out.update(_ngrams(sequence, order, index_mode="none"))
    return out


def _accepted_by_ngrams(
    record: Record,
    order: int,
    trained: set[tuple[int, tuple[tuple[str, str], ...]]],
    index_mode: str = "absolute",
) -> bool:
    for sequence in record.sequences:
        grams = _ngrams(sequence, order, index_mode=index_mode)
        if index_mode == "top_relative_prefix":
            min_index = min((index for index, _gram in grams), default=0)
            grams = {
                ((-1 if index == min_index else index), gram)
                for index, gram in grams
            }
        if grams and grams <= trained:
            return True
    return False


def _sequence_to_predecessor(sequence: tuple[tuple[str, str], ...]) -> str:
    left = sfa.normalize_code(":".join(item[0] for item in sequence))
    right = sfa.normalize_code(":".join(item[1] for item in sequence))
    return _or_shape(left, _rotate_180(right))


def _enumerate_sequences(
    trained: set[tuple[int, tuple[tuple[str, str], ...]]],
    order: int,
    layers: int,
    max_sequences: int,
    started: float,
    max_seconds: float,
) -> tuple[set[str], bool]:
    starts = sorted(gram for index, gram in trained if index == 0)
    next_map: dict[tuple[int, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]], list[tuple[str, str]]] = {}
    if order == 1:
        by_index: dict[int, list[tuple[str, str]]] = {}
        for index, gram in trained:
            by_index.setdefault(index, []).append(gram[0])
        generated: set[str] = set()
        truncated = False

        def rec(index: int, seq: tuple[tuple[str, str], ...]) -> None:
            nonlocal truncated
            if truncated:
                return
            if max_seconds and time.perf_counter() - started > max_seconds:
                truncated = True
                return
            if max_sequences and len(generated) >= max_sequences:
                truncated = True
                return
            if index == layers:
                pred = _sequence_to_predecessor(seq)
                if pred:
                    generated.add(pred)
                return
            for item in by_index.get(index, ()):
                rec(index + 1, seq + (item,))

        rec(0, ())
        return generated, truncated

    transitions: dict[tuple[int, tuple[tuple[str, str], ...]], list[tuple[str, str]]] = {}
    for index, gram in trained:
        if len(gram) != order:
            continue
        transitions.setdefault((index, gram[:-1]), []).append(gram[-1])
    for values in transitions.values():
        values.sort()

    generated: set[str] = set()
    truncated = False

    def rec(sequence: tuple[tuple[str, str], ...]) -> None:
        nonlocal truncated
        if truncated:
            return
        if max_seconds and time.perf_counter() - started > max_seconds:
            truncated = True
            return
        if max_sequences and len(generated) >= max_sequences:
            truncated = True
            return
        if len(sequence) == layers:
            pred = _sequence_to_predecessor(sequence)
            if pred:
                generated.add(pred)
            return
        index = len(sequence) - order + 1
        suffix = sequence[-(order - 1) :]
        for child in transitions.get((index, suffix), ()):
            rec(sequence + (child,))
            if truncated:
                return

    for start in starts:
        rec(start)
        if truncated:
            break
    return generated, truncated


def _enumerate_abstract_sequences(
    trained: set[tuple[int, tuple[tuple[str, str], ...]]],
    order: int,
    layers: int,
    max_sequences: int,
    started: float,
    max_seconds: float,
    index_mode: str = "absolute",
    train_layers: int = 5,
) -> tuple[int, bool]:
    if index_mode == "absolute":
        start_index = 0
    elif index_mode == "none":
        start_index = -1
    elif index_mode == "top_relative_prefix":
        start_index = -1
    else:
        start_index = -(layers - order)
    starts = sorted(gram for index, gram in trained if index == start_index)
    transitions: dict[tuple[int, tuple[tuple[str, str], ...]], list[tuple[str, str]]] = {}
    for index, gram in trained:
        if len(gram) != order:
            continue
        transitions.setdefault((index if index_mode != "none" else -1, gram[:-1]), []).append(gram[-1])
    for values in transitions.values():
        values.sort()

    count = 0
    truncated = False

    def rec(sequence: tuple[tuple[str, str], ...]) -> None:
        nonlocal count, truncated
        if truncated:
            return
        if max_seconds and time.perf_counter() - started > max_seconds:
            truncated = True
            return
        if max_sequences and count >= max_sequences:
            truncated = True
            return
        if len(sequence) == layers:
            count += 1
            return
        raw_index = len(sequence) - order + 1
        if index_mode == "none":
            index = -1
        elif index_mode == "top_relative_prefix":
            top_relative_index = _ngram_index(raw_index, layers, order, "top_relative")
            min_train_top_relative = -(train_layers - order)
            index = -1 if top_relative_index < min_train_top_relative else top_relative_index
        else:
            index = _ngram_index(raw_index, layers, order, index_mode)
        suffix = sequence[-(order - 1) :]
        for child in transitions.get((index, suffix), ()):
            rec(sequence + (child,))
            if truncated:
                return

    for start in starts:
        rec(start)
        if truncated:
            break
    return count, truncated


def validate(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    records = _collect(args)
    rng = random.Random(args.seed)
    rng.shuffle(records)
    train_size = int(len(records) * args.train_ratio)
    train = records[:train_size]
    holdout = records[train_size:]
    index_mode = "none" if args.unindexed else args.index_mode
    trained = _train_ngrams(train, args.order, index_mode=index_mode)
    train_accept = sum(1 for record in train if _accepted_by_ngrams(record, args.order, trained, index_mode=index_mode))
    holdout_accept = sum(1 for record in holdout if _accepted_by_ngrams(record, args.order, trained, index_mode=index_mode))
    if args.abstraction == "raw":
        generated, truncated = _enumerate_sequences(
            trained,
            args.order,
            args.generate_layers,
            args.max_sequences,
            started,
            args.max_seconds,
            indexed=index_mode != "none",
        )
        abstract_generated_count = 0
        abstract_truncated = False
    else:
        generated, truncated = set(), False
        abstract_generated_count, abstract_truncated = _enumerate_abstract_sequences(
            trained,
            args.order,
            args.generate_layers,
            args.max_sequences,
            started,
            args.max_seconds,
            index_mode=index_mode,
            train_layers=args.train_layers,
        )
    train_preds = {record.predecessor for record in train}
    holdout_preds = {record.predecessor for record in holdout}
    generated_train = generated & train_preds
    generated_holdout = generated & holdout_preds

    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"train_layers={args.train_layers}")
    print(f"generate_layers={args.generate_layers}")
    print(f"order={args.order}")
    print(f"abstraction={args.abstraction}")
    print(f"index_mode={index_mode}")
    print(f"records={len(records)}")
    print(f"train={len(train)}")
    print(f"holdout={len(holdout)}")
    print(f"trained_ngrams={len(trained)}")
    print(f"train_accept={train_accept}")
    print(f"train_accept_rate={100.0 * train_accept / len(train) if train else 100:.6f}%")
    print(f"holdout_accept={holdout_accept}")
    print(f"holdout_accept_rate={100.0 * holdout_accept / len(holdout) if holdout else 100:.6f}%")
    print(f"generated={len(generated)}")
    print(f"generated_truncated={truncated}")
    print(f"abstract_generated_count={abstract_generated_count}")
    print(f"abstract_generated_truncated={abstract_truncated}")
    print(f"generated_train_overlap={len(generated_train)}")
    print(f"generated_holdout_overlap={len(generated_holdout)}")
    print(f"generated_holdout_recall={100.0 * len(generated_holdout) / len(holdout_preds) if holdout_preds else 100:.6f}%")
    print(f"generated_extra_vs_all={len(generated - train_preds - holdout_preds)}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate half-pair ngram automaton generalization with train/holdout splits.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--train-layers", type=int, default=0)
    parser.add_argument("--generate-layers", type=int, default=0)
    parser.add_argument("--order", type=int, default=4)
    parser.add_argument("--abstraction", choices=("raw", "counts", "mask_counts", "classes"), default="raw")
    parser.add_argument("--unindexed", action="store_true")
    parser.add_argument("--index-mode", choices=("absolute", "top_relative", "top_relative_prefix"), default="absolute")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-sequences", type=int, default=0)
    args = parser.parse_args()
    if args.train_layers <= 0:
        args.train_layers = args.layers
    if args.generate_layers <= 0:
        args.generate_layers = args.layers
    return validate(args)


if __name__ == "__main__":
    raise SystemExit(main())
