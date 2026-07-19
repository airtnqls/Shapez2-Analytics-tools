"""
Regex forbidden-rule counter/search GUI for alphabet {S, -, P, c}.

Run:
    pip install PyQt6
    python main.py

This file is intentionally self-contained.  The bulk engine does not enumerate
4^n candidates and does not run Python regexes against every candidate.  The
forbidden regexes are compiled once into small NFAs, and each compact combined
state is advanced one character at a time.  Counting uses DP over states.

README-style notes
------------------
Why not brute force 4^n?
    Length n has 4^n raw strings.  That grows too quickly: n=16 already means
    4,294,967,296 candidates before filtering.  Generating them and checking
    six regexes per candidate is not practical.

Why not load all possible strings into a txt/list/set?
    The output can still be huge after filtering.  Holding every possible
    string in memory wastes RAM, makes the GUI unresponsive, and prevents
    long-running searches from streaming partial results.

How count works here:
    The engine keeps only a dictionary of {DFA-like combined_state: count}.
    For each length position it advances those states through the four alphabet
    characters.  The answer is the sum of counts after n steps.

How search works here:
    Search is a DFS/generator that carries the current state and a small buffer.
    Branches that complete a forbidden rule are discarded immediately.  Results
    are yielded one by one and written/displayed as a stream.
"""

from __future__ import annotations

import re
import sys
import json
import time
import contextlib
import io
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Iterator

from PyQt6.QtCore import QByteArray, QObject, QSize, QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QTextOption
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QAbstractScrollArea,
    QCheckBox,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
try:
    from i18n import load_locales, set_language

    load_locales(str(PROJECT_ROOT / "locales"))
    set_language("en")
except Exception:
    pass

ALPHABET = ("S", "-", "P", "c")
Symbol = frozenset[str] | None


LUCIDE_PATHS = {
    # Lucide icons, ISC license: https://lucide.dev/license
    "calculator": ["M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z", "M8 6h8", "M8 10h.01", "M12 10h.01", "M16 10h.01", "M8 14h.01", "M12 14h.01", "M16 14h.01", "M8 18h.01", "M12 18h.01", "M16 18h.01"],
    "search": ["m21 21-4.34-4.34", "M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z"],
    "check": ["M20 6 9 17l-5-5"],
    "save": ["M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z", "M17 21v-8H7v8", "M7 3v5h8"],
    "x": ["M18 6 6 18", "m6 6 12 12"],
    "chevron-left": ["m15 18-6-6 6-6"],
    "chevron-right": ["m9 18 6-6-6-6"],
    "circle-help": ["M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3", "M12 17h.01", "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"],
}


def lucide_icon(name: str, color: str = "#1f2937", size: int = 22) -> QIcon:
    paths = "\n".join(f'<path d="{path}"/>' for path in LUCIDE_PATHS[name])
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24"
         fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        {paths}
    </svg>
    """
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


@dataclass(frozen=True)
class Fragment:
    start: int
    accepts: frozenset[int]


class NFABuilder:
    """Tiny Thompson-NFA builder for the regex subset needed by R1..R6."""

    def __init__(self) -> None:
        self.next_id = 0
        self.transitions: dict[int, dict[Symbol, set[int]]] = defaultdict(lambda: defaultdict(set))

    def new_state(self) -> int:
        sid = self.next_id
        self.next_id += 1
        return sid

    def add_edge(self, src: int, symbol: Symbol, dst: int) -> None:
        self.transitions[src][symbol].add(dst)

    def literal(self, ch: str) -> Fragment:
        start, end = self.new_state(), self.new_state()
        self.add_edge(start, frozenset({ch}), end)
        return Fragment(start, frozenset({end}))

    def any_char(self) -> Fragment:
        start, end = self.new_state(), self.new_state()
        self.add_edge(start, frozenset(ALPHABET), end)
        return Fragment(start, frozenset({end}))

    def char_set(self, chars: Iterable[str]) -> Fragment:
        start, end = self.new_state(), self.new_state()
        self.add_edge(start, frozenset(chars), end)
        return Fragment(start, frozenset({end}))

    def concat(self, *parts: Fragment) -> Fragment:
        if not parts:
            start = end = self.new_state()
            return Fragment(start, frozenset({end}))
        current = parts[0]
        for nxt in parts[1:]:
            for accept in current.accepts:
                self.add_edge(accept, None, nxt.start)
            current = Fragment(current.start, nxt.accepts)
        return current

    def alternate(self, *parts: Fragment) -> Fragment:
        start, end = self.new_state(), self.new_state()
        for part in parts:
            self.add_edge(start, None, part.start)
            for accept in part.accepts:
                self.add_edge(accept, None, end)
        return Fragment(start, frozenset({end}))

    def star(self, part: Fragment) -> Fragment:
        start, end = self.new_state(), self.new_state()
        self.add_edge(start, None, part.start)
        self.add_edge(start, None, end)
        for accept in part.accepts:
            self.add_edge(accept, None, part.start)
            self.add_edge(accept, None, end)
        return Fragment(start, frozenset({end}))

    def plus(self, part: Fragment) -> Fragment:
        start, end = self.new_state(), self.new_state()
        self.add_edge(start, None, part.start)
        for accept in part.accepts:
            self.add_edge(accept, None, part.start)
            self.add_edge(accept, None, end)
        return Fragment(start, frozenset({end}))

    def optional(self, part: Fragment) -> Fragment:
        start, end = self.new_state(), self.new_state()
        self.add_edge(start, None, part.start)
        self.add_edge(start, None, end)
        for accept in part.accepts:
            self.add_edge(accept, None, end)
        return Fragment(start, frozenset({end}))


@dataclass(frozen=True)
class RuleNFA:
    name: str
    anchored: bool
    start: int
    accepts: frozenset[int]
    transitions: tuple[tuple[tuple[Symbol, tuple[int, ...]], ...], ...]
    eps_closure: tuple[frozenset[int], ...]
    start_closure: frozenset[int]

    @classmethod
    def build(cls, name: str, anchored: bool, build_func: Callable[[NFABuilder], Fragment]) -> "RuleNFA":
        builder = NFABuilder()
        frag = build_func(builder)
        max_state = builder.next_id
        raw: list[list[tuple[Symbol, tuple[int, ...]]]] = [[] for _ in range(max_state)]
        for src, edges in builder.transitions.items():
            for symbol, dsts in edges.items():
                raw[src].append((symbol, tuple(sorted(dsts))))

        transitions = tuple(tuple(edges) for edges in raw)

        def closure(seed: Iterable[int]) -> frozenset[int]:
            stack = list(seed)
            seen = set(stack)
            while stack:
                state = stack.pop()
                for symbol, dsts in transitions[state]:
                    if symbol is None:
                        for dst in dsts:
                            if dst not in seen:
                                seen.add(dst)
                                stack.append(dst)
            return frozenset(seen)

        eps_closure = tuple(closure([state]) for state in range(max_state))
        start_closure = closure([frag.start])
        return cls(name, anchored, frag.start, frag.accepts, transitions, eps_closure, start_closure)

    def advance(self, active: frozenset[int], ch: str) -> frozenset[int]:
        reached: set[int] = set()
        for state in active:
            for symbol, dsts in self.transitions[state]:
                if symbol is not None and ch in symbol:
                    reached.update(dsts)
        if not reached:
            return frozenset()
        closed: set[int] = set()
        for state in reached:
            closed.update(self.eps_closure[state])
        return frozenset(closed)

    def is_accepting(self, active: frozenset[int]) -> bool:
        return bool(active & self.accepts)


@dataclass(frozen=True)
class State:
    active: tuple[frozenset[int], ...]


@dataclass(frozen=True)
class RegexAst:
    kind: str
    value: object = None


class RuleRegexParser:
    """Parser for the compact regex subset used by editable forbidden rules."""

    def __init__(self, pattern: str) -> None:
        self.original = pattern
        self.pattern = pattern
        self.pos = 0
        self.anchored = False

    def parse(self) -> tuple[bool, RegexAst]:
        if self.pattern.startswith("^"):
            self.anchored = True
            self.pattern = self.pattern[1:]
        if "$" in self.pattern:
            raise ValueError("Rule editor does not support the end anchor $.")
        ast = self._parse_alt()
        if self.pos != len(self.pattern):
            raise ValueError(f"Unexpected character: {self.pattern[self.pos]!r}")
        return self.anchored, ast

    def _peek(self) -> str | None:
        return self.pattern[self.pos] if self.pos < len(self.pattern) else None

    def _take(self) -> str:
        ch = self.pattern[self.pos]
        self.pos += 1
        return ch

    def _parse_alt(self) -> RegexAst:
        parts = [self._parse_seq()]
        while self._peek() == "|":
            self._take()
            parts.append(self._parse_seq())
        if len(parts) == 1:
            return parts[0]
        return RegexAst("alt", parts)

    def _parse_seq(self) -> RegexAst:
        parts: list[RegexAst] = []
        while self._peek() is not None and self._peek() not in ")|":
            parts.append(self._parse_repeat())
        if not parts:
            return RegexAst("empty")
        if len(parts) == 1:
            return parts[0]
        return RegexAst("concat", parts)

    def _parse_repeat(self) -> RegexAst:
        atom = self._parse_atom()
        ch = self._peek()
        if ch in ("*", "+", "?"):
            self._take()
            return RegexAst("repeat", (atom, ch))
        if ch == "{":
            return RegexAst("repeat", (atom, self._parse_brace_repeat()))
        return atom

    def _parse_brace_repeat(self) -> tuple[int, int | None]:
        self._take()
        start = self.pos
        while self._peek() and self._peek().isdigit():
            self._take()
        if self.pos == start:
            raise ValueError("{m,n} repeat requires a number.")
        minimum = int(self.pattern[start:self.pos])
        if self._peek() == "}":
            self._take()
            return minimum, minimum
        if self._peek() != ",":
            raise ValueError("Invalid {m,n} repeat syntax.")
        self._take()
        start = self.pos
        while self._peek() and self._peek().isdigit():
            self._take()
        maximum = None if self.pos == start else int(self.pattern[start:self.pos])
        if self._peek() != "}":
            raise ValueError("Missing closing brace in {m,n} repeat.")
        self._take()
        if maximum is not None and maximum < minimum:
            raise ValueError("In {m,n}, n cannot be smaller than m.")
        return minimum, maximum

    def _parse_atom(self) -> RegexAst:
        ch = self._peek()
        if ch is None:
            return RegexAst("empty")
        if ch == "(":
            self._take()
            ast = self._parse_alt()
            if self._peek() != ")":
                raise ValueError("Missing closing parenthesis.")
            self._take()
            return ast
        if ch == ".":
            self._take()
            return RegexAst("any")
        if ch == "[":
            return self._parse_class()
        if ch == "\\":
            self._take()
            ch = self._take()
        else:
            ch = self._take()
        if ch not in ALPHABET:
            raise ValueError(f"Unsupported character: {ch!r}")
        return RegexAst("lit", ch)

    def _parse_class(self) -> RegexAst:
        self._take()
        negated = False
        if self._peek() == "^":
            negated = True
            self._take()
        chars: set[str] = set()
        while self._peek() is not None and self._peek() != "]":
            ch = self._take()
            if ch == "\\":
                ch = self._take()
            if ch not in ALPHABET:
                raise ValueError(f"Unsupported character in character class: {ch!r}")
            chars.add(ch)
        if self._peek() != "]":
            raise ValueError("Missing closing bracket in character class.")
        self._take()
        if not chars:
            raise ValueError("Empty character class is not allowed.")
        if negated:
            chars = set(ALPHABET) - chars
        return RegexAst("set", frozenset(chars))


def build_regex_ast(ast: RegexAst, builder: NFABuilder) -> Fragment:
    if ast.kind == "empty":
        return builder.concat()
    if ast.kind == "lit":
        return builder.literal(str(ast.value))
    if ast.kind == "set":
        return builder.char_set(ast.value)
    if ast.kind == "any":
        return builder.any_char()
    if ast.kind == "concat":
        return builder.concat(*(build_regex_ast(part, builder) for part in ast.value))
    if ast.kind == "alt":
        return builder.alternate(*(build_regex_ast(part, builder) for part in ast.value))
    if ast.kind == "repeat":
        child, quantifier = ast.value
        if quantifier == "*":
            return builder.star(build_regex_ast(child, builder))
        if quantifier == "+":
            return builder.plus(build_regex_ast(child, builder))
        if quantifier == "?":
            return builder.optional(build_regex_ast(child, builder))
        minimum, maximum = quantifier
        required = [build_regex_ast(child, builder) for _ in range(minimum)]
        if maximum is None:
            tail = builder.star(build_regex_ast(child, builder))
            return builder.concat(*required, tail)
        optional_count = maximum - minimum
        optional_parts = [builder.optional(build_regex_ast(child, builder)) for _ in range(optional_count)]
        return builder.concat(*required, *optional_parts)
    raise ValueError(f"Unsupported AST node: {ast.kind}")


@dataclass(frozen=True)
class RuleSpec:
    name: str
    pattern: str


DEFAULT_RULE_SPECS = (
    RuleSpec("R1", r"-P"),
    RuleSpec("R2", r"^P*-+c"),
    RuleSpec("R3", r"[^P]P.*c"),
    RuleSpec("R4", r"c-.*c"),
    RuleSpec("R5", r"c.-+c"),
    RuleSpec("R6", r"^S*-?S*c(.*c)?(S-+)+c"),
    RuleSpec("R7", ""),
    RuleSpec("R8", ""),
    RuleSpec("R9", ""),
    RuleSpec("R10", ""),
)

DEFAULT_RULE_MAP = {spec.name: spec.pattern for spec in DEFAULT_RULE_SPECS}
SETTINGS_PATH = Path(__file__).with_name("corners_rule_search_settings.json")


class RuleEngine:
    alphabet = list(ALPHABET)

    def __init__(self, rule_specs: Iterable[RuleSpec] = DEFAULT_RULE_SPECS) -> None:
        self.rule_specs = tuple(spec for spec in rule_specs if spec.pattern.strip())
        self.rules = self._build_rules(self.rule_specs)
        self._regex_rules = [(spec.name, re.compile(spec.pattern)) for spec in self.rule_specs]

    @staticmethod
    def _build_rules(rule_specs: Iterable[RuleSpec]) -> tuple[RuleNFA, ...]:
        built: list[RuleNFA] = []
        for spec in rule_specs:
            parser = RuleRegexParser(spec.pattern)
            anchored, ast = parser.parse()
            built.append(
                RuleNFA.build(
                    spec.name,
                    anchored,
                    lambda builder, ast=ast: build_regex_ast(ast, builder),
                )
            )
        return tuple(built)

    def start_state(self) -> State:
        return State(tuple(rule.start_closure for rule in self.rules))

    def step(self, state: State, ch: str) -> State | None:
        next_active: list[frozenset[int]] = []
        for rule, active in zip(self.rules, state.active):
            # Unanchored regexes behave like re.search: a fresh match may start
            # at the current character position.
            current = active if rule.anchored else (active | rule.start_closure)
            moved = rule.advance(current, ch)
            if rule.is_accepting(moved):
                return None
            next_active.append(moved)
        return State(tuple(next_active))

    def is_valid_string(self, s: str) -> bool:
        state = self.start_state()
        for ch in s:
            if ch not in ALPHABET:
                return False
            state = self.step(state, ch)
            if state is None:
                return False
        return True

    def matched_rules(self, s: str) -> list[str]:
        return [name for name, pattern in self._regex_rules if pattern.search(s)]

    def dead_rules_by_state_machine(self, s: str) -> list[str]:
        """Debug helper: report which NFA rule(s) first accept while scanning s."""
        state = self.start_state()
        for ch in s:
            if ch not in ALPHABET:
                return []
            next_active: list[frozenset[int]] = []
            dead: list[str] = []
            for rule, active in zip(self.rules, state.active):
                current = active if rule.anchored else (active | rule.start_closure)
                moved = rule.advance(current, ch)
                if rule.is_accepting(moved):
                    dead.append(rule.name)
                next_active.append(moved)
            if dead:
                return dead
            state = State(tuple(next_active))
        return []

    def count_valid_dp(self, n: int, cancel_flag: Callable[[], bool] | None = None, progress=None) -> int:
        dp: dict[State, int] = {self.start_state(): 1}
        for pos in range(n):
            if cancel_flag and cancel_flag():
                raise RuntimeError("cancelled")
            ndp: dict[State, int] = defaultdict(int)
            for state, count in dp.items():
                for ch in self.alphabet:
                    ns = self.step(state, ch)
                    if ns is not None:
                        ndp[ns] += count
            dp = ndp
            if progress:
                progress(pos + 1, n, len(dp))
        return sum(dp.values())

    def generate_valid(self, n: int, query_regex=None, limit=None, cancel_flag=None):
        yielded = 0
        buffer: list[str] = []

        def is_cancelled() -> bool:
            return bool(cancel_flag and cancel_flag())

        def dfs(pos: int, state: State):
            nonlocal yielded
            if is_cancelled():
                return
            if limit is not None and yielded >= limit:
                return
            if pos == n:
                s = "".join(buffer)
                if query_regex is None or query_regex.search(s):
                    yielded += 1
                    yield s
                return
            for ch in self.alphabet:
                if is_cancelled():
                    return
                ns = self.step(state, ch)
                if ns is None:
                    continue
                buffer.append(ch)
                yield from dfs(pos + 1, ns)
                buffer.pop()

        yield from dfs(0, self.start_state())


FULL_LAYER_VALUES = tuple(
    a + b + c + d
    for a in ALPHABET
    for b in ALPHABET
    for c in ALPHABET
    for d in ALPHABET
)


def simplified_layers_to_code(layers: tuple[str, ...]) -> str:
    return ":".join(layers)


@lru_cache(maxsize=500_000)
def classify_full_shape(code: str) -> tuple[str, str]:
    with contextlib.redirect_stdout(io.StringIO()):
        from shape_classifier import analyze_shape

        # analyze_shape builds the Shape object internally. Passing a prebuilt
        # object would currently be ignored by the repository implementation.
        return analyze_shape(code)


def _normalize_simplified_layers(layers: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for layer in layers:
        clean = "".join(ch if ch in ALPHABET else "-" for ch in layer.strip())
        normalized.append((clean + "----")[:4])
    while normalized and normalized[-1] == "----":
        normalized.pop()
    return tuple(normalized)


def _rotate_layer_cw(layer: str) -> str:
    # Shape quadrant order is TR, BR, BL, TL. Clockwise rotation maps TL to TR.
    return layer[3] + layer[0] + layer[1] + layer[2]


def _mirror_layer(layer: str) -> str:
    # Mirror preserves east/west vertical order: TR, TL, BL, BR.
    return layer[0] + layer[3] + layer[2] + layer[1]


@lru_cache(maxsize=1_000_000)
def canonical_full_shape_code(code: str) -> str:
    layers = _normalize_simplified_layers(code.split(":") if code else ())
    if not layers:
        return ""

    variants: list[str] = []
    current = layers
    for _ in range(4):
        variants.append(simplified_layers_to_code(current))
        variants.append(simplified_layers_to_code(tuple(_mirror_layer(layer) for layer in current)))
        current = tuple(_rotate_layer_cw(layer) for layer in current)
    return min(variants)


@lru_cache(maxsize=500_000)
def simplify_full_shape_code(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        from shape import Shape

        shape = Shape.from_string(code)
        layers: list[str] = []
        for layer in shape.layers:
            chars: list[str] = []
            for quadrant in layer.quadrants:
                if quadrant is None:
                    chars.append("-")
                elif quadrant.shape == "P":
                    chars.append("P")
                elif quadrant.shape == "c":
                    chars.append("c")
                elif quadrant.shape in {"C", "S", "R", "W"}:
                    chars.append("S")
                else:
                    chars.append("-")
            layers.append("".join(chars))
        while layers and layers[-1] == "----":
            layers.pop()
        return simplified_layers_to_code(tuple(layers))


class FullShapeEngine:
    alphabet = list(ALPHABET)

    def __init__(self) -> None:
        self.corner_engine = RuleEngine(DEFAULT_RULE_SPECS)
        self._layer_transition_cache: dict[
            tuple[tuple[State, State, State, State], str],
            tuple[State, State, State, State] | None,
        ] = {}

    def _start_pillar_states(self) -> tuple[State, State, State, State]:
        start = self.corner_engine.start_state()
        return (start, start, start, start)

    def _step_layer(self, states: tuple[State, State, State, State], layer: str) -> tuple[State, State, State, State] | None:
        cache_key = (states, layer)
        if cache_key in self._layer_transition_cache:
            return self._layer_transition_cache[cache_key]

        next_states: list[State] = []
        for state, ch in zip(states, layer):
            ns = self.corner_engine.step(state, ch)
            if ns is None:
                self._layer_transition_cache[cache_key] = None
                return None
            next_states.append(ns)
        result = tuple(next_states)  # type: ignore[assignment]
        self._layer_transition_cache[cache_key] = result
        return result

    def _is_valid_full_shape(self, code: str) -> tuple[bool, str, str]:
        try:
            classification, reason = classify_full_shape(code)
            from shape_classifier import ShapeType
        except Exception:
            return False, "", ""
        if classification in {ShapeType.IMPOSSIBLE.value, ShapeType.UNKNOWN.value}:
            return False, classification, reason
        return True, classification, reason

    def _is_canonical(self, code: str) -> bool:
        try:
            return code == canonical_full_shape_code(code)
        except Exception:
            return False

    def generate_valid(self, max_layers: int, query_regex=None, limit=None, cancel_flag=None, exclude_symmetry: bool = True):
        yielded = 0
        layers: list[str] = []

        def is_cancelled() -> bool:
            return bool(cancel_flag and cancel_flag())

        def dfs(pos: int, states: tuple[State, State, State, State]):
            nonlocal yielded
            if is_cancelled():
                return
            if limit is not None and yielded >= limit:
                return
            if pos >= max_layers:
                return

            for layer in FULL_LAYER_VALUES:
                if is_cancelled():
                    return
                ns = self._step_layer(states, layer)
                if ns is None:
                    continue
                layers.append(layer)
                if layer != "----":
                    code = simplified_layers_to_code(tuple(layers))
                    if exclude_symmetry and not self._is_canonical(code):
                        layers.pop()
                        continue
                    else:
                        valid, classification, reason = self._is_valid_full_shape(code)
                    if valid and (query_regex is None or query_regex.search(code)):
                        yielded += 1
                        suffix = f" [{classification}]"
                        if reason:
                            suffix += f" {reason}"
                        yield code + suffix
                        if limit is not None and yielded >= limit:
                            layers.pop()
                            return
                yield from dfs(pos + 1, ns)
                if limit is not None and yielded >= limit:
                    layers.pop()
                    return
                layers.pop()

        yield from dfs(0, self._start_pillar_states())

    def count_valid_streaming(
        self,
        max_layers: int,
        query_regex=None,
        cancel_flag=None,
        progress=None,
        exclude_symmetry: bool = True,
    ) -> int:
        count = 0
        for count, _row in enumerate(
            self.generate_valid(max_layers, query_regex, None, cancel_flag, exclude_symmetry),
            start=1,
        ):
            if cancel_flag and cancel_flag():
                raise RuntimeError("cancelled")
            if progress and count % 1000 == 0:
                progress(count)
        return count


EXPECTED_COUNTS = {
    1: 4,
    2: 14,
    3: 47,
    4: 152,
    5: 476,
    6: 1450,
    7: 4320,
    8: 12645,
    9: 36500,
    10: 104191,
    11: 294743,
    12: 827579,
    13: 2309083,
    14: 6408106,
    15: 17700857,
    16: 48695444,
}


def wrap_long_token_text(text: str, width: int = 100) -> str:
    """Break very long uninterrupted tokens so Qt widgets never request huge width."""
    wrapped_lines: list[str] = []
    for line in str(text).splitlines() or [""]:
        chunks: list[str] = []
        for token in line.split(" "):
            if len(token) <= width:
                chunks.append(token)
                continue
            chunks.extend(token[i : i + width] for i in range(0, len(token), width))
        wrapped_lines.append(" ".join(chunks))
    return "\n".join(wrapped_lines)


def format_elapsed(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)}m {rest:.1f}s"


class CancelToken:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def is_cancelled(self) -> bool:
        return self.cancelled


class Worker(QObject):
    progress = pyqtSignal(int, int, str)
    batch = pyqtSignal(list)
    page_ready = pyqtSignal(list, bool)
    message = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        mode: str,
        engine,
        token: CancelToken,
        n: int = 0,
        regex_text: str = "",
        page_size: int = 1000,
        search_iter: Iterator[str] | None = None,
        save_path: str | None = None,
        exclude_symmetry: bool = True,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.engine = engine
        self.token = token
        self.n = n
        self.regex_text = regex_text
        self.page_size = page_size
        self.search_iter = search_iter
        self.save_path = save_path
        self.exclude_symmetry = exclude_symmetry

    def run(self) -> None:
        started = time.perf_counter()
        try:
            if self.mode == "count":
                self._run_count()
            elif self.mode == "full_count":
                self._run_full_count()
            elif self.mode in {"search_page", "full_search_page"}:
                self._run_search_page()
            elif self.mode in {"save", "full_save"}:
                self._run_save()
            elif self.mode == "selftest":
                self._run_selftest()
            else:
                raise ValueError(f"unknown worker mode: {self.mode}")
        except RuntimeError as exc:
            if str(exc) == "cancelled":
                self.finished.emit(f"Cancelled ({format_elapsed(time.perf_counter() - started)})")
            else:
                self.failed.emit(str(exc))
        except Exception as exc:  # GUI boundary: show the error instead of crashing.
            self.failed.emit(str(exc))

    def _compile_query(self):
        if not self.regex_text:
            return None
        return re.compile(self.regex_text)

    def _run_count(self) -> None:
        def progress(pos: int, total: int, states: int) -> None:
            self.progress.emit(pos, total, f"DP {pos}/{total}, states={states}")

        started = time.perf_counter()
        answer = self.engine.count_valid_dp(self.n, self.token.is_cancelled, progress)
        self.finished.emit(f"a{self.n} ({format_elapsed(time.perf_counter() - started)}) =\n{wrap_long_token_text(str(answer))}")

    def _run_search_page(self) -> None:
        if self.search_iter is None:
            raise ValueError("No active search session.")
        started = time.perf_counter()
        page: list[str] = []
        exhausted = False
        while len(page) < self.page_size:
            if self.token.is_cancelled():
                raise RuntimeError("cancelled")
            try:
                page.append(next(self.search_iter))
            except StopIteration:
                exhausted = True
                break
            if len(page) % 100 == 0:
                self.progress.emit(len(page), self.page_size, f"Loading page {len(page)}/{self.page_size}")
        self.page_ready.emit(page, exhausted)
        self.finished.emit(f"Page loaded: {len(page)} items ({format_elapsed(time.perf_counter() - started)})")

    def _run_full_count(self) -> None:
        started = time.perf_counter()
        query = self._compile_query()

        def progress(count: int) -> None:
            self.progress.emit(0, 0, f"Counting full shapes: {count}")

        answer = self.engine.count_valid_streaming(
            self.n,
            query,
            self.token.is_cancelled,
            progress,
            self.exclude_symmetry,
        )
        symmetry_note = (
            "Symmetry note: rotations and mirrors are excluded."
            if self.exclude_symmetry
            else "Symmetry note: rotations and mirrors are included."
        )
        self.finished.emit(
            f"Full shape count ({format_elapsed(time.perf_counter() - started)}) =\n"
            f"{wrap_long_token_text(str(answer))}\n"
            f"{symmetry_note}"
        )

    def _run_save(self) -> None:
        if not self.save_path:
            raise ValueError("Save path is missing.")
        started = time.perf_counter()
        query = self._compile_query()
        written = 0
        with Path(self.save_path).open("w", encoding="utf-8", newline="\n") as fp:
            if self.mode == "full_save":
                rows = self.engine.generate_valid(
                    self.n,
                    query,
                    None,
                    self.token.is_cancelled,
                    self.exclude_symmetry,
                )
            else:
                rows = self.engine.generate_valid(self.n, query, None, self.token.is_cancelled)
            for s in rows:
                fp.write(s + "\n")
                written += 1
                if written % 1000 == 0:
                    self.progress.emit(0, 0, f"{written} items saved")
        suffix = "cancelled" if self.token.is_cancelled() else "complete"
        self.finished.emit(f"File save {suffix}: {written} items ({format_elapsed(time.perf_counter() - started)})")

    def _run_selftest(self) -> None:
        started = time.perf_counter()
        lines: list[str] = []
        for idx, (n, expected) in enumerate(EXPECTED_COUNTS.items(), start=1):
            if self.token.is_cancelled():
                raise RuntimeError("cancelled")
            actual = self.engine.count_valid_dp(n, self.token.is_cancelled)
            self.progress.emit(idx, len(EXPECTED_COUNTS), f"Self Test n={n}")
            if actual != expected:
                lines.append(f"FAIL n={n}: expected={expected}, actual={actual}")
                self.batch.emit(lines)
                self.finished.emit(f"Self Test FAIL ({format_elapsed(time.perf_counter() - started)})")
                return
            lines.append(f"PASS n={n}: {actual}")
        self.batch.emit(lines)
        self.finished.emit(f"Self Test PASS ({format_elapsed(time.perf_counter() - started)})")


def default_settings() -> dict:
    return {
        "max_layer": 16,
        "page_size": 1000,
        "search_regex": "",
        "rules": dict(DEFAULT_RULE_MAP),
        "full_shape": {
            "max_layer": 5,
            "page_size": 1000,
            "search_regex": "",
            "exclude_symmetry": True,
        },
    }


def load_settings() -> dict:
    settings = default_settings()
    try:
        if SETTINGS_PATH.exists():
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update({key: value for key, value in loaded.items() if key != "rules"})
                rules = loaded.get("rules")
                if isinstance(rules, dict):
                    merged = dict(DEFAULT_RULE_MAP)
                    for name in DEFAULT_RULE_MAP:
                        value = rules.get(name)
                        if isinstance(value, str):
                            merged[name] = value
                    settings["rules"] = merged
                full_shape = loaded.get("full_shape")
                if isinstance(full_shape, dict):
                    merged_full = dict(settings["full_shape"])
                    merged_full.update(full_shape)
                    settings["full_shape"] = merged_full
    except Exception:
        return settings
    return settings


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        initial_specs = self._settings_rule_specs(self.settings)
        try:
            self.engine = RuleEngine(initial_specs)
            self.loaded_rules_valid = True
        except Exception:
            self.engine = RuleEngine(DEFAULT_RULE_SPECS)
            self.loaded_rules_valid = False
        self.full_engine = FullShapeEngine()
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self.token: CancelToken | None = None
        self.active_worker_mode = ""
        self.selftest_thread: QThread | None = None
        self.selftest_worker: Worker | None = None
        self.selftest_token: CancelToken | None = None
        self.search_iter: Iterator[str] | None = None
        self.search_pages: list[list[str]] = []
        self.current_page_index = -1
        self.search_exhausted = True
        self.search_query_text = ""
        self.search_n = 0
        self.search_page_size = 1000
        self.search_token: CancelToken | None = None
        self.current_page_header = ""
        self.full_search_iter: Iterator[str] | None = None
        self.full_search_pages: list[list[str]] = []
        self.full_current_page_index = -1
        self.full_search_exhausted = True
        self.full_search_query_text = ""
        self.full_search_n = 5
        self.full_search_page_size = 1000
        self.full_search_exclude_symmetry = True
        self.full_search_token: CancelToken | None = None
        self.full_current_page_header = ""
        self.setWindowTitle("Shapez2 Corners Rule Search")
        self.resize(980, 720)
        self._build_ui()
        if self._settings_use_default_rules():
            QTimer.singleShot(0, self.start_background_selftest)
        elif not self.loaded_rules_valid:
            self.statusBar().showMessage("Saved rules are invalid. Started with the default rule engine.")

    def _settings_rule_specs(self, settings: dict) -> tuple[RuleSpec, ...]:
        rules = settings.get("rules")
        if not isinstance(rules, dict):
            rules = DEFAULT_RULE_MAP
        return tuple(RuleSpec(name, str(rules.get(name, ""))) for name in DEFAULT_RULE_MAP)

    def _settings_use_default_rules(self) -> bool:
        rules = self.settings.get("rules")
        return isinstance(rules, dict) and all(str(rules.get(name, "")) == pattern for name, pattern in DEFAULT_RULE_MAP.items())

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 10, 14, 8)
        layout.setSpacing(8)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel("Corners Rule Search")
        title.setObjectName("titleLabel")
        subtitle = QLabel("DFA / DP regex counter")
        subtitle.setObjectName("subtitleLabel")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addStretch(1)
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        search_layout.setContentsMargins(0, 8, 0, 0)
        search_layout.setSpacing(8)

        controls_panel = QWidget()
        controls_panel.setObjectName("panel")
        form = QGridLayout(controls_panel)
        form.setContentsMargins(10, 8, 10, 8)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        self.length_spin = QSpinBox()
        self.length_spin.setRange(0, 10000)
        self.length_spin.setValue(int(self.settings.get("max_layer", 16)))
        self.regex_input = QLineEdit()
        self.regex_input.setPlaceholderText("Search regex, leave empty to show all valid strings")
        self.regex_input.setText(str(self.settings.get("search_regex", "")))
        self.regex_input.setMinimumWidth(0)
        self.regex_input.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(1, 1_000_000)
        self.page_size_spin.setValue(int(self.settings.get("page_size", 1000)))
        self.length_spin.setToolTip("Max layer")
        regex_help = (
            "The search regex filters which valid strings you want to see.\n"
            "This tool calculates bottom-up, building from shorter layers to longer layers.\n"
            "Leave it empty to page through all valid strings.\n\n"
            "Common examples:\n"
            "  c      : contains c\n"
            "  ^S     : starts with S\n"
            "  c$     : ends with c\n"
            "  S.*c   : S appears before a later c\n"
            "  ^S+$   : contains only S\n"
            "  [SP]   : contains S or P\n"
            "  -{2,}  : contains two or more consecutive - characters\n\n"
            "The search regex is applied only after forbidden rules are filtered."
        )
        self.regex_input.setToolTip(regex_help)
        self.page_size_spin.setToolTip("Items per page")
        self.regex_help_button = QPushButton()
        self.regex_help_button.setIcon(lucide_icon("circle-help"))
        self.regex_help_button.setToolTip(regex_help)
        self.regex_help_button.setAccessibleName("Regex search help")
        self.regex_help_button.setObjectName("iconButton")
        self.regex_help_button.setFixedSize(34, 32)
        self.regex_help_button.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.regex_help_text = regex_help
        form.addWidget(QLabel("Max Layer"), 0, 0)
        form.addWidget(self.length_spin, 0, 1)
        form.addWidget(QLabel("Items/Page"), 0, 2)
        form.addWidget(self.page_size_spin, 0, 3)
        form.addWidget(QLabel("Search Regex"), 1, 0)
        form.addWidget(self.regex_input, 1, 1, 1, 2)
        form.addWidget(self.regex_help_button, 1, 3)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        search_layout.addWidget(controls_panel)

        action_panel = QWidget()
        action_panel.setObjectName("toolbarPanel")
        buttons = QHBoxLayout(action_panel)
        buttons.setContentsMargins(8, 7, 8, 7)
        buttons.setSpacing(8)
        self.count_button = QPushButton("Count")
        self.count_button.setIcon(lucide_icon("calculator"))
        self.count_button.setToolTip("Count valid strings for the max layer.")
        self.search_button = QPushButton("Search")
        self.search_button.setIcon(lucide_icon("search", "#ffffff"))
        self.search_button.setObjectName("primaryButton")
        self.search_button.setToolTip("Show valid strings matching the search regex by page.")
        self.save_button = QPushButton("Save")
        self.save_button.setIcon(lucide_icon("save"))
        self.save_button.setToolTip("Stream matching search results to a file, one line at a time.")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setIcon(lucide_icon("x", "#b91c1c"))
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setToolTip("Cancel the current running task.")
        self.prev_page_button = QPushButton()
        self.prev_page_button.setIcon(lucide_icon("chevron-left"))
        self.prev_page_button.setToolTip("Previous page")
        self.prev_page_button.setAccessibleName("Previous page")
        self.prev_page_button.setObjectName("iconButton")
        self.prev_page_button.setFixedSize(34, 32)
        self.next_page_button = QPushButton()
        self.next_page_button.setIcon(lucide_icon("chevron-right"))
        self.next_page_button.setToolTip("Next page")
        self.next_page_button.setAccessibleName("Next page")
        self.next_page_button.setObjectName("iconButton")
        self.next_page_button.setFixedSize(34, 32)
        for button in (
            self.count_button,
            self.search_button,
            self.save_button,
            self.cancel_button,
            self.prev_page_button,
            self.next_page_button,
        ):
            button.setIconSize(QSize(18, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.addWidget(self.count_button)
        buttons.addWidget(self.search_button)
        buttons.addWidget(self.save_button)
        spacer = QFrame()
        spacer.setFrameShape(QFrame.Shape.VLine)
        spacer.setObjectName("toolbarDivider")
        buttons.addWidget(spacer)
        buttons.addWidget(self.prev_page_button)
        buttons.addWidget(self.next_page_button)
        buttons.addStretch(1)
        search_layout.addWidget(action_panel)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(8)
        self.progress_label = QLabel("Idle")
        self.progress_label.setObjectName("progressLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_row.addWidget(self.progress_label)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.cancel_button)
        search_layout.addLayout(progress_row)

        self.output = QTextEdit()
        self.output.setObjectName("outputBox")
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.output.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.output.setMinimumWidth(0)
        self.output.setMinimumHeight(320)
        self.output.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        search_layout.addWidget(self.output, 1)

        self.tabs.addTab(search_tab, "Search")
        self.tabs.addTab(self._build_full_shape_tab(), "Full Shape")
        self.tabs.addTab(self._build_rules_tab(), "Edit Rules")
        layout.addWidget(self.tabs, 1)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self._apply_style()
        self._connect_settings_signals()

        self.count_button.clicked.connect(self.count_valid)
        self.search_button.clicked.connect(self.search_regex)
        self.regex_help_button.clicked.connect(self.show_regex_help)
        self.prev_page_button.clicked.connect(self.previous_page)
        self.next_page_button.clicked.connect(self.next_page)
        self.save_button.clicked.connect(self.save_results)
        self.cancel_button.clicked.connect(self.cancel_current)
        self.full_search_button.clicked.connect(self.full_search_regex)
        self.full_count_button.clicked.connect(self.full_count_valid)
        self.full_prev_page_button.clicked.connect(self.full_previous_page)
        self.full_next_page_button.clicked.connect(self.full_next_page)
        self.full_save_button.clicked.connect(self.full_save_results)
        self.full_cancel_button.clicked.connect(self.cancel_current)
        self.apply_rules_button.clicked.connect(self.apply_custom_rules)
        self.reset_rules_button.clicked.connect(self.reset_default_rules)
        self.cancel_button.setVisible(False)
        self.cancel_button.setEnabled(False)
        self.full_cancel_button.setVisible(False)
        self.full_cancel_button.setEnabled(False)
        self.prev_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)
        self.full_prev_page_button.setEnabled(False)
        self.full_next_page_button.setEnabled(False)

    def _build_full_shape_tab(self) -> QWidget:
        full_settings = self.settings.get("full_shape") if isinstance(self.settings.get("full_shape"), dict) else {}

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        controls_panel = QWidget()
        controls_panel.setObjectName("panel")
        form = QGridLayout(controls_panel)
        form.setContentsMargins(10, 8, 10, 8)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)

        self.full_length_spin = QSpinBox()
        self.full_length_spin.setRange(1, 5)
        self.full_length_spin.setValue(int(full_settings.get("max_layer", 5)))
        self.full_length_spin.setToolTip("Maximum whole-shape layers. Default is 5.")

        self.full_page_size_spin = QSpinBox()
        self.full_page_size_spin.setRange(1, 1_000_000)
        self.full_page_size_spin.setValue(int(full_settings.get("page_size", 1000)))
        self.full_page_size_spin.setToolTip("Items per page")

        self.full_regex_input = QLineEdit()
        self.full_regex_input.setPlaceholderText("Search simplified full shape regex, leave empty to show all valid shapes")
        self.full_regex_input.setText(str(full_settings.get("search_regex", "")))
        self.full_regex_input.setMinimumWidth(0)
        self.full_regex_input.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.full_regex_input.setToolTip(
            "Regex is applied to simplified whole-shape codes such as SSSS or SS-c:P--S.\n"
            "Generation streams layer by layer and uses the existing classifier as final validation."
        )

        self.full_exclude_symmetry_check = QCheckBox("Exclude Symmetry")
        self.full_exclude_symmetry_check.setChecked(bool(full_settings.get("exclude_symmetry", True)))
        self.full_exclude_symmetry_check.setToolTip(
            "Checked: count/search only one representative per rotation/mirror group.\n"
            "Unchecked: include rotated and mirrored variants as separate results."
        )

        form.addWidget(QLabel("Max Layer"), 0, 0)
        form.addWidget(self.full_length_spin, 0, 1)
        form.addWidget(QLabel("Items/Page"), 0, 2)
        form.addWidget(self.full_page_size_spin, 0, 3)
        form.addWidget(QLabel("Search Regex"), 1, 0)
        form.addWidget(self.full_regex_input, 1, 1, 1, 2)
        form.addWidget(self.full_exclude_symmetry_check, 1, 3)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        layout.addWidget(controls_panel)

        action_panel = QWidget()
        action_panel.setObjectName("toolbarPanel")
        buttons = QHBoxLayout(action_panel)
        buttons.setContentsMargins(8, 7, 8, 7)
        buttons.setSpacing(8)

        self.full_search_button = QPushButton("Search")
        self.full_search_button.setIcon(lucide_icon("search", "#ffffff"))
        self.full_search_button.setObjectName("primaryButton")
        self.full_search_button.setToolTip("Stream valid full shapes matching the regex by page.")

        self.full_count_button = QPushButton("Count")
        self.full_count_button.setIcon(lucide_icon("calculator"))
        self.full_count_button.setToolTip(
            "Count valid full shapes matching the current regex. Rotations and mirrors are canonicalized."
        )

        self.full_save_button = QPushButton("Save")
        self.full_save_button.setIcon(lucide_icon("save"))
        self.full_save_button.setToolTip("Stream matching full-shape results to a file, one line at a time.")

        self.full_cancel_button = QPushButton("Cancel")
        self.full_cancel_button.setIcon(lucide_icon("x", "#b91c1c"))
        self.full_cancel_button.setObjectName("dangerButton")
        self.full_cancel_button.setToolTip("Cancel the current running task.")

        self.full_prev_page_button = QPushButton()
        self.full_prev_page_button.setIcon(lucide_icon("chevron-left"))
        self.full_prev_page_button.setToolTip("Previous page")
        self.full_prev_page_button.setAccessibleName("Previous page")
        self.full_prev_page_button.setObjectName("iconButton")
        self.full_prev_page_button.setFixedSize(34, 32)

        self.full_next_page_button = QPushButton()
        self.full_next_page_button.setIcon(lucide_icon("chevron-right"))
        self.full_next_page_button.setToolTip("Next page")
        self.full_next_page_button.setAccessibleName("Next page")
        self.full_next_page_button.setObjectName("iconButton")
        self.full_next_page_button.setFixedSize(34, 32)

        for button in (
            self.full_count_button,
            self.full_search_button,
            self.full_save_button,
            self.full_cancel_button,
            self.full_prev_page_button,
            self.full_next_page_button,
        ):
            button.setIconSize(QSize(18, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        buttons.addWidget(self.full_count_button)
        buttons.addWidget(self.full_search_button)
        buttons.addWidget(self.full_save_button)
        spacer = QFrame()
        spacer.setFrameShape(QFrame.Shape.VLine)
        spacer.setObjectName("toolbarDivider")
        buttons.addWidget(spacer)
        buttons.addWidget(self.full_prev_page_button)
        buttons.addWidget(self.full_next_page_button)
        buttons.addStretch(1)
        layout.addWidget(action_panel)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(8)
        self.full_progress_label = QLabel("Idle")
        self.full_progress_label.setObjectName("progressLabel")
        self.full_progress_bar = QProgressBar()
        self.full_progress_bar.setRange(0, 100)
        self.full_progress_bar.setValue(0)
        progress_row.addWidget(self.full_progress_label)
        progress_row.addWidget(self.full_progress_bar, 1)
        progress_row.addWidget(self.full_cancel_button)
        layout.addLayout(progress_row)

        self.full_output = QTextEdit()
        self.full_output.setObjectName("outputBox")
        self.full_output.setReadOnly(True)
        self.full_output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.full_output.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.full_output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.full_output.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.full_output.setMinimumWidth(0)
        self.full_output.setMinimumHeight(320)
        self.full_output.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.full_output, 1)

        return tab

    def _build_rules_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        panel = QWidget()
        panel.setObjectName("panel")
        grid = QGridLayout(panel)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)

        self.rule_inputs: dict[str, QLineEdit] = {}
        saved_rules = self.settings.get("rules") if isinstance(self.settings.get("rules"), dict) else DEFAULT_RULE_MAP
        for row, spec in enumerate(DEFAULT_RULE_SPECS):
            label = QLabel(spec.name)
            edit = QLineEdit(str(saved_rules.get(spec.name, spec.pattern)))
            edit.setMinimumWidth(0)
            edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            edit.setToolTip(
                "Forbidden-rule regex. Supported: ^, ., [], [^], (), |, *, +, ?, {m,n}.\n"
                "Alphabet is S, -, P, c. The end anchor $ is not supported here."
            )
            self.rule_inputs[spec.name] = edit
            grid.addWidget(label, row, 0)
            grid.addWidget(edit, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(panel)

        action_panel = QWidget()
        action_panel.setObjectName("toolbarPanel")
        row = QHBoxLayout(action_panel)
        row.setContentsMargins(8, 7, 8, 7)
        row.setSpacing(8)
        self.apply_rules_button = QPushButton("Apply")
        self.apply_rules_button.setIcon(lucide_icon("check"))
        self.apply_rules_button.setToolTip("Apply R1-R10 edits and rebuild the engine.")
        self.reset_rules_button = QPushButton("Reset")
        self.reset_rules_button.setIcon(lucide_icon("x"))
        self.reset_rules_button.setToolTip("Restore R1-R10 to the default rules.")
        for button in (self.apply_rules_button, self.reset_rules_button):
            button.setIconSize(QSize(18, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self.apply_rules_button)
        row.addWidget(self.reset_rules_button)
        row.addStretch(1)
        layout.addWidget(action_panel)

        layout.addStretch(1)
        return tab

    def _collect_settings(self) -> dict:
        rules = {
            name: edit.text()
            for name, edit in getattr(self, "rule_inputs", {}).items()
        }
        return {
            "max_layer": self.length_spin.value(),
            "page_size": self.page_size_spin.value(),
            "search_regex": self.regex_input.text(),
            "rules": rules,
            "full_shape": {
                "max_layer": self.full_length_spin.value(),
                "page_size": self.full_page_size_spin.value(),
                "search_regex": self.full_regex_input.text(),
                "exclude_symmetry": self.full_exclude_symmetry_check.isChecked(),
            },
        }

    def _save_settings(self) -> None:
        try:
            SETTINGS_PATH.write_text(
                json.dumps(self._collect_settings(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self.statusBar().showMessage(f"Failed to save settings: {exc}")

    def _connect_settings_signals(self) -> None:
        self.length_spin.valueChanged.connect(self._save_settings)
        self.page_size_spin.valueChanged.connect(self._save_settings)
        self.regex_input.textChanged.connect(self._save_settings)
        self.full_length_spin.valueChanged.connect(self._save_settings)
        self.full_page_size_spin.valueChanged.connect(self._save_settings)
        self.full_regex_input.textChanged.connect(self._save_settings)
        self.full_exclude_symmetry_check.stateChanged.connect(self._save_settings)
        for edit in self.rule_inputs.values():
            edit.textChanged.connect(self._save_settings)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#appRoot {
                background: #f6f8fb;
                color: #172033;
                font-family: "Segoe UI", "Inter", "Noto Sans KR", Arial, sans-serif;
                font-size: 13px;
            }
            QLabel#titleLabel {
                color: #111827;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: #64748b;
                font-size: 12px;
                font-weight: 500;
            }
            QWidget#panel, QWidget#toolbarPanel {
                background: #ffffff;
                border: 1px solid #e3e8f0;
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: 0;
                top: -1px;
            }
            QTabBar::tab {
                min-height: 28px;
                padding: 4px 14px;
                margin-right: 4px;
                color: #475569;
                background: #e9eef6;
                border: 1px solid #d8dee9;
                border-radius: 7px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                color: #ffffff;
                background: #2563eb;
                border-color: #2563eb;
            }
            QLineEdit, QSpinBox {
                min-height: 28px;
                padding: 3px 8px;
                background: #ffffff;
                border: 1px solid #d8dee9;
                border-radius: 7px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #2563eb;
                background: #fbfdff;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 18px;
                background: transparent;
                border: 0;
                margin-right: 4px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #eef2f7;
                border-radius: 4px;
            }
            QSpinBox::up-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #64748b;
            }
            QSpinBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 10px;
                color: #1f2937;
                background: #ffffff;
                border: 1px solid #d8dee9;
                border-radius: 7px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f8fafc;
                border-color: #cbd5e1;
            }
            QPushButton:pressed {
                background: #eef2f7;
            }
            QPushButton:disabled {
                color: #9aa4b2;
                background: #edf1f6;
                border-color: #e1e6ee;
            }
            QPushButton#primaryButton {
                color: #ffffff;
                background: #2563eb;
                border-color: #2563eb;
            }
            QPushButton#primaryButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
            QPushButton#dangerButton {
                color: #b91c1c;
                background: #fff7f7;
                border-color: #fecaca;
            }
            QPushButton#dangerButton:hover {
                background: #fee2e2;
            }
            QPushButton#iconButton {
                min-width: 34px;
                max-width: 34px;
                padding: 0;
                border-radius: 7px;
            }
            QFrame#toolbarDivider {
                color: #d8dee9;
                margin-left: 4px;
                margin-right: 2px;
            }
            QLabel#progressLabel {
                color: #334155;
                min-width: 120px;
                font-weight: 600;
            }
            QProgressBar {
                min-height: 10px;
                max-height: 10px;
                border: 0;
                border-radius: 5px;
                background: #e5eaf2;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 5px;
                background: #2563eb;
            }
            QTextEdit#outputBox {
                background: #0f172a;
                color: #e5edf7;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
                font-family: "Cascadia Mono", "Consolas", "D2Coding", monospace;
                font-size: 12px;
            }
            QStatusBar {
                background: #f6f8fb;
                color: #64748b;
                border-top: 1px solid #e3e8f0;
            }
            QToolTip {
                color: #f8fafc;
                background: #111827;
                border: 0;
                padding: 6px 8px;
                border-radius: 6px;
            }
            """
        )

    def _set_busy(self, busy: bool) -> None:
        for button in (
            self.count_button,
            self.search_button,
            self.save_button,
            self.full_count_button,
            self.full_search_button,
            self.full_save_button,
            self.full_exclude_symmetry_check,
            self.apply_rules_button,
            self.reset_rules_button,
        ):
            button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.cancel_button.setVisible(busy)
        self.full_cancel_button.setEnabled(busy)
        self.full_cancel_button.setVisible(busy)
        self._update_page_buttons()

    def _update_page_buttons(self) -> None:
        busy = self.thread is not None
        self.prev_page_button.setEnabled(not busy and self.current_page_index > 0)
        has_cached_next = self.current_page_index + 1 < len(self.search_pages)
        can_fetch_next = self.search_iter is not None and not self.search_exhausted
        self.next_page_button.setEnabled(not busy and (has_cached_next or can_fetch_next))
        self.full_prev_page_button.setEnabled(not busy and self.full_current_page_index > 0)
        has_cached_full_next = self.full_current_page_index + 1 < len(self.full_search_pages)
        can_fetch_full_next = self.full_search_iter is not None and not self.full_search_exhausted
        self.full_next_page_button.setEnabled(not busy and (has_cached_full_next or can_fetch_full_next))

    def _clear_search_session(self) -> None:
        if self.search_token:
            self.search_token.cancel()
        self.search_iter = None
        self.search_pages = []
        self.current_page_index = -1
        self.search_exhausted = True
        self.current_page_header = ""
        self._update_page_buttons()

    def _clear_full_search_session(self) -> None:
        if self.full_search_token:
            self.full_search_token.cancel()
        self.full_search_iter = None
        self.full_search_pages = []
        self.full_current_page_index = -1
        self.full_search_exhausted = True
        self.full_current_page_header = ""
        self._update_page_buttons()

    def apply_custom_rules(self) -> None:
        if self.thread is not None:
            QMessageBox.warning(self, "Busy", "Apply rules after the running task finishes.")
            return
        specs = tuple(
            RuleSpec(name, edit.text().strip())
            for name, edit in self.rule_inputs.items()
        )
        try:
            self.engine = RuleEngine(specs)
        except Exception as exc:
            QMessageBox.critical(self, "Rule Error", str(exc))
            self.statusBar().showMessage("Failed to apply rules")
            return
        self._save_settings()
        self._clear_search_session()
        self.progress_label.setText("Rules applied")
        self.statusBar().showMessage("Rules applied")

    def reset_default_rules(self) -> None:
        if self.thread is not None:
            QMessageBox.warning(self, "Busy", "Reset rules after the running task finishes.")
            return
        for spec in DEFAULT_RULE_SPECS:
            self.rule_inputs[spec.name].setText(spec.pattern)
        self.engine = RuleEngine(DEFAULT_RULE_SPECS)
        self._save_settings()
        self._clear_search_session()
        self.progress_label.setText("Default rules restored")
        self.statusBar().showMessage("Default rules restored")

    def _start_worker(self, mode: str, **kwargs) -> None:
        if self.thread is not None:
            QMessageBox.warning(self, "Busy", "A task is already running.")
            return
        engine = kwargs.pop("engine", self.engine)
        self.active_worker_mode = mode
        if mode.startswith("full_"):
            self.full_output.clear()
            self.full_progress_bar.setValue(0)
            self.full_progress_label.setText("Starting")
        else:
            self.output.clear()
            self.progress_bar.setValue(0)
            self.progress_label.setText("Starting")
        self.token = CancelToken()
        self.thread = QThread()
        self.worker = Worker(mode, engine, self.token, **kwargs)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.batch.connect(self.on_batch)
        self.worker.page_ready.connect(self.on_page_ready)
        self.worker.message.connect(self.statusBar().showMessage)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self._set_busy(True)
        self.thread.start()

    def _cleanup_thread(self) -> None:
        if self.worker:
            self.worker.deleteLater()
        if self.thread:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.token = None
        self.active_worker_mode = ""
        self._set_busy(False)

    def start_background_selftest(self) -> None:
        if self.selftest_thread is not None:
            return
        self.selftest_token = CancelToken()
        self.selftest_thread = QThread()
        self.selftest_worker = Worker("selftest", self.engine, self.selftest_token)
        self.selftest_worker.moveToThread(self.selftest_thread)
        self.selftest_thread.started.connect(self.selftest_worker.run)
        self.selftest_worker.progress.connect(
            lambda value, total, text: self.statusBar().showMessage(f"{text} ({value}/{total})")
        )
        self.selftest_worker.batch.connect(self.on_background_selftest_batch)
        self.selftest_worker.finished.connect(self.on_background_selftest_finished)
        self.selftest_worker.failed.connect(self.on_background_selftest_failed)
        self.selftest_worker.finished.connect(self.selftest_thread.quit)
        self.selftest_worker.failed.connect(self.selftest_thread.quit)
        self.selftest_thread.finished.connect(self._cleanup_selftest_thread)
        self.selftest_thread.start()

    def _cleanup_selftest_thread(self) -> None:
        if self.selftest_worker:
            self.selftest_worker.deleteLater()
        if self.selftest_thread:
            self.selftest_thread.deleteLater()
        self.selftest_worker = None
        self.selftest_thread = None
        self.selftest_token = None

    def on_background_selftest_batch(self, rows: list) -> None:
        failures = [str(row) for row in rows if str(row).startswith("FAIL")]
        if failures:
            self.output.setPlainText("\n".join(failures))

    def on_background_selftest_finished(self, text: str) -> None:
        if "FAIL" in text:
            self.output.setPlainText(text)
            self.progress_label.setText("Self Test FAIL")
        else:
            self.statusBar().showMessage("Self Test PASS")

    def on_background_selftest_failed(self, text: str) -> None:
        self.output.setPlainText(f"Self Test ERROR: {text}")
        self.progress_label.setText("Self Test ERROR")

    def on_progress(self, value: int, total: int, text: str) -> None:
        label = self.full_progress_label if self.active_worker_mode.startswith("full_") else self.progress_label
        bar = self.full_progress_bar if self.active_worker_mode.startswith("full_") else self.progress_bar
        label.setText(text)
        if total > 0:
            bar.setRange(0, total)
            bar.setValue(value)
        else:
            bar.setRange(0, 0)

    def on_batch(self, rows: list) -> None:
        self.output.append("\n".join(wrap_long_token_text(str(row)) for row in rows))

    def on_page_ready(self, page: list, exhausted: bool) -> None:
        if self.active_worker_mode.startswith("full_"):
            if page:
                self.full_search_pages.append([str(row) for row in page])
                self.full_current_page_index = len(self.full_search_pages) - 1
            elif not self.full_search_pages:
                self.full_current_page_index = -1
            self.full_search_exhausted = exhausted
            self._show_full_current_page()
            return
        if page:
            self.search_pages.append([str(row) for row in page])
            self.current_page_index = len(self.search_pages) - 1
        elif not self.search_pages:
            self.current_page_index = -1
        self.search_exhausted = exhausted
        self._show_current_page()

    def on_finished(self, text: str) -> None:
        status_text = text.splitlines()[0] if text else "Done"
        is_full = self.active_worker_mode.startswith("full_")
        current_header = self.full_current_page_header if is_full else self.current_page_header
        if text.startswith("Page loaded") and current_header:
            elapsed = ""
            if "(" in text and text.endswith(")"):
                elapsed = " " + text[text.rfind("(") :]
            status_text = current_header + elapsed
        if len(status_text) > 80:
            status_text = "Task complete"
        label = self.full_progress_label if is_full else self.progress_label
        bar = self.full_progress_bar if is_full else self.progress_bar
        output = self.full_output if is_full else self.output
        label.setText(status_text)
        bar.setRange(0, 100)
        bar.setValue(100)
        if not text.startswith("Page loaded"):
            output.append(wrap_long_token_text(text))
        self.statusBar().showMessage(status_text)
        self._update_page_buttons()

    def on_failed(self, text: str) -> None:
        is_full = self.active_worker_mode.startswith("full_")
        label = self.full_progress_label if is_full else self.progress_label
        output = self.full_output if is_full else self.output
        label.setText("Error")
        output.append(f"ERROR: {text}")
        self.statusBar().showMessage(text)
        QMessageBox.critical(self, "Error", text)
        self._update_page_buttons()

    def show_regex_help(self) -> None:
        QMessageBox.information(self, "Regex Search Help", self.regex_help_text)

    def _show_current_page(self) -> None:
        self.output.clear()
        if self.current_page_index < 0:
            self.current_page_header = "No search results"
            self.output.append("No search results")
            self.output.verticalScrollBar().setValue(0)
            self.progress_label.setText("No search results")
            self.statusBar().showMessage("No search results")
            self._update_page_buttons()
            return

        page = self.search_pages[self.current_page_index]
        start_no = self.current_page_index * self.search_page_size + 1
        end_no = start_no + len(page) - 1
        header = (
            f"Page {self.current_page_index + 1} "
            f"({start_no}-{end_no}, {len(page)} items)"
        )
        if self.search_exhausted and self.current_page_index == len(self.search_pages) - 1:
            header += " / Last page"
        self.current_page_header = header
        self.output.append(header)
        self.output.append("")
        self.output.append("\n".join(wrap_long_token_text(str(row)) for row in page))
        self.output.moveCursor(self.output.textCursor().MoveOperation.Start)
        self.output.verticalScrollBar().setValue(0)
        self.progress_label.setText(header)
        self.statusBar().showMessage(header)
        self._update_page_buttons()

    def _show_full_current_page(self) -> None:
        self.full_output.clear()
        if self.full_current_page_index < 0:
            self.full_current_page_header = "No full-shape results"
            self.full_output.append("No full-shape results")
            self.full_output.verticalScrollBar().setValue(0)
            self.full_progress_label.setText("No full-shape results")
            self.statusBar().showMessage("No full-shape results")
            self._update_page_buttons()
            return

        page = self.full_search_pages[self.full_current_page_index]
        start_no = self.full_current_page_index * self.full_search_page_size + 1
        end_no = start_no + len(page) - 1
        header = (
            f"Full Shape Page {self.full_current_page_index + 1} "
            f"({start_no}-{end_no}, {len(page)} items)"
        )
        if self.full_search_exhausted and self.full_current_page_index == len(self.full_search_pages) - 1:
            header += " / Last page"
        self.full_current_page_header = header
        self.full_output.append(header)
        self.full_output.append("")
        self.full_output.append("\n".join(wrap_long_token_text(str(row)) for row in page))
        self.full_output.moveCursor(self.full_output.textCursor().MoveOperation.Start)
        self.full_output.verticalScrollBar().setValue(0)
        self.full_progress_label.setText(header)
        self.statusBar().showMessage(header)
        self._update_page_buttons()

    def count_valid(self) -> None:
        self._start_worker("count", n=self.length_spin.value())

    def search_regex(self) -> None:
        regex_text = self.regex_input.text().strip()
        try:
            query = re.compile(regex_text) if regex_text else None
        except re.error as exc:
            QMessageBox.warning(self, "Regex Error", str(exc))
            return
        self.search_pages = []
        self.current_page_index = -1
        self.search_exhausted = False
        self.search_query_text = regex_text
        self.search_n = self.length_spin.value()
        self.search_page_size = self.page_size_spin.value()
        self.search_token = CancelToken()
        self.search_iter = self.engine.generate_valid(
            self.search_n,
            query,
            None,
            self.search_token.is_cancelled,
        )
        self._fetch_next_page()

    def _fetch_next_page(self) -> None:
        if self.search_iter is None or self.search_exhausted:
            self._update_page_buttons()
            return
        self._start_worker(
            "search_page",
            n=self.search_n,
            page_size=self.search_page_size,
            search_iter=self.search_iter,
        )

    def next_page(self) -> None:
        if self.current_page_index + 1 < len(self.search_pages):
            self.current_page_index += 1
            self._show_current_page()
            return
        self._fetch_next_page()

    def previous_page(self) -> None:
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._show_current_page()

    def full_count_valid(self) -> None:
        regex_text = self.full_regex_input.text().strip()
        try:
            if regex_text:
                re.compile(regex_text)
        except re.error as exc:
            QMessageBox.warning(self, "Regex Error", str(exc))
            return
        self._start_worker(
            "full_count",
            engine=self.full_engine,
            n=self.full_length_spin.value(),
            regex_text=regex_text,
            exclude_symmetry=self.full_exclude_symmetry_check.isChecked(),
        )

    def full_search_regex(self) -> None:
        regex_text = self.full_regex_input.text().strip()
        try:
            query = re.compile(regex_text) if regex_text else None
        except re.error as exc:
            QMessageBox.warning(self, "Regex Error", str(exc))
            return
        self.full_search_pages = []
        self.full_current_page_index = -1
        self.full_search_exhausted = False
        self.full_search_query_text = regex_text
        self.full_search_n = self.full_length_spin.value()
        self.full_search_page_size = self.full_page_size_spin.value()
        self.full_search_exclude_symmetry = self.full_exclude_symmetry_check.isChecked()
        self.full_search_token = CancelToken()
        self.full_search_iter = self.full_engine.generate_valid(
            self.full_search_n,
            query,
            None,
            self.full_search_token.is_cancelled,
            self.full_search_exclude_symmetry,
        )
        self._fetch_full_next_page()

    def _fetch_full_next_page(self) -> None:
        if self.full_search_iter is None or self.full_search_exhausted:
            self._update_page_buttons()
            return
        self._start_worker(
            "full_search_page",
            engine=self.full_engine,
            n=self.full_search_n,
            page_size=self.full_search_page_size,
            search_iter=self.full_search_iter,
        )

    def full_next_page(self) -> None:
        if self.full_current_page_index + 1 < len(self.full_search_pages):
            self.full_current_page_index += 1
            self._show_full_current_page()
            return
        self._fetch_full_next_page()

    def full_previous_page(self) -> None:
        if self.full_current_page_index > 0:
            self.full_current_page_index -= 1
            self._show_full_current_page()

    def full_save_results(self) -> None:
        regex_text = self.full_regex_input.text().strip()
        try:
            if regex_text:
                re.compile(regex_text)
        except re.error as exc:
            QMessageBox.warning(self, "Regex Error", str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Full Shape Results", "full_shape_results.txt", "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        self._start_worker(
            "full_save",
            engine=self.full_engine,
            n=self.full_length_spin.value(),
            regex_text=regex_text,
            save_path=path,
            exclude_symmetry=self.full_exclude_symmetry_check.isChecked(),
        )

    def save_results(self) -> None:
        regex_text = self.regex_input.text().strip()
        try:
            if regex_text:
                re.compile(regex_text)
        except re.error as exc:
            QMessageBox.warning(self, "Regex Error", str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Search Results", "results.txt", "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        self._start_worker("save", n=self.length_spin.value(), regex_text=regex_text, save_path=path)

    def cancel_current(self) -> None:
        if self.token:
            self.token.cancel()
        if self.search_token:
            self.search_token.cancel()
            self.search_exhausted = True
        if self.full_search_token:
            self.full_search_token.cancel()
            self.full_search_exhausted = True
        self.progress_label.setText("Cancel requested")
        self.full_progress_label.setText("Cancel requested")
        self.statusBar().showMessage("Cancel requested")


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
