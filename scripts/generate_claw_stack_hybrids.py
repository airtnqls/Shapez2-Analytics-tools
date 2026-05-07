from __future__ import annotations

import argparse
import contextlib
import itertools
import io
import random
from collections import Counter
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shape import Shape

with contextlib.redirect_stdout(io.StringIO()):
    from shape_classifier import ShapeType, analyze_shape


DEFAULT_INPUT = REPO_ROOT / "data/all40171clawsnohybrid_정렬됨.txt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data"
DEFAULT_TOP_CHARS = ("-", "S")
DEFAULT_SKIP_PROBABILITY = 0.9

ALLOWED_EMPTY_MASKS = {
    "0000:0000:0001:0001:0011",
    "0000:0001:0011:0011:0111",
    "0000:0000:0010:0111:0111",
    "0001:0001:0001:0001:0011",
    "0000:0000:0010:0111:1111",
    "0000:0010:0011:0011:0111",
    "0000:0010:0011:0011:0011",
    "0000:0010:0011:0011:1111",
    "0000:0001:0011:0011:0011",
    "0000:0000:0001:0011:0111",
    "0000:0000:0001:0111:0111",
    "0000:0000:0000:0001:0011",
    "0000:0010:0010:1111:1111",
    "0000:0000:0000:0011:0111",
    "0000:0000:0000:0011:1111",
    "0000:0010:0010:0111:0111",
    "0000:0001:0001:0011:0111",
    "0000:0000:0010:0011:0111",
    "0001:0001:0001:0011:0011",
    "0000:0000:0001:0011:0011",
    "0000:0000:0010:0011:1111",
    "0000:0010:0010:0011:0111",
    "0000:0001:0001:0111:0111",
    "0000:0010:0010:0011:1111",
    "0000:0010:0010:0111:1111",
    "0000:0000:0000:0010:1111",
    "0000:0000:0010:0010:1111",
    "0000:0000:0010:0010:0111",
    "0000:0000:0000:0010:0111",
    "0000:0001:0001:0011:0011",
    "0000:0010:0010:0010:0111",
    "0000:0010:0010:0011:0011",
    "0000:0010:0010:0010:0011",
    "0000:0000:0010:0010:0011",
    "0000:0010:0010:0010:1111",
    "0000:0000:0010:0011:0011",
    "0000:0000:0000:0010:0011",
    "0000:0000:0010:0010:0010",
    "0000:0000:0000:0000:0011",
    "0000:0000:0000:0011:0011",
    "0000:0010:0010:0010:0010",
    "0000:0000:0000:0010:0010",
    "0000:0000:0000:0000:0010",
}


def simplify_shape_code(shape: Shape | str, layers: int = 5) -> str:
    shape_obj = Shape.from_string(shape) if isinstance(shape, str) else shape
    layer_codes: list[str] = []
    for layer_index in range(layers):
        chars: list[str] = []
        for quadrant_index in range(4):
            piece = shape_obj._get_piece(layer_index, quadrant_index)
            if piece is None:
                chars.append("-")
            elif piece.shape in {"C", "S", "R", "W"}:
                chars.append("S")
            elif piece.shape == "P":
                chars.append("P")
            elif piece.shape == "c":
                chars.append("c")
            else:
                chars.append("-")
        layer_codes.append("".join(chars))
    return ":".join(layer_codes)


def empty_mask_for_shape(shape: Shape | str, layers: int = 5) -> str:
    simple = simplify_shape_code(shape, layers)
    return ":".join(
        "".join("1" if char == "-" else "0" for char in layer)
        for layer in simple.split(":")
    )


def generate_top_codes(mask: str, top_chars: tuple[str, ...] = DEFAULT_TOP_CHARS) -> list[str]:
    layers = mask.split(":")
    variable_positions = [
        (layer_index, quadrant_index)
        for layer_index, layer_mask in enumerate(layers)
        for quadrant_index, bit in enumerate(layer_mask)
        if bit == "1"
    ]

    top_codes: list[str] = []
    for values in itertools.product(top_chars, repeat=len(variable_positions)):
        top_layers = [["-", "-", "-", "-"] for _ in layers]
        for (layer_index, quadrant_index), value in zip(variable_positions, values):
            top_layers[layer_index][quadrant_index] = value
        top_codes.append(":".join("".join(layer) for layer in top_layers))
    return top_codes


def classification_slug(classification: str) -> str:
    for shape_type in ShapeType:
        if shape_type.value == classification:
            return shape_type.name.lower()
    return "unknown"


def output_path_for(input_path: Path, output_dir: Path, slug: str) -> Path:
    return output_dir / f"{input_path.stem}_{slug}.txt"


def load_shapes(input_path: Path) -> list[str]:
    with input_path.open("r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def generate_all_mask_top_codes() -> list[str]:
    return sorted({
        top_code
        for mask in ALLOWED_EMPTY_MASKS
        for top_code in generate_top_codes(mask)
    })


def classify_generated_shapes(
    input_path: Path,
    output_dir: Path,
    *,
    dedupe: bool,
    progress_every: int,
    limit: int | None,
    skip_probability: float,
    seed: int | None,
) -> None:
    claws = load_shapes(input_path)
    if limit is not None:
        claws = claws[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)

    all_mask_top_codes = generate_all_mask_top_codes()
    valid_slugs = {shape_type.name.lower() for shape_type in ShapeType}
    handles = {}
    generated_seen: set[str] = set()
    counts: Counter[str] = Counter()
    errors: list[tuple[str, str]] = []
    start_time = time.monotonic()
    rng = random.Random(seed)
    attempted_top_count = 0
    skipped_top_count = 0

    try:
        for index, claw_code in enumerate(claws, 1):
            try:
                claw_shape = Shape.from_string(claw_code)
                for top_code in all_mask_top_codes:
                    if skip_probability > 0 and rng.random() < skip_probability:
                        skipped_top_count += 1
                        continue
                    attempted_top_count += 1
                    top_shape = Shape.from_string(top_code)
                    stacked = Shape.stack(claw_shape, top_shape)
                    stacked_code = simplify_shape_code(stacked)
                    if dedupe and stacked_code in generated_seen:
                        continue
                    generated_seen.add(stacked_code)

                    classification, _reason = analyze_shape(stacked_code, stacked)
                    slug = classification_slug(classification)
                    if slug not in valid_slugs:
                        slug = "unknown"
                    if slug not in handles:
                        handles[slug] = output_path_for(input_path, output_dir, slug).open("w", encoding="utf-8")
                    handles[slug].write(stacked_code + "\n")
                    counts[slug] += 1
            except Exception as exc:
                errors.append((claw_code, str(exc)))

            if progress_every and index % progress_every == 0:
                elapsed = time.monotonic() - start_time
                rate = index / elapsed if elapsed > 0 else 0
                remaining = (len(claws) - index) / rate if rate > 0 else 0
                total = sum(counts.values())
                print(
                    f"processed={index}/{len(claws)} "
                    f"generated={total} "
                    f"errors={len(errors)} "
                    f"attempted={attempted_top_count} "
                    f"random_skipped={skipped_top_count} "
                    f"elapsed={format_seconds(elapsed)} "
                    f"rate={rate:.2f}/s "
                    f"eta={format_seconds(remaining)}"
                )
    finally:
        for handle in handles.values():
            handle.close()

    summary_path = output_dir / f"{input_path.stem}_generation_summary.txt"
    with summary_path.open("w", encoding="utf-8") as file:
        file.write(f"input={input_path}\n")
        file.write(f"input_count={len(claws)}\n")
        file.write(f"dedupe={dedupe}\n")
        file.write(f"top_chars={''.join(DEFAULT_TOP_CHARS)}\n")
        file.write(f"skip_probability={skip_probability}\n")
        file.write(f"seed={seed}\n")
        file.write("mask_mode=all\n")
        file.write(f"top_code_count={len(all_mask_top_codes)}\n")
        file.write(f"attempted_top_count={attempted_top_count}\n")
        file.write(f"random_skipped_top_count={skipped_top_count}\n")
        file.write(f"generated_count={sum(counts.values())}\n\n")
        file.write("[classification_counts]\n")
        for slug, count in sorted(counts.items()):
            file.write(f"{slug}={count}\n")
        file.write("\n[errors]\n")
        for claw_code, error in errors:
            file.write(f"{claw_code}\t{error}\n")

    print(f"done: generated={sum(counts.values())} summary={summary_path}")


def format_seconds(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate stack results by filling sorted claw empty masks and split them by classifier result."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-dedupe", action="store_true", help="Write duplicate generated shapes too.")
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N input claws.")
    parser.add_argument("--skip-probability", type=float, default=DEFAULT_SKIP_PROBABILITY)
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible skipping.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    classify_generated_shapes(
        args.input,
        args.output_dir,
        dedupe=not args.no_dedupe,
        progress_every=args.progress_every,
        limit=args.limit,
        skip_probability=args.skip_probability,
        seed=args.seed,
    )
