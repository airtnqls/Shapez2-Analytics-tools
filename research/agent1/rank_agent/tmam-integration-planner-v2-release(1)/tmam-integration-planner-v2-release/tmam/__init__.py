from .automata import DFA, MinimizedDFA, distinguishing_word, minimize_dfa, product_dfa
from .bootstrap import BootstrapResult, build_runtime, load_plugins
from .classification import ClassificationPolicy, ClassificationResult, ReasonCode, map_to_legacy_enum
from .contracts import (
    Certificate,
    Coverage,
    DEFAULT_FAMILY_CONTEXT,
    FamilyContext,
    FamilyDecision,
    Goal,
    InverseBatch,
    InverseCandidate,
    PluginManifest,
    Progress,
    ProviderIncompleteError,
    ProviderResourceLimit,
    Subgoal,
)
from .cost import CostVector, CriticalPathCostModel, LexicographicCostModel
from .enums import (
    ClassificationMode,
    Decision,
    LegacyShapeTypeKey,
    Operation,
    Phase,
    ProofStatus,
    SearchMode,
)
from .facts import ShapeFacts, facts_from_analysis
from .family_algebra import AutomatonFamily, FamilyStage, RankedFamilySequence
from .fixed_point import FixedPointResult, least_fixed_point
from .legacy_adapter import LegacyClassifierAdapter
from .planner import (
    AnalysisResult,
    GoalAnalysis,
    OperationEvidence,
    PlannerConfig,
    PlannerContractError,
    ProviderEvaluation,
    SolveResult,
    TMAMPlanner,
)
from .proof import ProofNode, ProofValidator, ValidationReport, proof_to_legacy_tree
from .process_tree_adapter import (
    LegacyProcessTreeBundle,
    PrecomputedProcessNode,
    proof_to_precomputed_process_tree,
)
from .proof_metrics import ProofMetrics, collect_proof_metrics
from .registry import IntegrationRegistry, RegistryError
from .cache import CacheStats, CandidateCacheKey, GenerationalCache, GoalCacheKey, ProviderCacheKey
from .gui_bridge import (
    DetailedAnalysisViewModel,
    MinimumProofViewModel,
    PossibilityViewModel,
    TMAMApplicationService,
)
from .instrumentation import PlannerMetricsSnapshot, TraceEvent
from .provider_adapter import CallableInverseRelationAdapter, legacy_corner_rule_accepts
from .state_tools import AutomatonMetrics, StateInterner, automaton_metrics, generic_reachable_states
from .runtime import RuntimeAnalysis, TMAMRuntime
from .shadow import ShadowDiff, compare_legacy_result
from .testkit import ContractIssue, RelationAuditReport, audit_relation
from .version import INTEGRATION_API_VERSION

__all__ = [name for name in globals() if not name.startswith("_")]
