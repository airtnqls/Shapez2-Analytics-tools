export type Cell = "-" | "S" | "P" | "c";
export type ShapeRows = Cell[][];
export type Verdict = "POSSIBLE" | "IMPOSSIBLE" | "UNKNOWN";
export type AnalyzeMode = "fast" | "type" | "proof";
export type OperationName =
  | "destroy_half" | "stack" | "push_pin" | "apply_physics" | "swap"
  | "half_cutter" | "rotate_cw" | "rotate_ccw" | "rotate_180"
  | "simple_cutter" | "quad_cutter" | "paint" | "crystal_generator"
  | "mirror" | "simplify" | "detail" | "corner_1q" | "reverse" | "cornerize";

export interface OperationResult {
  operation: OperationName;
  outputs: string[];
  message: string;
}

export type ShapeType =
  | "EMPTY"
  | "BASIC"
  | "HALF"
  | "SWAPPABLE"
  | "STACKABLE"
  | "CLAW"
  | "CLAW_HYBRID"
  | "PIN_PUSH"
  | "IMPOSSIBLE"
  | "UNKNOWN";

export interface ColumnFact {
  quadrant: number;
  pillar: string;
  accepted: boolean;
  violatedRule?: string;
}

export interface StackWitness {
  bottom: string;
  topPieces: string[];
  splitHeights: number[];
}

export interface ClawWitness {
  predecessor: string;
  backend: string;
  targetCode?: string;
  restoreTurns?: number;
}

export interface PinPushWitness extends ClawWitness {
  kind: "primitive-rank0" | "receipt-chain";
  /** Pin Push outputs in construction order, including the final target. */
  receiptTargets: string[];
  predecessorStack?: StackWitness;
}

export interface HybridWitness {
  bottom: string;
  top: string;
  cuts: number[];
  backend: string;
  bottomClaw?: ClawWitness;
}

export interface AnalysisFacts {
  stable: boolean;
  basic: boolean;
  half: boolean;
  swappable: boolean;
  stackable: boolean;
  claw: boolean;
  hybrid: boolean;
  generatorImage: boolean;
  height: number;
  occupiedCells: number;
  activeColumns: number;
  ppDepth?: number;
  stackDepth?: number;
  receiptProfile: [number, number, number, number];
  receiptRank: number;
  ppChainUpperBound: number;
  ppBatchUpperBound: number;
  ppTerminationProof: "bottom-pin-receipt-rank";
  coverage: "complete" | "partial";
}

export interface TimingInfo {
  totalMs: number;
  normalizeMs: number;
  familyMs: number;
  proofMs: number;
  tableLoadMs: number;
}

export interface AnalysisResult {
  jobId: string;
  mode: AnalyzeMode;
  originalCode: string;
  normalizedCode: string;
  cap: number;
  verdict: Verdict;
  shapeType: ShapeType;
  route: string;
  reason: string;
  explanation: string[];
  facts: AnalysisFacts;
  columns: ColumnFact[];
  timing: TimingInfo;
  witness?: StackWitness | ClawWitness | PinPushWitness | HybridWitness | Record<string, unknown>;
  proof?: ProofGraph;
  processRecipe?: ProcessRecipe;
  negativeCertificate?: NegativeCertificate;
  diagnostics: Diagnostics;
}

export interface Diagnostics {
  backend: string;
  backendVersion: string;
  cacheHit: boolean;
  statesVisited: number;
  candidatesChecked: number;
  tablesLoaded: string[];
  warnings: string[];
}

export interface NegativeCertificateItem {
  id: string;
  family: string;
  status: "rejected" | "exhausted" | "not-applicable" | "open";
  reason: string;
  details?: Record<string, string | number | boolean>;
}

export interface NegativeCertificate {
  complete: boolean;
  verifier: "passed" | "not-run" | "partial";
  items: NegativeCertificateItem[];
}

export interface ProofNodeData {
  id: string;
  kind: "shape" | "operation" | "certificate";
  label: string;
  code?: string;
  operation?: string;
  status?: "positive" | "negative" | "unknown" | "ghost";
  metadata?: Record<string, string | number | boolean | string[]>;
}

export interface ProofEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  dashed?: boolean;
}

export interface ProofGraph {
  nodes: ProofNodeData[];
  edges: ProofEdgeData[];
  rootId: string;
  operationCount: number;
  uniqueOperationCount: number;
  expandedOperationCount: number;
  sharedNodeCount: number;
  primitiveComplete: boolean;
  omittedReasons: string[];
  replayStatus: "passed" | "partial" | "failed" | "not-applicable";
  /** Optional small, sequential semantic view backed by this verified primitive graph. */
  overview?: ProofGraph;
  viewKind?: "semantic-overview" | "primitive-detail" | string;
  detailOperationCount?: number;
}

/** A deterministic CPCP-style backpointer view of the proof DAG. */
export interface ProcessRecipePort {
  nodeId: string;
  code?: string;
  label: string;
  role: string;
  selected: boolean;
  ghost: boolean;
}

export interface ProcessRecipeStep {
  id: string;
  index: number;
  operationNodeId: string;
  operation: string;
  label: string;
  inputs: ProcessRecipePort[];
  outputs: ProcessRecipePort[];
  selectedOutputIds: string[];
  unusedOutputIds: string[];
}

export interface ProcessRecipe {
  rootId: string;
  steps: ProcessRecipeStep[];
}
