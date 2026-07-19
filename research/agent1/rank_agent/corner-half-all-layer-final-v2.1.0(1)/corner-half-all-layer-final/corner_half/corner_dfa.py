"""Exact all-layer craftable-column recognizer for Shapez 2 quad mode.

The accepted language is the six-forbidden-pattern characterization from the
column theorem.  This module compiles those rules into a deterministic,
minimized DFA.  It is independent of the GUI and of the mutable legacy Shape
class.

Alphabet: ``- S P c``.  Input is one column, bottom to top, with trailing
empty cells removed.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Iterable, Iterator, Mapping

ALPHABET = ("-", "S", "P", "c")
Symbol = frozenset[str] | None

# The theorem-normalized rules.  R5 is written as cS-+c.  Some legacy
# code uses c.-+c; under R1/R3/R4 the two six-rule conjunctions appear
# equivalent, but this branch keeps the statement used by the proof.
FORBIDDEN_RULES: tuple[tuple[str, str], ...] = (
    ("R1", r"-P"),
    ("R2", r"^P*-+c"),
    ("R3", r"[^P]P.*c"),
    ("R4", r"c-.*c"),
    ("R5", r"cS-+c"),
    ("R6", r"^S*-?S*c(.*c)?(S-+)+c"),
)


@dataclass(frozen=True)
class Fragment:
    start: int
    accepts: frozenset[int]


class NFABuilder:
    def __init__(self) -> None:
        self.next_id = 0
        self.transitions: dict[int, dict[Symbol, set[int]]] = defaultdict(
            lambda: defaultdict(set)
        )

    def new_state(self) -> int:
        sid = self.next_id
        self.next_id += 1
        return sid

    def add_edge(self, src: int, symbol: Symbol, dst: int) -> None:
        self.transitions[src][symbol].add(dst)

    def literal(self, ch: str) -> Fragment:
        a, b = self.new_state(), self.new_state()
        self.add_edge(a, frozenset({ch}), b)
        return Fragment(a, frozenset({b}))

    def any_char(self) -> Fragment:
        a, b = self.new_state(), self.new_state()
        self.add_edge(a, frozenset(ALPHABET), b)
        return Fragment(a, frozenset({b}))

    def char_set(self, chars: Iterable[str]) -> Fragment:
        a, b = self.new_state(), self.new_state()
        self.add_edge(a, frozenset(chars), b)
        return Fragment(a, frozenset({b}))

    def concat(self, *parts: Fragment) -> Fragment:
        if not parts:
            a = self.new_state()
            return Fragment(a, frozenset({a}))
        cur = parts[0]
        for nxt in parts[1:]:
            for accept in cur.accepts:
                self.add_edge(accept, None, nxt.start)
            cur = Fragment(cur.start, nxt.accepts)
        return cur

    def alternate(self, *parts: Fragment) -> Fragment:
        a, b = self.new_state(), self.new_state()
        for part in parts:
            self.add_edge(a, None, part.start)
            for accept in part.accepts:
                self.add_edge(accept, None, b)
        return Fragment(a, frozenset({b}))

    def star(self, part: Fragment) -> Fragment:
        a, b = self.new_state(), self.new_state()
        self.add_edge(a, None, b)
        self.add_edge(a, None, part.start)
        for accept in part.accepts:
            self.add_edge(accept, None, b)
            self.add_edge(accept, None, part.start)
        return Fragment(a, frozenset({b}))

    def plus(self, part: Fragment) -> Fragment:
        a, b = self.new_state(), self.new_state()
        self.add_edge(a, None, part.start)
        for accept in part.accepts:
            self.add_edge(accept, None, b)
            self.add_edge(accept, None, part.start)
        return Fragment(a, frozenset({b}))

    def optional(self, part: Fragment) -> Fragment:
        a, b = self.new_state(), self.new_state()
        self.add_edge(a, None, b)
        self.add_edge(a, None, part.start)
        for accept in part.accepts:
            self.add_edge(accept, None, b)
        return Fragment(a, frozenset({b}))


@dataclass(frozen=True)
class Ast:
    kind: str
    value: object = None


class RegexParser:
    """Parser for the tiny regex subset used by R1..R6."""

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self.pos = 0
        self.anchored = False

    def parse(self) -> tuple[bool, Ast]:
        if self.pattern.startswith("^"):
            self.anchored = True
            self.pattern = self.pattern[1:]
        ast = self._alt()
        if self.pos != len(self.pattern):
            raise ValueError(f"unexpected regex input at {self.pos}")
        return self.anchored, ast

    def _peek(self) -> str | None:
        return self.pattern[self.pos] if self.pos < len(self.pattern) else None

    def _take(self) -> str:
        ch = self.pattern[self.pos]
        self.pos += 1
        return ch

    def _alt(self) -> Ast:
        parts = [self._seq()]
        while self._peek() == "|":
            self._take()
            parts.append(self._seq())
        return parts[0] if len(parts) == 1 else Ast("alt", parts)

    def _seq(self) -> Ast:
        parts: list[Ast] = []
        while self._peek() is not None and self._peek() not in ")|":
            parts.append(self._repeat())
        if not parts:
            return Ast("empty")
        return parts[0] if len(parts) == 1 else Ast("concat", parts)

    def _repeat(self) -> Ast:
        atom = self._atom()
        if self._peek() in ("*", "+", "?"):
            return Ast("repeat", (atom, self._take()))
        return atom

    def _atom(self) -> Ast:
        ch = self._peek()
        if ch is None:
            return Ast("empty")
        if ch == "(":
            self._take()
            out = self._alt()
            if self._peek() != ")":
                raise ValueError("missing )")
            self._take()
            return out
        if ch == ".":
            self._take()
            return Ast("any")
        if ch == "[":
            return self._class()
        ch = self._take()
        if ch not in ALPHABET:
            raise ValueError(f"unsupported literal {ch!r}")
        return Ast("lit", ch)

    def _class(self) -> Ast:
        self._take()
        negated = self._peek() == "^"
        if negated:
            self._take()
        chars: set[str] = set()
        while self._peek() not in (None, "]"):
            chars.add(self._take())
        if self._peek() != "]":
            raise ValueError("missing ]")
        self._take()
        if negated:
            chars = set(ALPHABET) - chars
        return Ast("set", frozenset(chars))


def _build_ast(ast: Ast, b: NFABuilder) -> Fragment:
    if ast.kind == "empty":
        return b.concat()
    if ast.kind == "lit":
        return b.literal(str(ast.value))
    if ast.kind == "set":
        return b.char_set(ast.value)  # type: ignore[arg-type]
    if ast.kind == "any":
        return b.any_char()
    if ast.kind == "concat":
        return b.concat(*(_build_ast(x, b) for x in ast.value))  # type: ignore[union-attr]
    if ast.kind == "alt":
        return b.alternate(*(_build_ast(x, b) for x in ast.value))  # type: ignore[union-attr]
    if ast.kind == "repeat":
        child, quant = ast.value  # type: ignore[misc]
        part = _build_ast(child, b)
        return {"*": b.star, "+": b.plus, "?": b.optional}[quant](part)
    raise AssertionError(ast.kind)


@dataclass(frozen=True)
class RuleNFA:
    name: str
    anchored: bool
    accepts: frozenset[int]
    transitions: tuple[tuple[tuple[Symbol, tuple[int, ...]], ...], ...]
    eps: tuple[frozenset[int], ...]
    start: frozenset[int]

    @classmethod
    def compile(cls, name: str, pattern: str) -> "RuleNFA":
        anchored, ast = RegexParser(pattern).parse()
        b = NFABuilder()
        frag = _build_ast(ast, b)
        raw: list[list[tuple[Symbol, tuple[int, ...]]]] = [
            [] for _ in range(b.next_id)
        ]
        for src, edges in b.transitions.items():
            for symbol, dsts in edges.items():
                raw[src].append((symbol, tuple(sorted(dsts))))
        trans = tuple(tuple(xs) for xs in raw)

        def closure(seed: Iterable[int]) -> frozenset[int]:
            seen = set(seed)
            stack = list(seen)
            while stack:
                s = stack.pop()
                for symbol, dsts in trans[s]:
                    if symbol is None:
                        for d in dsts:
                            if d not in seen:
                                seen.add(d)
                                stack.append(d)
            return frozenset(seen)

        eps = tuple(closure([i]) for i in range(b.next_id))
        return cls(name, anchored, frag.accepts, trans, eps, closure([frag.start]))

    def advance(self, active: frozenset[int], ch: str) -> frozenset[int]:
        reached: set[int] = set()
        for state in active:
            for symbol, dsts in self.transitions[state]:
                if symbol is not None and ch in symbol:
                    reached.update(dsts)
        out: set[int] = set()
        for state in reached:
            out.update(self.eps[state])
        return frozenset(out)


RawState = tuple[frozenset[int], ...]


@dataclass(frozen=True)
class RejectionCertificate:
    rule: str
    position: int
    prefix: str


@dataclass(frozen=True)
class CornerDFA:
    transitions: tuple[tuple[int, int, int, int], ...]
    start: int
    reject: int
    state_count: int

    def step(self, state: int, ch: str) -> int:
        try:
            index = ALPHABET.index(ch)
        except ValueError as exc:
            raise ValueError(f"invalid column symbol {ch!r}") from exc
        return self.transitions[state][index]

    def accepts(self, column: str) -> bool:
        state = self.start
        for ch in normalize_column(column):
            state = self.step(state, ch)
            if state == self.reject:
                return False
        return True


RULE_NFAS = tuple(RuleNFA.compile(name, pattern) for name, pattern in FORBIDDEN_RULES)


def normalize_column(column: str) -> str:
    column = column.strip().rstrip("-")
    bad = set(column) - set(ALPHABET)
    if bad:
        raise ValueError(f"invalid column alphabet: {sorted(bad)!r}")
    return column


def _raw_start() -> RawState:
    return tuple(rule.start for rule in RULE_NFAS)


def _raw_step(state: RawState, ch: str) -> RawState | None:
    next_active: list[frozenset[int]] = []
    for rule, active in zip(RULE_NFAS, state):
        current = active if rule.anchored else active | rule.start
        moved = rule.advance(current, ch)
        if moved & rule.accepts:
            return None
        next_active.append(moved)
    return tuple(next_active)


def first_rejection(column: str) -> RejectionCertificate | None:
    state = _raw_start()
    prefix = ""
    for pos, ch in enumerate(normalize_column(column)):
        prefix += ch
        for rule, active in zip(RULE_NFAS, state):
            current = active if rule.anchored else active | rule.start
            moved = rule.advance(current, ch)
            if moved & rule.accepts:
                return RejectionCertificate(rule.name, pos, prefix)
        nxt = _raw_step(state, ch)
        assert nxt is not None
        state = nxt
    return None


def _determinize() -> tuple[list[list[int]], int, int]:
    start_raw = _raw_start()
    ids: dict[RawState | None, int] = {None: 0, start_raw: 1}
    queue: deque[RawState] = deque([start_raw])
    table: list[list[int]] = [[0] * len(ALPHABET), [0] * len(ALPHABET)]
    while queue:
        state = queue.popleft()
        sid = ids[state]
        while len(table) <= sid:
            table.append([0] * len(ALPHABET))
        for i, ch in enumerate(ALPHABET):
            nxt = _raw_step(state, ch)
            if nxt not in ids:
                ids[nxt] = len(ids)
                table.append([0] * len(ALPHABET))
                if nxt is not None:
                    queue.append(nxt)
            table[sid][i] = ids[nxt]
    table[0] = [0] * len(ALPHABET)
    return table, 1, 0


def _minimize(table: list[list[int]], start: int, reject: int) -> CornerDFA:
    n = len(table)
    accepting = frozenset(range(n)) - {reject}
    partitions: list[set[int]] = [set(accepting), {reject}]
    changed = True
    while changed:
        changed = False
        block_of = {s: i for i, block in enumerate(partitions) for s in block}
        refined: list[set[int]] = []
        for block in partitions:
            groups: dict[tuple[int, ...], set[int]] = defaultdict(set)
            for s in block:
                sig = tuple(block_of[table[s][a]] for a in range(len(ALPHABET)))
                groups[sig].add(s)
            refined.extend(groups.values())
            changed |= len(groups) > 1
        partitions = refined
    block_of = {s: i for i, block in enumerate(partitions) for s in block}
    min_table: list[tuple[int, int, int, int]] = []
    for block in partitions:
        rep = next(iter(block))
        min_table.append(tuple(block_of[table[rep][a]] for a in range(4)))
    return CornerDFA(
        transitions=tuple(min_table),
        start=block_of[start],
        reject=block_of[reject],
        state_count=len(partitions),
    )


@lru_cache(maxsize=1)
def build_minimized_dfa() -> CornerDFA:
    return _minimize(*_determinize())


def is_craftable_column(column: str) -> bool:
    return build_minimized_dfa().accepts(column)


def count_craftable(length: int) -> int:
    if length < 0:
        raise ValueError("length must be nonnegative")
    dfa = build_minimized_dfa()
    counts = [0] * dfa.state_count
    counts[dfa.start] = 1
    for _ in range(length):
        nxt = [0] * dfa.state_count
        for state, count in enumerate(counts):
            if not count or state == dfa.reject:
                continue
            for dst in dfa.transitions[state]:
                if dst != dfa.reject:
                    nxt[dst] += count
        counts = nxt
    return sum(counts[state] for state in range(dfa.state_count) if state != dfa.reject)


def export_transition_table() -> Mapping[str, object]:
    dfa = build_minimized_dfa()
    return {
        "alphabet": ALPHABET,
        "start": dfa.start,
        "reject": dfa.reject,
        "state_count": dfa.state_count,
        "transitions": dfa.transitions,
    }
