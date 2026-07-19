import { describe, expect, it } from "vitest";
import { buildProcessRecipe } from "../lib/process-recipe";
import type { ProofGraph } from "../lib/types";

describe("CPCP-style process recipe", () => {
  it("orders operations by dependencies and marks unused outputs", () => {
    const graph: ProofGraph = {
      nodes: [
        { id: "shape-final", kind: "shape", label: "SSSS", code: "SSSS", status: "positive" },
        { id: "op-cut", kind: "operation", label: "자르기", operation: "CUT", status: "positive" },
        { id: "shape-raw", kind: "shape", label: "SSSS", code: "SSSS", status: "positive" },
        { id: "op-raw", kind: "operation", label: "기본 입력", operation: "RAW_INPUT", status: "positive" },
        { id: "shape-ghost", kind: "shape", label: "----", code: "----", status: "ghost" },
      ],
      edges: [
        { id: "e1", source: "op-raw", target: "shape-raw", label: "출력" },
        { id: "e2", source: "shape-raw", target: "op-cut", label: "입력" },
        { id: "e3", source: "op-cut", target: "shape-final", label: "사용 출력" },
        { id: "e4", source: "op-cut", target: "shape-ghost", label: "다른 출력", dashed: true },
      ],
      rootId: "shape-final",
      operationCount: 1,
      uniqueOperationCount: 1,
      expandedOperationCount: 1,
      sharedNodeCount: 0,
      primitiveComplete: true,
      omittedReasons: [],
      replayStatus: "passed",
    };

    const recipe = buildProcessRecipe(graph);
    expect(recipe.steps.map((step) => step.operation)).toEqual(["RAW_INPUT", "CUT"]);
    expect(recipe.steps[1].dependencyStepIds).toEqual(["step-1"]);
    expect(recipe.steps[1].selectedOutputNodeIds).toEqual(["shape-final"]);
    expect(recipe.steps[1].outputs.find((output) => output.nodeId === "shape-ghost")?.selected).toBe(false);
  });
});
