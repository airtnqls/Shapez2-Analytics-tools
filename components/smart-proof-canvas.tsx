"use client";

import { useEffect, useMemo, useState } from "react";
import { GitBranch, ListTree, ShieldCheck } from "lucide-react";
import type { ProofGraph, ProofNodeData } from "@/lib/types";
import { cn } from "@/lib/cn";
import { ProofCanvas } from "./proof-canvas";

interface SmartProofCanvasProps {
  graph: ProofGraph | null;
  onNodeSelect?: (node: ProofNodeData | null) => void;
}

export function SmartProofCanvas({ graph, onNodeSelect }: SmartProofCanvasProps) {
  const hasOverview = Boolean(graph?.overview);
  const [view, setView] = useState<"overview" | "primitive">(hasOverview ? "overview" : "primitive");

  useEffect(() => {
    setView(graph?.overview ? "overview" : "primitive");
    onNodeSelect?.(null);
  }, [graph, onNodeSelect]);

  const activeGraph = useMemo(() => {
    if (!graph) return null;
    if (view === "overview" && graph.overview) return graph.overview;
    return graph;
  }, [graph, view]);

  if (!graph) return <ProofCanvas graph={null} onNodeSelect={onNodeSelect} />;

  return <div className="flex h-full min-h-0 flex-col bg-[var(--surface-0)]">
    {hasOverview ? <div className="no-print flex h-9 shrink-0 items-center gap-1 border-b border-[var(--border)] bg-[var(--surface-1)] px-2">
      <button
        type="button"
        onClick={() => setView("overview")}
        className={cn(
          "flex h-7 items-center gap-1.5 border px-2.5 text-[10px] font-semibold",
          view === "overview"
            ? "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_9%,var(--surface-1))] text-[var(--text)]"
            : "border-transparent text-[var(--muted)] hover:border-[var(--border)] hover:text-[var(--text)]",
        )}
      >
        <ListTree size={13} />핵심 순차 공정
        <span className="font-mono text-[9px] text-[var(--muted)]">{graph.overview?.operationCount ?? 0}</span>
      </button>
      <button
        type="button"
        onClick={() => setView("primitive")}
        className={cn(
          "flex h-7 items-center gap-1.5 border px-2.5 text-[10px] font-semibold",
          view === "primitive"
            ? "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_9%,var(--surface-1))] text-[var(--text)]"
            : "border-transparent text-[var(--muted)] hover:border-[var(--border)] hover:text-[var(--text)]",
        )}
      >
        <GitBranch size={13} />원시 전체 공정
        <span className="font-mono text-[9px] text-[var(--muted)]">{graph.uniqueOperationCount}</span>
      </button>
      <span className="ml-auto flex items-center gap-1.5 text-[9px] text-[var(--muted)]">
        <ShieldCheck size={12} className="text-emerald-600" />
        핵심 공정도는 재생 검증된 원시 DAG의 축약 보기입니다.
      </span>
    </div> : null}
    <div className="min-h-0 flex-1">
      <ProofCanvas graph={activeGraph} onNodeSelect={onNodeSelect} />
    </div>
  </div>;
}
