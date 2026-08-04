"use client";

import Image from "next/image";
import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { toPng, toSvg } from "html-to-image";
import {
  Box,
  ChevronLeft,
  ChevronRight,
  Download,
  FileCheck2,
  FileCode2,
  GitBranch,
  ListTree,
  Maximize2,
  Pause,
  Play,
  Search,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import type { ProofGraph, ProofNodeData } from "@/lib/types";
import { buildProcessRecipe } from "@/lib/process-recipe";
import { displayLayers } from "@/lib/shape";
import { ShapeRenderer } from "./shape-renderer";
import { Badge, Button, IconButton, Segmented, SegmentButton } from "./ui";
import { cn } from "@/lib/cn";

export interface ProofCanvasHandle {
  exportPng: () => Promise<void>;
  exportSvg: () => Promise<void>;
  exportDot: () => void;
  fit: () => void;
}

type FlowData = ProofNodeData & Record<string, unknown> & { active?: boolean; direction?: "LR" | "TB" };

const operationAssets: Record<string, string> = {
  RAW_INPUT: "globe.png",
  ROTATE: "rotator-cw.png",
  CUT: "cutter.png",
  SWAP: "swapper.png",
  STACK: "stacker.png",
  GENERATE: "crystal-generator.png",
  PIN_PUSH: "pin-pusher.png",
};

const ShapeFlowNode = memo(function ShapeFlowNode({ data, selected }: NodeProps<Node<FlowData>>) {
  const horizontal = data.direction === "LR";
  const layerCount = displayLayers(data.code ?? "").length;
  const status = data.status === "positive" ? "검증" : data.status === "ghost" ? "미사용" : data.status === "negative" ? "거부" : data.status === "unknown" ? "미완료" : "";
  return <div data-layer-count={layerCount} className={cn(
    "proof-node proof-node-shape relative w-[150px] border bg-[var(--surface-1)]",
    selected || data.active ? "border-[var(--accent)] outline outline-2 outline-[color-mix(in_srgb,var(--accent)_24%,transparent)]" : "border-[var(--border-strong)]",
    data.status === "ghost" && "border-dashed opacity-50",
    data.status === "negative" && "border-rose-500/45",
    data.status === "unknown" && "border-amber-500/45",
  )}>
    <Handle type="target" position={horizontal ? Position.Left : Position.Top} className="!h-2 !w-2 !border !border-[var(--surface-0)] !bg-[var(--accent)]" />
    <div className="flex h-5 items-center justify-between border-b border-[var(--border)] px-2">
      <span className="truncate text-[9px] font-semibold uppercase tracking-[.08em] text-[var(--muted)]">도형</span>
      <span className="text-[9px] text-[var(--muted)]">{status}</span>
    </div>
    <div className="flex min-h-[78px] justify-center overflow-visible bg-[var(--surface-0)] px-1.5 py-1.5">
      <ShapeRenderer code={data.code ?? ""} compact maxLayers={Number.MAX_SAFE_INTEGER} />
    </div>
    <code title={data.code ?? ""} className="block truncate border-t border-[var(--border)] px-2 py-1 text-[9px] text-[var(--muted)]">{data.code || "<empty>"}</code>
    <Handle type="source" position={horizontal ? Position.Right : Position.Bottom} className="!h-2 !w-2 !border !border-[var(--surface-0)] !bg-[var(--accent)]" />
  </div>;
});

const OperationFlowNode = memo(function OperationFlowNode({ data, selected }: NodeProps<Node<FlowData>>) {
  const horizontal = data.direction === "LR";
  const asset = operationAssets[data.operation ?? ""];
  return <div className={cn(
    "proof-node relative flex w-[142px] items-center border bg-[var(--surface-2)]",
    selected || data.active ? "border-[var(--accent)] outline outline-2 outline-[color-mix(in_srgb,var(--accent)_24%,transparent)]" : "border-[var(--border-strong)]",
  )}>
    <Handle type="target" position={horizontal ? Position.Left : Position.Top} className="!h-2 !w-2 !border !border-[var(--surface-0)] !bg-[var(--accent)]" />
    <span className="grid h-10 w-10 shrink-0 place-items-center border-r border-[var(--border)] bg-white">
      {asset ? <Image src={`/legacy-icons/${asset}`} width={21} height={21} alt="" unoptimized /> : data.operation === "CERTIFIED_MACRO" ? <ShieldCheck size={17} /> : <Workflow size={17} />}
    </span>
    <div className="min-w-0 px-2 py-1.5">
      <div className="truncate text-[11px] font-semibold">{data.label}</div>
      <div className="mt-0.5 truncate text-[9px] text-[var(--muted)]">{data.metadata?.parameter ? `매개변수 ${String(data.metadata.parameter)}` : data.operation}</div>
    </div>
    <Handle type="source" position={horizontal ? Position.Right : Position.Bottom} className="!h-2 !w-2 !border !border-[var(--surface-0)] !bg-[var(--accent)]" />
  </div>;
});

const CertificateFlowNode = memo(function CertificateFlowNode({ data, selected }: NodeProps<Node<FlowData>>) {
  const horizontal = data.direction === "LR";
  const negative = data.status === "negative";
  const unknown = data.status === "unknown";
  return <div className={cn(
    "proof-node relative w-[200px] border bg-[var(--surface-1)]",
    selected && "outline outline-2 outline-[color-mix(in_srgb,var(--accent)_24%,transparent)]",
    negative ? "border-rose-500/40" : unknown ? "border-amber-500/40" : "border-emerald-500/40",
  )}>
    <Handle type="target" position={horizontal ? Position.Left : Position.Top} className="!h-2 !w-2 !border !border-[var(--surface-0)] !bg-current" />
    <div className="flex gap-2 px-2.5 py-2">
      {negative ? <FileCheck2 className="mt-0.5 shrink-0 text-rose-500" size={15} /> : <ShieldCheck className={cn("mt-0.5 shrink-0", unknown ? "text-amber-500" : "text-emerald-600")} size={15} />}
      <div className="min-w-0">
        <div className="text-[11px] font-semibold leading-4">{data.label}</div>
        {data.metadata ? <div className="mt-1 line-clamp-2 text-[9px] leading-4 text-[var(--muted)]">{Object.entries(data.metadata).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(",") : String(value)}`).join(" · ")}</div> : null}
      </div>
    </div>
    <Handle type="source" position={horizontal ? Position.Right : Position.Bottom} className="!h-2 !w-2 !border !border-[var(--surface-0)] !bg-current" />
  </div>;
});

const nodeTypes = { shape: ShapeFlowNode, operation: OperationFlowNode, certificate: CertificateFlowNode };

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function cloneToTree(graph: ProofGraph): ProofGraph {
  const nodeMap = new Map(graph.nodes.map((node) => [node.id, node]));
  const incoming = new Map<string, typeof graph.edges>();
  for (const edge of graph.edges) incoming.set(edge.target, [...(incoming.get(edge.target) ?? []), edge]);
  const nodes: ProofNodeData[] = [];
  const edges: ProofGraph["edges"] = [];
  let index = 0;
  const visit = (id: string, path: Set<string>): string => {
    index += 1;
    const cloneId = `${id}-tree-${index}`;
    const original = nodeMap.get(id);
    if (!original) return cloneId;
    nodes.push({ ...original, id: cloneId });
    if (path.has(id)) return cloneId;
    const nextPath = new Set(path).add(id);
    for (const edge of incoming.get(id) ?? []) {
      const child = visit(edge.source, nextPath);
      edges.push({ ...edge, id: `${edge.id}-tree-${index}-${child}`, source: child, target: cloneId });
    }
    return cloneId;
  };
  const rootId = visit(graph.rootId, new Set());
  return { ...graph, nodes, edges, rootId };
}

function localSubgraph(graph: ProofGraph, focusId: string, depth = 5): ProofGraph {
  const incoming = new Map<string, ProofGraph["edges"]>();
  const outgoing = new Map<string, ProofGraph["edges"]>();
  for (const edge of graph.edges) {
    incoming.set(edge.target, [...(incoming.get(edge.target) ?? []), edge]);
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge]);
  }
  const selected = new Set<string>([focusId]);
  let frontier = [focusId];
  for (let level = 0; level < depth && frontier.length; level += 1) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const edge of incoming.get(id) ?? []) {
        if (!selected.has(edge.source)) next.push(edge.source);
        selected.add(edge.source);
      }
    }
    frontier = next;
  }
  // Retain the immediate result/consumer so a selected operation never floats
  // without showing which shape it produces.
  for (const edge of outgoing.get(focusId) ?? []) selected.add(edge.target);
  return {
    ...graph,
    nodes: graph.nodes.filter((node) => selected.has(node.id)),
    edges: graph.edges.filter((edge) => selected.has(edge.source) && selected.has(edge.target)),
    rootId: selected.has(graph.rootId) ? graph.rootId : focusId,
  };
}

function hasSharedSubgraph(graph: ProofGraph): boolean {
  const outgoing = new Map<string, number>();
  for (const edge of graph.edges) outgoing.set(edge.source, (outgoing.get(edge.source) ?? 0) + 1);
  return [...outgoing.values()].some((count) => count > 1);
}

function layoutGraph(graph: ProofGraph, direction: "LR" | "TB", collapseInputs: boolean): { nodes: Node<FlowData>[]; edges: Edge[] } {
  const rawIds = new Set(graph.nodes.filter((node) => node.kind === "operation" && node.operation === "RAW_INPUT").map((node) => node.id));
  const view = collapseInputs ? {
    ...graph,
    nodes: graph.nodes.filter((node) => !rawIds.has(node.id)),
    edges: graph.edges.filter((edge) => !rawIds.has(edge.source) && !rawIds.has(edge.target)),
  } : graph;
  const dag = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  dag.setGraph({
    rankdir: direction,
    ranker: "network-simplex",
    acyclicer: "greedy",
    nodesep: direction === "TB" ? 58 : 44,
    ranksep: direction === "TB" ? 68 : 88,
    edgesep: 18,
    marginx: 36,
    marginy: 36,
  });
  for (const node of view.nodes) {
    const layers = node.kind === "shape" ? Math.max(1, displayLayers(node.code ?? "").length) : 0;
    const size = node.kind === "shape"
      ? { width: 150, height: 42 + Math.max(78, layers * 25 + 14) }
      : node.kind === "operation"
        ? { width: 142, height: 40 }
        : { width: 200, height: 68 };
    dag.setNode(node.id, size);
  }
  for (const edge of view.edges) dag.setEdge(edge.source, edge.target, { weight: edge.dashed ? 1 : 3 });
  dagre.layout(dag);
  const nodes: Node<FlowData>[] = view.nodes.map((node) => {
    const point = dag.node(node.id) ?? { x: 0, y: 0, width: 160, height: 80 };
    return {
      id: node.id,
      type: node.kind,
      data: { ...node, direction },
      position: { x: point.x - point.width / 2, y: point.y - point.height / 2 },
      width: point.width,
      height: point.height,
    };
  });
  const edges: Edge[] = view.edges.map((edge) => {
    const stroke = edge.dashed ? "#526273" : "#2b3f52";
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      animated: false,
      type: "smoothstep",
      pathOptions: { borderRadius: 12, offset: 20 },
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: stroke },
      interactionWidth: 16,
      style: { stroke, strokeDasharray: edge.dashed ? "6 5" : undefined, opacity: edge.dashed ? .88 : 1, strokeWidth: 1.65 },
      labelStyle: { fill: "var(--muted)", fontSize: 9, fontWeight: 600 },
      labelBgStyle: { fill: "var(--surface-0)", fillOpacity: .94 },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 2,
    };
  });
  return { nodes, edges };
}

function graphToDot(graph: ProofGraph): string {
  const esc = (value: string) => value.replaceAll("\\", "\\\\").replaceAll('"', '\\"').replaceAll("\n", "\\n");
  return [
    "digraph TMAM {",
    "  rankdir=LR;",
    "  node [shape=box, fontname=\"Segoe UI\"] ;",
    ...graph.nodes.map((node) => `  "${esc(node.id)}" [label="${esc(node.label)}"];`),
    ...graph.edges.map((edge) => `  "${esc(edge.source)}" -> "${esc(edge.target)}" [label="${esc(edge.label)}"${edge.dashed ? ", style=dashed" : ""}];`),
    "}",
  ].join("\n");
}

const ProofCanvasInner = forwardRef<ProofCanvasHandle, { graph: ProofGraph | null; onNodeSelect?: (node: ProofNodeData | null) => void }>(function ProofCanvasInner({ graph, onNodeSelect }, ref) {
  const flow = useReactFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [direction, setDirection] = useState<"LR" | "TB">("LR");
  const [viewMode, setViewMode] = useState<"dag" | "tree">("dag");
  const [scope, setScope] = useState<"local" | "full">("full");
  const [collapseInputs, setCollapseInputs] = useState(false);
  const [query, setQuery] = useState("");
  const [activeStep, setActiveStep] = useState(-1);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);

  const safeGraph = useMemo<ProofGraph | null>(() => {
    if (!graph) return null;
    return {
      ...graph,
      nodes: Array.isArray(graph.nodes) ? graph.nodes : [],
      edges: Array.isArray(graph.edges) ? graph.edges : [],
      omittedReasons: Array.isArray(graph.omittedReasons) ? graph.omittedReasons : [],
      uniqueOperationCount: Number.isFinite(graph.uniqueOperationCount) ? graph.uniqueOperationCount : 0,
      expandedOperationCount: Number.isFinite(graph.expandedOperationCount) ? graph.expandedOperationCount : 0,
      replayStatus: graph.replayStatus ?? "partial",
    };
  }, [graph]);
  const shared = useMemo(() => safeGraph ? hasSharedSubgraph(safeGraph) : false, [safeGraph]);
  const displayGraph = useMemo(() => safeGraph && viewMode === "tree" ? cloneToTree(safeGraph) : safeGraph, [safeGraph, viewMode]);
  const recipe = useMemo(() => displayGraph ? buildProcessRecipe(displayGraph) : null, [displayGraph]);
  const allOperations = useMemo(() => {
    if (!displayGraph || !recipe) return [];
    const nodeById = new Map(displayGraph.nodes.map((node) => [node.id, node]));
    return recipe.steps.flatMap((step) => {
      const node = nodeById.get(step.operationNodeId);
      return node ? [node] : [];
    });
  }, [displayGraph, recipe]);
  const semanticOperations = useMemo(() => allOperations.filter((node) => {
    const metadata = node.metadata ?? {};
    return !metadata.constructor && !metadata.theorem;
  }), [allOperations]);
  const constructorOperationCount = allOperations.length - semanticOperations.length;
  const operations = allOperations;
  const activeId = operations[activeStep]?.id ?? null;
  const anchorId = activeId ?? focusId ?? displayGraph?.rootId ?? "";
  const scopedGraph = useMemo(() => displayGraph && scope === "local" ? localSubgraph(displayGraph, anchorId || displayGraph.rootId) : displayGraph, [anchorId, displayGraph, scope]);
  const layout = useMemo(() => scopedGraph ? layoutGraph(scopedGraph, direction, collapseInputs) : { nodes: [], edges: [] }, [collapseInputs, direction, scopedGraph]);
  const renderedNodes = useMemo(() => layout.nodes.map((node) => ({ ...node, data: { ...node.data, active: node.id === activeId } })), [activeId, layout.nodes]);
  const renderedEdges = useMemo(() => layout.edges.map((edge) => {
    const active = activeId != null && (edge.source === activeId || edge.target === activeId);
    return active ? { ...edge, style: { ...edge.style, stroke: "var(--accent)", strokeWidth: 2.25, opacity: 1 } } : edge;
  }), [activeId, layout.edges]);
  const macroCount = safeGraph?.omittedReasons?.length ?? 0;

  useEffect(() => {
    setActiveStep(-1);
    setFocusId(null);
    setPlaying(false);
    onNodeSelect?.(null);
  }, [graph, viewMode, onNodeSelect]);

  useEffect(() => {
    const timer = window.setTimeout(() => flow.fitView({ padding: scope === "local" ? .16 : .06, duration: 180, maxZoom: scope === "local" ? 1.08 : .72 }), 80);
    return () => window.clearTimeout(timer);
  }, [flow, layout.nodes, scope]);

  const focusNode = useCallback((id: string) => {
    const node = layout.nodes.find((item) => item.id === id);
    if (!node) return;
    const width = node.width ?? (node.type === "shape" ? 150 : node.type === "certificate" ? 200 : 142);
    const height = node.height ?? (node.type === "operation" ? 40 : 100);
    flow.setCenter(node.position.x + width / 2, node.position.y + height / 2, { zoom: .92, duration: 220 });
  }, [flow, layout.nodes]);

  useEffect(() => {
    if (!activeId) return;
    const timer = window.setTimeout(() => focusNode(activeId), 20);
    return () => window.clearTimeout(timer);
  }, [activeId, focusNode]);

  useEffect(() => {
    if (!playing || !operations.length) return;
    const timer = window.setInterval(() => setActiveStep((step) => step >= operations.length - 1 ? 0 : step + 1), 900);
    return () => window.clearInterval(timer);
  }, [playing, operations.length]);

  const exportImage = async (kind: "png" | "svg") => {
    if (!wrapperRef.current) return;
    const options = { backgroundColor: getComputedStyle(document.documentElement).getPropertyValue("--surface-0").trim() || "#f0f0f0", pixelRatio: 2, cacheBust: true };
    const dataUrl = kind === "png" ? await toPng(wrapperRef.current, options) : await toSvg(wrapperRef.current, options);
    const response = await fetch(dataUrl);
    downloadBlob(await response.blob(), `shapez2-proof.${kind}`);
  };

  const exportDot = () => {
    if (safeGraph) downloadBlob(new Blob([graphToDot(safeGraph)], { type: "text/vnd.graphviz;charset=utf-8" }), "shapez2-proof.dot");
  };

  useImperativeHandle(ref, () => ({
    exportPng: () => exportImage("png"),
    exportSvg: () => exportImage("svg"),
    exportDot,
    fit: () => flow.fitView({ padding: .12, duration: 260, maxZoom: 1.05 }),
  }));

  const selectOperation = (index: number) => {
    setActiveStep(index);
    setFocusId(operations[index]?.id ?? null);
    const node = operations[index];
    if (node) onNodeSelect?.(node);
  };

  const focusSearch = () => {
    const needle = query.trim().toLowerCase();
    if (!needle || !displayGraph) return;
    const match = displayGraph.nodes.find((node) => `${node.label} ${node.code ?? ""} ${node.operation ?? ""}`.toLowerCase().includes(needle));
    if (!match) return;
    setFocusId(match.id);
    const operationIndex = operations.findIndex((node) => node.id === match.id);
    setActiveStep(operationIndex);
    onNodeSelect?.(match);
    window.setTimeout(() => focusNode(match.id), 20);
  };

  if (!safeGraph) return <div className="grid h-full min-h-0 place-items-center bg-[var(--surface-0)] text-center text-xs leading-5 text-[var(--muted)]">
    <div><Workflow className="mx-auto mb-3 opacity-50" size={30} /><p>공정 트리 탭을 열면<br />ZIP proof DAG가 표시됩니다.</p></div>
  </div>;

  return <div className="legacy-process-view flex h-full min-h-0 flex-col bg-[var(--surface-0)]" data-scope={scope} data-direction={direction}>
    <div className="no-print flex min-h-10 shrink-0 flex-wrap items-center gap-1.5 border-b border-[var(--border)] bg-[var(--surface-1)] px-2 py-1">
      <Segmented>
        <SegmentButton active={scope === "local"} onClick={() => setScope("local")}><ListTree size={12} />읽기 보기</SegmentButton>
        <SegmentButton active={scope === "full"} onClick={() => setScope("full")}><Workflow size={12} />전체 DAG</SegmentButton>
      </Segmented>
      <Segmented>
        <SegmentButton active={viewMode === "dag"} onClick={() => setViewMode("dag")}>공유 DAG · 고유 {safeGraph.uniqueOperationCount}</SegmentButton>
        <SegmentButton active={viewMode === "tree"} onClick={() => setViewMode("tree")}>제작 트리 · 사용 {safeGraph.expandedOperationCount}</SegmentButton>
      </Segmented>
      <Segmented>
        <SegmentButton active={direction === "TB"} onClick={() => setDirection("TB")}>세로</SegmentButton>
        <SegmentButton active={direction === "LR"} onClick={() => setDirection("LR")}>가로</SegmentButton>
      </Segmented>
      <Button size="xs" variant={collapseInputs ? "default" : "ghost"} onClick={() => setCollapseInputs((value) => !value)}>{collapseInputs ? "원재료 표시" : "원재료 숨김"}</Button>
      <div className="ml-auto flex min-w-[150px] max-w-[260px] flex-1 items-center border border-[var(--border-strong)] bg-[var(--surface-0)] px-2">
        <Search size={13} className="shrink-0 text-[var(--muted)]" />
        <input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") focusSearch(); }} placeholder="공정·도형 코드 검색" className="h-7 min-w-0 flex-1 bg-transparent px-2 text-[11px] outline-none" />
      </div>
      <IconButton label="화면 맞춤" onClick={() => flow.fitView({ padding: .12, duration: 260, maxZoom: 1.05 })}><Maximize2 size={14} /></IconButton>
      <IconButton label="PNG로 저장" onClick={() => void exportImage("png")}><Download size={14} /></IconButton>
      <IconButton label="SVG로 저장" onClick={() => void exportImage("svg")}><FileCode2 size={14} /></IconButton>
      <IconButton label="DOT로 저장" onClick={exportDot}><GitBranch size={14} /></IconButton>
    </div>

    {macroCount > 0 ? <div className="flex shrink-0 items-center gap-2 border-b border-amber-500/25 bg-amber-50 px-3 py-1.5 text-[10px] text-amber-800">
      <ShieldCheck size={12} className="shrink-0" />
      <span><b>ZIP 증명 경고 {macroCount}개.</b> {safeGraph.omittedReasons[0]}</span>
    </div> : null}

    <div className="flex min-h-0 flex-1">
      <aside className="no-print hidden w-56 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface-1)] lg:flex">
        <div className="border-b border-[var(--border)] px-3 py-2 text-[10px] font-semibold">{scope === "local" ? "핵심 ZIP 제작 순서" : "전체 ZIP 제작 순서"}</div>
        <div className="min-h-0 flex-1 overflow-auto p-1.5">
          {scope === "local" && constructorOperationCount > 0 ? <button type="button" onClick={() => { setActiveStep(-1); setFocusId(displayGraph?.rootId ?? null); }} className="mb-1 flex w-full items-center gap-2 border border-dashed border-[var(--border-strong)] bg-[var(--surface-2)] px-2 py-2 text-left text-[10px]">
            <span className="grid h-6 w-6 shrink-0 place-items-center bg-white"><Workflow size={14} /></span>
            <span className="min-w-0"><b className="block">전층 constructor</b><span className="text-[9px] text-[var(--muted)]">검증된 원시 연산 {constructorOperationCount}개 접음</span></span>
          </button> : null}
          {operations.map((node, index) => <button type="button" data-proof-operation={node.id} key={node.id} onClick={() => selectOperation(index)} className={cn("flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-left text-[10px]", index === activeStep ? "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_8%,white)]" : "border-transparent hover:border-[var(--border)] hover:bg-[var(--surface-2)]")}>
            <span className="w-6 shrink-0 text-right font-mono text-[9px] text-[var(--muted)]">{index + 1}</span>
            {operationAssets[node.operation ?? ""] ? <Image src={`/legacy-icons/${operationAssets[node.operation ?? ""]}`} width={16} height={16} alt="" unoptimized /> : <Box size={14} />}
            <span className="min-w-0 truncate">{node.label}</span>
          </button>)}
        </div>
        <div className="border-t border-[var(--border)] p-2 text-[9px] leading-4 text-[var(--muted)]">{shared ? "같은 하위 공정은 DAG에서 한 번만 표시됩니다." : "공유되는 하위 공정이 없는 제작 경로입니다."}</div>
      </aside>
      <div ref={wrapperRef} className="relative min-w-0 flex-1">
        <ReactFlow
          nodes={renderedNodes}
          edges={renderedEdges}
          nodeTypes={nodeTypes}
          minZoom={.05}
          maxZoom={2.2}
          onlyRenderVisibleElements
          selectionOnDrag={false}
          panOnDrag={[0, 1, 2]}
          nodesDraggable={false}
          nodesConnectable={false}
          onNodeClick={(_, node) => { const index = operations.findIndex((operation) => operation.id === node.id); setActiveStep(index); setFocusId(node.id); onNodeSelect?.(node.data); window.setTimeout(() => focusNode(node.id), 20); }}
          onPaneClick={() => onNodeSelect?.(null)}
          onMove={(_, viewport) => {
            const wrapper = wrapperRef.current;
            if (!wrapper) return;
            wrapper.classList.toggle("graph-far", viewport.zoom < .3);
            wrapper.style.setProperty("--graph-inverse-zoom", String(Math.max(1, 1 / Math.max(viewport.zoom, .05))));
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={22} size={1} color="var(--graph-dot)" />
          <Controls position="bottom-left" showInteractive={false} />
          <MiniMap position="bottom-right" pannable zoomable nodeColor={(node) => node.type === "operation" ? "var(--accent)" : node.type === "certificate" ? "#a77837" : "#61718a"} maskColor="rgba(240,240,240,.72)" />
        </ReactFlow>
      </div>
    </div>

    <div className="no-print flex h-12 shrink-0 items-center border-t border-[var(--border)] bg-[var(--surface-1)] px-2">
      <IconButton label="이전 단계" disabled={!operations.length} onClick={() => selectOperation(Math.max(0, activeStep - 1))}><ChevronLeft size={15} /></IconButton>
      <IconButton label={playing ? "일시정지" : "재생"} disabled={!operations.length} onClick={() => setPlaying((value) => !value)}>{playing ? <Pause size={15} /> : <Play size={15} />}</IconButton>
      <IconButton label="다음 단계" disabled={!operations.length} onClick={() => selectOperation(Math.min(operations.length - 1, activeStep + 1))}><ChevronRight size={15} /></IconButton>
      <div className="ml-2 min-w-0 flex-1">
        <div className="h-1 overflow-hidden bg-[var(--surface-3)]"><div className="h-full bg-[var(--accent)] transition-all" style={{ width: operations.length && activeStep >= 0 ? `${((activeStep + 1) / operations.length) * 100}%` : "0%" }} /></div>
        <div className="mt-1 truncate text-[9px] text-[var(--muted)]">{activeStep >= 0 ? `${activeStep + 1}단계 · ${operations[activeStep]?.label ?? ""}` : "단계를 선택하면 전체 DAG를 유지한 채 해당 연산으로 이동합니다."}</div>
      </div>
      <span className="ml-3 w-24 text-right text-[10px] text-[var(--muted)]">{operations.length ? `${Math.max(0, activeStep + 1)} / ${operations.length}` : "연산 없음"}</span>
      <Badge tone={safeGraph.replayStatus === "passed" ? "positive" : safeGraph.replayStatus === "failed" ? "negative" : "unknown"} className="ml-2">{safeGraph.replayStatus === "passed" ? "재생 검증 통과" : safeGraph.replayStatus === "failed" ? "재생 검증 실패" : "부분 재생 검증"}</Badge>
    </div>
  </div>;
});

export const ProofCanvas = forwardRef<ProofCanvasHandle, { graph: ProofGraph | null; onNodeSelect?: (node: ProofNodeData | null) => void }>(function ProofCanvas(props, ref) {
  return <ReactFlowProvider><ProofCanvasInner {...props} ref={ref} /></ReactFlowProvider>;
});
