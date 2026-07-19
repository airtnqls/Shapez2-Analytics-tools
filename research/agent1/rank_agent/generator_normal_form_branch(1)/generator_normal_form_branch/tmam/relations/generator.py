"""All-layer Crystal Generator normal form and family-constrained inverse.

This module is intentionally independent from the project's mutable ``Shape``
implementation and from the future CompactShape backend.  Its structural core
uses one byte per layer (two bits per quadrant):

    0 = empty, 1 = normal part, 2 = pin, 3 = crystal

Layers are ordered bottom -> top and trailing empty layers are trimmed.

The Crystal Generator with color k has the exact semantics:

* let H be the input's global height;
* for every cell below H, empty and pin become a k-colored crystal;
* normal pieces and existing crystals are preserved;
* nothing above H is created;
* no gravity pass follows.

For inverse search, the target must therefore be a completely occupied,
pin-free H x 4 slab.  A target crystal of the selected generator color may
have been empty, pin, or the same crystal in the predecessor.  Every other
cell is fixed.  This local relation is represented as a GeneratorConstraint
and intersected directly with a finite-state family; concrete predecessors are
not enumerated in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from typing import (
    Callable,
    Generic,
    Hashable,
    Iterable,
    Iterator,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    runtime_checkable,
)


class CellKind(IntEnum):
    EMPTY = 0
    NORMAL = 1
    PIN = 2
    CRYSTAL = 3


EMPTY = int(CellKind.EMPTY)
NORMAL = int(CellKind.NORMAL)
PIN = int(CellKind.PIN)
CRYSTAL = int(CellKind.CRYSTAL)
FULL_ROW_MASK = 0b1111

SIMPLIFIED_TO_KIND = {
    "-": EMPTY,
    "S": NORMAL,
    "P": PIN,
    "c": CRYSTAL,
}
KIND_TO_SIMPLIFIED = "-SPc"


class GeneratorError(ValueError):
    """Base class for Generator relation errors."""


class NotGeneratorImage(GeneratorError):
    """The target cannot be the output of the selected Generator operation."""


class NoGeneratorPredecessor(GeneratorError):
    """No predecessor satisfying the supplied family exists."""


class GeneratorCertificateError(AssertionError):
    """A produced witness failed forward replay."""


LayerWord = int
StructuralShape = tuple[LayerWord, ...]
StateT = TypeVar("StateT", bound=Hashable)


def get_cell(row: LayerWord, quadrant: int) -> int:
    if not 0 <= quadrant < 4:
        raise IndexError("quadrant must be in 0..3")
    return (row >> (quadrant * 2)) & 0b11


def set_cell(row: LayerWord, quadrant: int, kind: int) -> LayerWord:
    if not 0 <= quadrant < 4:
        raise IndexError("quadrant must be in 0..3")
    if not 0 <= int(kind) <= 3:
        raise ValueError("cell kind must be in 0..3")
    shift = quadrant * 2
    return (row & ~(0b11 << shift)) | (int(kind) << shift)


def encode_row(chars: str) -> LayerWord:
    chars = chars.strip()
    if len(chars) != 4:
        raise ValueError(f"a structural layer must have four cells, got {chars!r}")
    row = 0
    for q, char in enumerate(chars):
        try:
            kind = SIMPLIFIED_TO_KIND[char]
        except KeyError as exc:
            raise ValueError(f"unsupported structural cell {char!r}") from exc
        row = set_cell(row, q, kind)
    return row


def decode_row(row: LayerWord) -> str:
    return "".join(KIND_TO_SIMPLIFIED[get_cell(row, q)] for q in range(4))


def row_occupied_mask(row: LayerWord) -> int:
    mask = 0
    for q in range(4):
        if get_cell(row, q) != EMPTY:
            mask |= 1 << q
    return mask


def row_kind_mask(row: LayerWord, kind: int) -> int:
    mask = 0
    for q in range(4):
        if get_cell(row, q) == int(kind):
            mask |= 1 << q
    return mask


def trim_shape(rows: Sequence[LayerWord]) -> StructuralShape:
    end = len(rows)
    while end > 0 and row_occupied_mask(rows[end - 1]) == 0:
        end -= 1
    return tuple(int(row) for row in rows[:end])


def parse_structural(code: str) -> StructuralShape:
    if not code:
        return ()
    return trim_shape(tuple(encode_row(layer) for layer in code.split(":")))


def format_structural(shape: Sequence[LayerWord]) -> str:
    shape = trim_shape(shape)
    return ":".join(decode_row(row) for row in shape)


def structural_height(shape: Sequence[LayerWord]) -> int:
    return len(trim_shape(shape))


def structural_crystal_count(shape: Sequence[LayerWord]) -> int:
    return sum(row_kind_mask(row, CRYSTAL).bit_count() for row in trim_shape(shape))


def generator_forward_structural(predecessor: Sequence[LayerWord]) -> StructuralShape:
    """Apply the color-erased Crystal Generator exactly.

    Existing crystals remain crystals; empty cells and pins below the global
    height become crystals; normal parts remain normal.  The empty shape stays
    empty.
    """

    predecessor = trim_shape(predecessor)
    if not predecessor:
        return ()
    output: list[int] = []
    for row in predecessor:
        out = 0
        for q in range(4):
            kind = get_cell(row, q)
            out_kind = CRYSTAL if kind in (EMPTY, PIN) else kind
            out = set_cell(out, q, out_kind)
        output.append(out)
    return tuple(output)


@dataclass(frozen=True)
class ExactCell:
    """Exact cell payload needed only for color/provenance integration."""

    kind: CellKind
    shape: str = "-"
    color: str = "-"

    @staticmethod
    def empty() -> "ExactCell":
        return ExactCell(CellKind.EMPTY, "-", "-")

    @staticmethod
    def pin() -> "ExactCell":
        return ExactCell(CellKind.PIN, "P", "-")

    @staticmethod
    def crystal(color: str) -> "ExactCell":
        return ExactCell(CellKind.CRYSTAL, "c", color)


ExactShape = tuple[tuple[ExactCell, ExactCell, ExactCell, ExactCell], ...]


def parse_exact_code(code: str) -> ExactShape:
    """Parse the project's two-character-per-cell shape code."""

    if not code:
        return ()
    rows: list[tuple[ExactCell, ExactCell, ExactCell, ExactCell]] = []
    for layer_text in code.split(":"):
        if len(layer_text) != 8:
            raise ValueError(f"exact layer must contain eight characters, got {layer_text!r}")
        cells: list[ExactCell] = []
        for q in range(4):
            token = layer_text[q * 2 : q * 2 + 2]
            shape, color = token
            if shape == "-":
                if color != "-":
                    raise ValueError(f"empty token must be --, got {token!r}")
                cells.append(ExactCell.empty())
            elif shape == "P":
                if color != "-":
                    raise ValueError(f"pin token must be P-, got {token!r}")
                cells.append(ExactCell.pin())
            elif shape == "c":
                if color == "-":
                    raise ValueError("crystal must carry a color")
                cells.append(ExactCell.crystal(color))
            else:
                if color == "-":
                    raise ValueError("normal part must carry a color")
                cells.append(ExactCell(CellKind.NORMAL, shape, color))
        rows.append(tuple(cells))  # type: ignore[arg-type]
    return trim_exact(rows)


def format_exact_code(shape: Sequence[Sequence[ExactCell]]) -> str:
    rows = []
    for layer in trim_exact(shape):
        tokens = []
        for cell in layer:
            if cell.kind == CellKind.EMPTY:
                tokens.append("--")
            elif cell.kind == CellKind.PIN:
                tokens.append("P-")
            else:
                tokens.append(cell.shape + cell.color)
        rows.append("".join(tokens))
    return ":".join(rows)


def trim_exact(shape: Sequence[Sequence[ExactCell]]) -> ExactShape:
    rows = [tuple(row) for row in shape]
    if any(len(row) != 4 for row in rows):
        raise ValueError("every exact layer must have four cells")
    end = len(rows)
    while end > 0 and all(cell.kind == CellKind.EMPTY for cell in rows[end - 1]):
        end -= 1
    return tuple(rows[:end])  # type: ignore[return-value]


def exact_to_structural(shape: Sequence[Sequence[ExactCell]]) -> StructuralShape:
    rows: list[int] = []
    for layer in trim_exact(shape):
        row = 0
        for q, cell in enumerate(layer):
            row = set_cell(row, q, int(cell.kind))
        rows.append(row)
    return tuple(rows)


def generator_forward_exact(predecessor: Sequence[Sequence[ExactCell]], color: str) -> ExactShape:
    predecessor = trim_exact(predecessor)
    if not predecessor:
        return ()
    rows: list[tuple[ExactCell, ExactCell, ExactCell, ExactCell]] = []
    for layer in predecessor:
        out: list[ExactCell] = []
        for cell in layer:
            if cell.kind in (CellKind.EMPTY, CellKind.PIN):
                out.append(ExactCell.crystal(color))
            else:
                out.append(cell)
        rows.append(tuple(out))  # type: ignore[arg-type]
    return tuple(rows)


@dataclass(frozen=True)
class LayerChoice:
    """One predecessor row allowed by a GeneratorConstraint."""

    row: LayerWord
    changed_cells: int
    retained_eligible_crystals: int
    pins: int
    empties: int

    @property
    def productive(self) -> bool:
        return self.changed_cells != 0


@lru_cache(maxsize=512)
def _row_choices_cached(
    normal_mask: int,
    fixed_crystal_mask: int,
    eligible_crystal_mask: int,
    require_nonempty: bool,
) -> tuple[LayerChoice, ...]:
    if normal_mask & fixed_crystal_mask or normal_mask & eligible_crystal_mask or fixed_crystal_mask & eligible_crystal_mask:
        raise ValueError("row masks must be disjoint")
    if (normal_mask | fixed_crystal_mask | eligible_crystal_mask) != FULL_ROW_MASK:
        raise ValueError("target Generator row must be fully occupied")

    eligible_quads = [q for q in range(4) if eligible_crystal_mask & (1 << q)]
    choices: list[LayerChoice] = []
    # Base row: fixed normal and fixed crystal cells.
    base = 0
    for q in range(4):
        bit = 1 << q
        if normal_mask & bit:
            base = set_cell(base, q, NORMAL)
        elif fixed_crystal_mask & bit:
            base = set_cell(base, q, CRYSTAL)

    # Each eligible target crystal may have been EMPTY, PIN, or CRYSTAL.
    def visit(index: int, row: int, changed: int, retained: int, pins: int, empties: int) -> None:
        if index == len(eligible_quads):
            if require_nonempty and row_occupied_mask(row) == 0:
                return
            choices.append(LayerChoice(row, changed, retained, pins, empties))
            return
        q = eligible_quads[index]
        bit = 1 << q
        visit(index + 1, set_cell(row, q, EMPTY), changed | bit, retained, pins, empties + 1)
        visit(index + 1, set_cell(row, q, PIN), changed | bit, retained, pins + 1, empties)
        visit(index + 1, set_cell(row, q, CRYSTAL), changed, retained + 1, pins, empties)

    visit(0, base, 0, 0, 0, 0)
    # Deterministic normal form: maximize generation first, then prefer empty
    # over pin, then use the compact row code as the final tie-break.
    choices.sort(
        key=lambda c: (
            c.retained_eligible_crystals,
            c.pins,
            c.row,
        )
    )
    return tuple(choices)


@dataclass(frozen=True)
class GeneratorConstraint:
    """Exact structural inverse constraint for one selected generator color.

    ``eligible_crystal_masks[l]`` marks target crystals whose color equals the
    selected Generator color.  Such cells allow predecessor EMPTY/PIN/CRYSTAL.
    Target crystals of other colors are fixed crystals.
    """

    target_rows: StructuralShape
    normal_masks: tuple[int, ...]
    fixed_crystal_masks: tuple[int, ...]
    eligible_crystal_masks: tuple[int, ...]
    generator_color: Optional[str] = None
    productive_only: bool = True

    def __post_init__(self) -> None:
        h = len(self.target_rows)
        if not (
            len(self.normal_masks)
            == len(self.fixed_crystal_masks)
            == len(self.eligible_crystal_masks)
            == h
        ):
            raise ValueError("constraint arrays must have target height")
        for l, row in enumerate(self.target_rows):
            normal = self.normal_masks[l]
            fixed = self.fixed_crystal_masks[l]
            eligible = self.eligible_crystal_masks[l]
            if normal & fixed or normal & eligible or fixed & eligible:
                raise ValueError("constraint masks overlap")
            if (normal | fixed | eligible) != FULL_ROW_MASK:
                raise NotGeneratorImage("Generator output has an empty or pin cell")
            # Cross-check the structural target.
            if row_kind_mask(row, NORMAL) != normal:
                raise ValueError("normal mask disagrees with target row")
            if row_kind_mask(row, CRYSTAL) != (fixed | eligible):
                raise ValueError("crystal masks disagree with target row")
        if self.productive_only and not self.has_eligible_crystal:
            raise NotGeneratorImage("a productive Generator step must create at least one target crystal")

    @property
    def height(self) -> int:
        return len(self.target_rows)

    @property
    def has_eligible_crystal(self) -> bool:
        return any(self.eligible_crystal_masks)

    @property
    def eligible_cell_count(self) -> int:
        return sum(mask.bit_count() for mask in self.eligible_crystal_masks)

    @classmethod
    def structural(cls, target: Sequence[LayerWord], *, productive_only: bool = True) -> "GeneratorConstraint":
        """Build a color-erased constraint where every target crystal is eligible."""

        rows = trim_shape(target)
        if not rows:
            if productive_only:
                raise NotGeneratorImage("the empty output has no productive Generator predecessor")
            return cls((), (), (), (), None, productive_only=False)
        normals: list[int] = []
        fixed: list[int] = []
        eligible: list[int] = []
        for row in rows:
            if row_occupied_mask(row) != FULL_ROW_MASK or row_kind_mask(row, PIN):
                raise NotGeneratorImage("Generator output must be a full, pin-free slab")
            normals.append(row_kind_mask(row, NORMAL))
            fixed.append(0)
            eligible.append(row_kind_mask(row, CRYSTAL))
        return cls(rows, tuple(normals), tuple(fixed), tuple(eligible), None, productive_only)

    @classmethod
    def exact(
        cls,
        target: Sequence[Sequence[ExactCell]],
        generator_color: str,
        *,
        productive_only: bool = True,
    ) -> "GeneratorConstraint":
        exact = trim_exact(target)
        if not exact:
            if productive_only:
                raise NotGeneratorImage("the empty output has no productive Generator predecessor")
            return cls((), (), (), (), generator_color, productive_only=False)
        rows = exact_to_structural(exact)
        normals: list[int] = []
        fixed: list[int] = []
        eligible: list[int] = []
        for layer in exact:
            normal_mask = fixed_mask = eligible_mask = 0
            for q, cell in enumerate(layer):
                bit = 1 << q
                if cell.kind == CellKind.NORMAL:
                    normal_mask |= bit
                elif cell.kind == CellKind.CRYSTAL:
                    if cell.color == generator_color:
                        eligible_mask |= bit
                    else:
                        fixed_mask |= bit
                else:
                    raise NotGeneratorImage("Generator output must be a full, pin-free slab")
            normals.append(normal_mask)
            fixed.append(fixed_mask)
            eligible.append(eligible_mask)
        return cls(rows, tuple(normals), tuple(fixed), tuple(eligible), generator_color, productive_only)

    def row_choices(self, layer: int) -> tuple[LayerChoice, ...]:
        if not 0 <= layer < self.height:
            raise IndexError(layer)
        return _row_choices_cached(
            self.normal_masks[layer],
            self.fixed_crystal_masks[layer],
            self.eligible_crystal_masks[layer],
            layer == self.height - 1,
        )

    def accepts_predecessor(self, predecessor: Sequence[LayerWord]) -> bool:
        predecessor = trim_shape(predecessor)
        if len(predecessor) != self.height:
            return False
        changed = False
        for l, row in enumerate(predecessor):
            choice_by_row = {choice.row: choice for choice in self.row_choices(l)}
            choice = choice_by_row.get(row)
            if choice is None:
                return False
            changed = changed or choice.productive
        if self.productive_only and not changed:
            return False
        return generator_forward_structural(predecessor) == self.target_rows

    def unconstrained_count(self) -> int:
        """Count raw structural predecessors without enumerating them."""

        if self.height == 0:
            return 1 if not self.productive_only else 0
        total = 1
        for l in range(self.height):
            total *= len(self.row_choices(l))
        if self.productive_only:
            # The unique unchanged predecessor chooses CRYSTAL at every eligible
            # cell and is always height-preserving because the target is nonempty.
            total -= 1
        return total

    def iter_raw_predecessors(self, limit: Optional[int] = None) -> Iterator[StructuralShape]:
        """Testing/debug iterator. Production code should use family intersection."""

        if limit is not None and limit < 0:
            raise ValueError("limit must be nonnegative or None")
        if limit == 0:
            return
        rows: list[int] = []
        emitted = 0

        def visit(layer: int, changed: bool) -> Iterator[StructuralShape]:
            nonlocal emitted
            if limit is not None and emitted >= limit:
                return
            if layer == self.height:
                if self.productive_only and not changed:
                    return
                candidate = tuple(rows)
                emitted += 1
                yield candidate
                return
            for choice in self.row_choices(layer):
                rows.append(choice.row)
                yield from visit(layer + 1, changed or choice.productive)
                rows.pop()
                if limit is not None and emitted >= limit:
                    return

        yield from visit(0, False)


@runtime_checkable
class DeterministicLayerFamily(Protocol[StateT]):
    """Minimal contract required for exact family-constrained Generator inverse."""

    def initial_state(self) -> StateT:
        ...

    def transition(self, state: StateT, row: LayerWord) -> Optional[StateT]:
        ...

    def is_accepting(self, state: StateT) -> bool:
        ...


@dataclass(frozen=True, order=True)
class GeneratorObjective:
    """Default additive objective for a canonical predecessor.

    Lower is better.  It first minimizes target-color crystals which were
    already crystals before generation (maximizing the actual work done by the
    Generator), then pins, then empties.  Fixed cells do not affect the score.
    """

    retained_eligible_crystals: int = 0
    pins: int = 0
    empties: int = 0

    def plus(self, choice: LayerChoice) -> "GeneratorObjective":
        return GeneratorObjective(
            self.retained_eligible_crystals + choice.retained_eligible_crystals,
            self.pins + choice.pins,
            self.empties + choice.empties,
        )


@dataclass(frozen=True)
class ExactGeneratorSolution:
    generator_color: str
    constraint: "GeneratorConstraint"
    witness: "GeneratorWitness"
    predecessor: ExactShape

    def certify(self, target: Sequence[Sequence[ExactCell]]) -> None:
        if generator_forward_exact(self.predecessor, self.generator_color) != trim_exact(target):
            raise GeneratorCertificateError("exact multi-color Generator replay failed")
        self.witness.certify()


@dataclass(frozen=True)
class GeneratorWitness:
    predecessor: StructuralShape
    target: StructuralShape
    generator_color: Optional[str]
    changed_masks: tuple[int, ...]
    objective: GeneratorObjective

    @property
    def productive(self) -> bool:
        return any(self.changed_masks)

    @property
    def crystal_drop(self) -> int:
        return structural_crystal_count(self.target) - structural_crystal_count(self.predecessor)

    def certify(self) -> None:
        replay = generator_forward_structural(self.predecessor)
        if replay != self.target:
            raise GeneratorCertificateError(
                f"Generator replay mismatch: predecessor={format_structural(self.predecessor)}, "
                f"target={format_structural(self.target)}, got={format_structural(replay)}"
            )
        if self.productive and self.crystal_drop <= 0:
            raise GeneratorCertificateError("productive Generator inverse did not reduce crystal count")


@dataclass
class _DPRecord(Generic[StateT]):
    objective: GeneratorObjective
    parent_key: Optional[tuple[StateT, bool]]
    row: Optional[int]
    changed_mask: int = 0


def solve_with_family(
    constraint: GeneratorConstraint,
    family: DeterministicLayerFamily[StateT],
) -> GeneratorWitness:
    """Find the optimal predecessor in ``family`` without enumerating shapes.

    Complexity is O(H * |Q| * 81), because one layer has at most 3^4 = 81
    predecessor rows.  Memory is O(H * |Q|) when reconstructing a witness.
    """

    if constraint.height == 0:
        state = family.initial_state()
        if family.is_accepting(state) and not constraint.productive_only:
            witness = GeneratorWitness((), (), constraint.generator_color, (), GeneratorObjective())
            witness.certify()
            return witness
        raise NoGeneratorPredecessor("empty predecessor is not accepted by the family")

    initial = family.initial_state()
    current: dict[tuple[StateT, bool], _DPRecord[StateT]] = {
        (initial, False): _DPRecord(GeneratorObjective(), None, None)
    }
    history: list[dict[tuple[StateT, bool], _DPRecord[StateT]]] = [current]

    for layer in range(constraint.height):
        nxt: dict[tuple[StateT, bool], _DPRecord[StateT]] = {}
        # Python dict insertion order plus sorted row choices makes the first
        # equal-cost path deterministic for deterministic family transitions.
        for key, record in current.items():
            state, changed_before = key
            for choice in constraint.row_choices(layer):
                next_state = family.transition(state, choice.row)
                if next_state is None:
                    continue
                changed_after = changed_before or choice.productive
                next_key = (next_state, changed_after)
                objective = record.objective.plus(choice)
                old = nxt.get(next_key)
                if old is None or objective < old.objective:
                    nxt[next_key] = _DPRecord(
                        objective=objective,
                        parent_key=key,
                        row=choice.row,
                        changed_mask=choice.changed_cells,
                    )
        if not nxt:
            raise NoGeneratorPredecessor(f"family rejected all Generator rows at layer {layer}")
        current = nxt
        history.append(current)

    final_candidates = [
        (key, record)
        for key, record in current.items()
        if family.is_accepting(key[0]) and (key[1] or not constraint.productive_only)
    ]
    if not final_candidates:
        raise NoGeneratorPredecessor("no accepting productive Generator predecessor")
    final_key, final_record = min(final_candidates, key=lambda item: item[1].objective)

    rows = [0] * constraint.height
    changed_masks = [0] * constraint.height
    key = final_key
    for layer in range(constraint.height, 0, -1):
        record = history[layer][key]
        assert record.row is not None and record.parent_key is not None
        rows[layer - 1] = record.row
        changed_masks[layer - 1] = record.changed_mask
        key = record.parent_key

    witness = GeneratorWitness(
        predecessor=tuple(rows),
        target=constraint.target_rows,
        generator_color=constraint.generator_color,
        changed_masks=tuple(changed_masks),
        objective=final_record.objective,
    )
    witness.certify()
    return witness


def family_predecessor_exists(
    constraint: GeneratorConstraint,
    family: DeterministicLayerFamily[StateT],
) -> bool:
    try:
        solve_with_family(constraint, family)
        return True
    except NoGeneratorPredecessor:
        return False


def count_with_deterministic_family(
    constraint: GeneratorConstraint,
    family: DeterministicLayerFamily[StateT],
) -> int:
    """Count distinct predecessors accepted by a deterministic family DFA."""

    if constraint.height == 0:
        return int(not constraint.productive_only and family.is_accepting(family.initial_state()))
    current: dict[tuple[StateT, bool], int] = {(family.initial_state(), False): 1}
    for layer in range(constraint.height):
        nxt: dict[tuple[StateT, bool], int] = {}
        for (state, changed_before), count in current.items():
            for choice in constraint.row_choices(layer):
                next_state = family.transition(state, choice.row)
                if next_state is None:
                    continue
                key = (next_state, changed_before or choice.productive)
                nxt[key] = nxt.get(key, 0) + count
        current = nxt
        if not current:
            return 0
    return sum(
        count
        for (state, changed), count in current.items()
        if family.is_accepting(state) and (changed or not constraint.productive_only)
    )


class AcceptAllFamily:
    """Useful baseline family for tests and raw canonical normal forms."""

    def initial_state(self) -> int:
        return 0

    def transition(self, state: int, row: LayerWord) -> int:
        return 0

    def is_accepting(self, state: int) -> bool:
        return True


def canonical_raw_predecessor(constraint: GeneratorConstraint) -> GeneratorWitness:
    """Return the canonical raw predecessor, not a buildability proof."""

    return solve_with_family(constraint, AcceptAllFamily())


def stable_single_pin_predecessor(constraint: GeneratorConstraint) -> GeneratorWitness:
    """Return a universally stable productive predecessor.

    It copies the full target and replaces the bottommost/lowest-quadrant
    eligible target-color crystal by one pin.  The predecessor remains a full
    slab, hence every cell is vertically supported.  This is a stability
    witness only; it is not necessarily a member of the buildable family.
    """

    if not constraint.has_eligible_crystal:
        raise NoGeneratorPredecessor("no target-color crystal can be generated")
    rows = list(constraint.target_rows)
    changed_masks = [0] * constraint.height
    chosen = None
    for l, mask in enumerate(constraint.eligible_crystal_masks):
        if mask:
            q = (mask & -mask).bit_length() - 1
            rows[l] = set_cell(rows[l], q, PIN)
            changed_masks[l] = 1 << q
            chosen = (l, q)
            break
    assert chosen is not None
    retained = constraint.eligible_cell_count - 1
    witness = GeneratorWitness(
        predecessor=tuple(rows),
        target=constraint.target_rows,
        generator_color=constraint.generator_color,
        changed_masks=tuple(changed_masks),
        objective=GeneratorObjective(retained, 1, 0),
    )
    witness.certify()
    return witness


def solve_exact_with_family(
    target: Sequence[Sequence[ExactCell]],
    family: DeterministicLayerFamily[StateT],
    *,
    colors: Optional[Iterable[str]] = None,
) -> ExactGeneratorSolution:
    """Choose the best productive Generator color and family predecessor.

    The family is structural/color-erased.  Exact normal and pre-existing
    crystal payloads are restored after the structural witness is selected.
    """

    exact = trim_exact(target)
    candidate_colors = tuple(sorted(set(colors))) if colors is not None else possible_productive_colors(exact)
    best: Optional[ExactGeneratorSolution] = None
    best_key = None
    for color in candidate_colors:
        try:
            constraint = GeneratorConstraint.exact(exact, color, productive_only=True)
            witness = solve_with_family(constraint, family)
        except (NotGeneratorImage, NoGeneratorPredecessor):
            continue
        predecessor = materialize_exact_predecessor(exact, constraint, witness)
        solution = ExactGeneratorSolution(color, constraint, witness, predecessor)
        solution.certify(exact)
        key = (
            structural_crystal_count(witness.predecessor),
            witness.objective.pins,
            witness.objective.empties,
            color,
        )
        if best is None or key < best_key:
            best = solution
            best_key = key
    if best is None:
        raise NoGeneratorPredecessor("no productive Generator color has a family predecessor")
    return best


def possible_productive_colors(target: Sequence[Sequence[ExactCell]]) -> tuple[str, ...]:
    """Generator colors that can have changed at least one target cell."""

    colors = {
        cell.color
        for layer in trim_exact(target)
        for cell in layer
        if cell.kind == CellKind.CRYSTAL
    }
    return tuple(sorted(colors))


def materialize_exact_predecessor(
    target: Sequence[Sequence[ExactCell]],
    constraint: GeneratorConstraint,
    witness: GeneratorWitness,
) -> ExactShape:
    """Restore exact normal/crystal payloads around a structural witness."""

    exact = trim_exact(target)
    if len(exact) != len(witness.predecessor):
        raise ValueError("target and witness heights differ")
    output: list[tuple[ExactCell, ExactCell, ExactCell, ExactCell]] = []
    for l, layer in enumerate(exact):
        row: list[ExactCell] = []
        for q, target_cell in enumerate(layer):
            kind = CellKind(get_cell(witness.predecessor[l], q))
            if kind == CellKind.EMPTY:
                row.append(ExactCell.empty())
            elif kind == CellKind.PIN:
                row.append(ExactCell.pin())
            else:
                # NORMAL and retained CRYSTAL are fixed exact target payloads.
                row.append(target_cell)
        output.append(tuple(row))  # type: ignore[arg-type]
    predecessor = tuple(output)
    if constraint.generator_color is None:
        raise ValueError("exact materialization requires a generator color")
    if generator_forward_exact(predecessor, constraint.generator_color) != exact:
        raise GeneratorCertificateError("exact Generator replay failed")
    return predecessor


# ---------------------------------------------------------------------------
# Duck-typed adapter for the user's existing Shape / Layer / Quadrant classes.
# ---------------------------------------------------------------------------


def exact_from_project_shape(shape) -> ExactShape:
    """Convert a project Shape instance without importing GUI dependencies."""

    rows: list[tuple[ExactCell, ExactCell, ExactCell, ExactCell]] = []
    for layer in getattr(shape, "layers", []):
        cells: list[ExactCell] = []
        for piece in layer.quadrants:
            if piece is None:
                cells.append(ExactCell.empty())
            elif piece.shape == "P":
                cells.append(ExactCell.pin())
            elif piece.shape == "c":
                cells.append(ExactCell.crystal(piece.color))
            else:
                cells.append(ExactCell(CellKind.NORMAL, piece.shape, piece.color))
        rows.append(tuple(cells))  # type: ignore[arg-type]
    return trim_exact(rows)


def constraint_from_project_shape(shape, generator_color: str, *, productive_only: bool = True) -> GeneratorConstraint:
    return GeneratorConstraint.exact(
        exact_from_project_shape(shape),
        generator_color,
        productive_only=productive_only,
    )


def materialize_project_predecessor(target_shape, constraint: GeneratorConstraint, witness: GeneratorWitness):
    """Create a project Shape predecessor while preserving exact target payloads."""

    try:
        from shape import Layer, Quadrant, Shape
    except ImportError as exc:  # pragma: no cover - project integration only
        raise ImportError("project shape.py is not importable") from exc

    exact_target = exact_from_project_shape(target_shape)
    exact_predecessor = materialize_exact_predecessor(exact_target, constraint, witness)
    layers = []
    for row in exact_predecessor:
        quadrants = []
        for cell in row:
            if cell.kind == CellKind.EMPTY:
                quadrants.append(None)
            elif cell.kind == CellKind.PIN:
                quadrants.append(Quadrant("P", "u"))
            else:
                quadrants.append(Quadrant(cell.shape, cell.color))
        layers.append(Layer(quadrants))
    result = Shape(layers)
    result.max_layers = target_shape.max_layers
    return result


def generator_forward_project(shape, generator_color: str):
    """Reference-correct forward adapter for the current mutable Shape class.

    This deliberately does *not* call ``Shape.crystal_generator`` because the
    current repository implementation fills an invented layer for the empty
    shape and uses ``len(layers)`` instead of the global occupied height.
    """

    try:
        from shape import Layer, Quadrant, Shape
    except ImportError as exc:  # pragma: no cover - project integration only
        raise ImportError("project shape.py is not importable") from exc

    # Compute global occupied height, ignoring trailing empty internal layers.
    height = 0
    for l, layer in enumerate(getattr(shape, "layers", [])):
        if any(piece is not None for piece in layer.quadrants):
            height = l + 1
    if height == 0:
        result = Shape([])
        result.max_layers = shape.max_layers
        return result

    layers = []
    for l in range(height):
        source_layer = shape.layers[l] if l < len(shape.layers) else Layer([None] * 4)
        quadrants = []
        for piece in source_layer.quadrants:
            if piece is None or piece.shape == "P":
                quadrants.append(Quadrant("c", generator_color))
            else:
                quadrants.append(piece.copy())
        layers.append(Layer(quadrants))
    result = Shape(layers)
    result.max_layers = shape.max_layers
    return result


__all__ = [
    "AcceptAllFamily",
    "CRYSTAL",
    "CellKind",
    "DeterministicLayerFamily",
    "EMPTY",
    "ExactCell",
    "ExactGeneratorSolution",
    "ExactShape",
    "GeneratorCertificateError",
    "GeneratorConstraint",
    "GeneratorError",
    "GeneratorObjective",
    "GeneratorWitness",
    "LayerChoice",
    "LayerWord",
    "NORMAL",
    "NoGeneratorPredecessor",
    "NotGeneratorImage",
    "PIN",
    "StructuralShape",
    "canonical_raw_predecessor",
    "constraint_from_project_shape",
    "count_with_deterministic_family",
    "decode_row",
    "encode_row",
    "exact_from_project_shape",
    "exact_to_structural",
    "family_predecessor_exists",
    "format_exact_code",
    "format_structural",
    "generator_forward_exact",
    "generator_forward_project",
    "generator_forward_structural",
    "get_cell",
    "materialize_exact_predecessor",
    "materialize_project_predecessor",
    "parse_exact_code",
    "parse_structural",
    "possible_productive_colors",
    "row_kind_mask",
    "row_occupied_mask",
    "set_cell",
    "solve_exact_with_family",
    "stable_single_pin_predecessor",
    "solve_with_family",
    "structural_crystal_count",
    "trim_exact",
    "trim_shape",
]
