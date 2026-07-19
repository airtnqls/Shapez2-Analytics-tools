export interface HalfProofForestNode {
  op: "RAW_INPUT" | "ROTATE" | "CUT" | "SWAP" | "STACK" | "GENERATE" | "PIN_PUSH";
  cap: number;
  result: string;
  children: number[];
  parameter: string | number | null;
  note: string;
}

export interface HalfProofForest {
  version: number;
  cap: number;
  roots: Record<string, number>;
  nodes: HalfProofForestNode[];
  audit: {
    uniqueNodes: number;
    operationNodes: number;
    rawLeaves: number;
    edges: number;
    maxDepth: number;
    replayOk: boolean;
  };
}
