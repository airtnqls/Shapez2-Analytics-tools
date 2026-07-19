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
  primitive: boolean;
  depth: number;
  dependencyStepIds: string[];
  inputs: ProcessRecipePort[];
  outputs: ProcessRecipePort[];
  selectedOutputNodeIds: string[];
  metadata?: Record<string, string | number | boolean | string[]>;
}

export interface ProcessRecipe {
  version: 1;
  finalShapeNodeId: string;
  finalCode?: string;
  steps: ProcessRecipeStep[];
  sharedShapeNodeIds: string[];
  primitiveComplete: boolean;
  replayStatus: ProofGraph["replayStatus"];
  warnings: string[];
}

export interface ProgressMessage {
  type: "progress";
  jobId: string;
  phase: string;
  current: number;
  total: number;
  message: string;
  statesVisited?: number;
  queued?: number;
  elapsedMs?: number;
}

export interface ResultMessage {
  type: "result";
  jobId: string;
  result: AnalysisResult;
}

export interface ErrorMessage {
  type: "error";
  jobId: string;
  error: string;
}

export interface CancelledMessage {
  type: "cancelled";
  jobId: string;
}

export interface OperationResultMessage {
  type: "operation-result";
  jobId: string;
  result: OperationResult;
}

export type WorkerOutbound = ProgressMessage | ResultMessage | OperationResultMessage | ErrorMessage | CancelledMessage;

export type WorkerInbound =
  | { type: "analyze"; jobId: string; mode: AnalyzeMode; code: string; cap: number }
  | { type: "operate"; jobId: string; operation: OperationName; inputA: string; inputB?: string; inputBPresent?: boolean; cap: number; paintColor?: string; crystalColor?: string }
  | { type: "cancel"; jobId: string }
  | { type: "warmup"; jobId: string; tables?: ("targets" | "samples")[] };

export interface BatchRow {
  index: number;
  raw: string;
  code: string;
  cap: number;
  status: "pending" | "running" | "done" | "error" | "cancelled";
  result?: AnalysisResult;
  error?: string;
}

export interface HistoryRecord {
  id?: number;
  createdAt: number;
  code: string;
  normalizedCode: string;
  cap: number;
  verdict: Verdict;
  shapeType: ShapeType;
  route: string;
  elapsedMs: number;
  favorite: boolean;
  note?: string;
  result: AnalysisResult;
}
