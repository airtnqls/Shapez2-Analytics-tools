"""Public API of the completed corner-half branch."""
from .corner_dfa import (
    ALPHABET,
    FORBIDDEN_RULES,
    RejectionCertificate,
    build_minimized_dfa,
    first_rejection,
    is_craftable_column,
)
from .corner_regions import CornerWitness, analyze_column
from .corner_plan import AbstractCornerPlan, compile_abstract
from .component_plans import RegionMove, MoveKind
from .corner_constructor import (
    ConstructorKind,
    CornerConstructionCertificate,
    CornerConstructionError,
    construct_corner,
)
from .corner_ir import (
    CornerIRStep, CornerIRError, CornerRule, CornerRuleProgram, compile_corner_ir,
)
from .corner_full_replay import (
    CornerFullReplay, FullOperationStep, FullReplayError, replay_corner_full,
)
from .corner_macro_replay import (
    CornerMacroReplay,
    MacroReplayError,
    replay_corner_certificate,
)
from .c7_gadget import (
    C7Certificate,
    C7CompilationError,
    C7Duty,
    DutyKind,
    compile_c7,
)
from .half_automaton import (
    HALF_DFA,
    HalfDFA,
    MinimalityAudit,
    StabilityMinimalityAudit,
    ROW_ALPHABET,
    STABILITY_STATE_NAMES,
    audit_frozen_table,
    audit_minimality,
    audit_stability_minimality,
    build_minimized_half_dfa,
    rebuild_minimized_half_dfa,
    stability_accepts_rows,
)
from .half_inverse import (
    CutHalfInverse,
    HalfInverseError,
    SwapFullInverse,
    canonical_cut_inverse,
    first_swap_inverse,
    is_swappable_full,
    swap_inverse_candidates,
)
from .half_family import (
    ExactHalfFamily,
    HALF_FAMILY,
    HalfAnalysis,
    analyze_half,
    is_buildable_half,
)
from .half_constructor import (
    HalfConstructionCertificate,
    HalfConstructionError,
    construct_half,
)
from .half_full_replay import (
    HalfFullReplay, HalfFullReplayError, replay_half_full,
)
from .interfaces import HalfCertificate, HalfOp, HalfResult
from .proof_dag import (
    ProofAudit,
    ProofForestAudit,
    ProofDagError,
    ProofNode,
    clear_proof_caches,
    corner_raw_proof,
    half_raw_proof,
    verify_proof,
    verify_proof_forest,
)
from .primitive_prefabs import (
    OnePinPrefabCertificate,
    StructuralPrefabCertificate,
    build_crystal_trigger,
    build_layer_stack,
    build_one_pin,
    build_single_crystal_helper,
    build_single_layer_pattern,
)

__all__ = [
    "ALPHABET", "FORBIDDEN_RULES", "RejectionCertificate",
    "build_minimized_dfa", "first_rejection", "is_craftable_column",
    "CornerWitness", "analyze_column", "AbstractCornerPlan", "compile_abstract",
    "RegionMove", "MoveKind", "ConstructorKind", "CornerConstructionCertificate",
    "CornerConstructionError", "construct_corner", "CornerMacroReplay",
    "MacroReplayError", "replay_corner_certificate", "CornerRule",
    "CornerIRStep", "CornerRuleProgram", "CornerIRError", "compile_corner_ir",
    "CornerFullReplay", "FullOperationStep", "FullReplayError",
    "replay_corner_full", "C7Certificate",
    "C7CompilationError", "C7Duty", "DutyKind", "compile_c7",
    "ExactHalfFamily", "HALF_FAMILY", "HalfAnalysis", "analyze_half",
    "is_buildable_half", "HalfConstructionCertificate", "HalfConstructionError",
    "construct_half", "HalfFullReplay", "HalfFullReplayError",
    "replay_half_full", "HalfCertificate", "HalfOp", "HalfResult",
    "ProofNode", "ProofAudit", "ProofForestAudit", "ProofDagError",
    "clear_proof_caches", "corner_raw_proof", "half_raw_proof",
    "verify_proof", "verify_proof_forest",
    "OnePinPrefabCertificate", "StructuralPrefabCertificate", "build_one_pin",
    "build_single_layer_pattern", "build_layer_stack",
    "build_single_crystal_helper", "build_crystal_trigger",
    "HALF_DFA", "HalfDFA", "MinimalityAudit",
    "StabilityMinimalityAudit", "ROW_ALPHABET",
    "STABILITY_STATE_NAMES", "audit_frozen_table", "audit_minimality",
    "audit_stability_minimality",
    "build_minimized_half_dfa", "rebuild_minimized_half_dfa",
    "stability_accepts_rows",
    "CutHalfInverse", "HalfInverseError", "SwapFullInverse",
    "canonical_cut_inverse", "first_swap_inverse",
    "is_swappable_full", "swap_inverse_candidates",
]
