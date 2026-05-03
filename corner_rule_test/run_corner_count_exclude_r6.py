"""Count valid corner strings for n=1..max_n with R6 excluded. UTF-8 BOM txt for Notepad."""
from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

CRT_DIR = Path(__file__).resolve().parent
ROOT = CRT_DIR.parent
sys.path.insert(0, str(ROOT))


def format_ms_or_s(dt: float) -> str:
    """Show duration in ms only; if >= 1000 ms, show in seconds instead."""
    ms = dt * 1000.0
    if ms >= 1000.0:
        return f"{dt:.6f} s"
    return f"{ms:.3f} ms"


def main() -> None:
    parser = argparse.ArgumentParser(description="Corner rule counts with R6 excluded (n=1..max_n).")
    parser.add_argument(
        "-n",
        "--max-n",
        type=int,
        default=100,
        metavar="N",
        help="Maximum string length n (runs n=1 through N). Default: 100.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .txt path. Default: corner_count_n1_<N>_exclude_R6.txt next to this script.",
    )
    args = parser.parse_args()
    max_n = args.max_n
    if max_n < 1:
        parser.error("--max-n must be >= 1")

    spec = importlib.util.spec_from_file_location("corner_rule_main_exec", CRT_DIR / "main.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["corner_rule_main_exec"] = mod
    spec.loader.exec_module(mod)

    specs_no_r6 = tuple(s for s in mod.DEFAULT_RULE_SPECS if s.name != "R6")
    engine = mod.RuleEngine(specs_no_r6)

    out_lines: list[str] = []
    out_lines.append(f"Valid corner-string counts (R6 excluded), n=1..{max_n}")
    out_lines.append("Alphabet: S, -, P, c")
    out_lines.append("Active rules: " + ", ".join(s.name for s in specs_no_r6 if s.pattern.strip()))
    out_lines.append("")

    t_all0 = time.perf_counter()
    for n in range(1, max_n + 1):
        t0 = time.perf_counter()
        cnt = engine.count_valid_dp(n)
        t1 = time.perf_counter()
        dt = t1 - t0
        out_lines.append(f"n={n}: count={cnt}, time={format_ms_or_s(dt)}")
        elapsed_so_far = time.perf_counter() - t_all0
        print(
            f"progress {n}/{max_n} count={cnt} step={format_ms_or_s(dt)} "
            f"elapsed={format_ms_or_s(elapsed_so_far)}",
            flush=True,
        )
    t_all1 = time.perf_counter()
    elapsed = t_all1 - t_all0
    out_lines.append("")
    out_lines.append(f"total_time={format_ms_or_s(elapsed)}")

    out_path = args.output
    if out_path is None:
        out_path = CRT_DIR / f"corner_count_n1_{max_n}_exclude_R6.txt"
    else:
        out_path = Path(out_path)
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8-sig")
    print("Wrote", out_path.resolve())
    print(f"total_time={format_ms_or_s(elapsed)}")


if __name__ == "__main__":
    main()
