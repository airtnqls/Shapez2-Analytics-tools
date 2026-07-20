"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, Beaker, ChevronDown, ChevronRight, GitCompareArrows, History, Layers3, Menu,
  Moon, Play, Settings, Square, Sun, Workflow, X,
} from "lucide-react";
import { solverClient } from "@/lib/solver-client";
import { saveHistory } from "@/lib/db";
import { simplifyExactCode } from "@/lib/shape";
import { useAppStore, type WorkspaceTab } from "@/lib/store";
import type { AnalyzeMode, ProofNodeData } from "@/lib/types";
import { KO_MODE, KO_SHAPE_TYPE, KO_VERDICT } from "@/lib/ko";
import { AnalysisPanel } from "./analysis-panel";
import { BatchPanel } from "./batch-panel";
import { ComparePanel } from "./compare-panel";
import { HistoryPanel } from "./history-panel";
import { OperationsLab } from "./operations-lab";
import { SmartProofCanvas } from "./smart-proof-canvas";
import { ResearchPanel } from "./research-panel";
import { ShapeEditor } from "./shape-editor";
import { ShapeRenderer } from "./shape-renderer";
import { Button, IconButton } from "./ui";
import { cn } from "@/lib/cn";

const toolTabs: Array<{ key: WorkspaceTab; label: string; icon: React.ReactNode }> = [
  { key: "lab", label: "연산 실험", icon: <Beaker size={14} /> },
  { key: "batch", label: "일괄 분석", icon: <Menu size={14} /> },
  { key: "compare", label: "비교", icon: <GitCompareArrows size={14} /> },
];

function verdictClass(verdict?: string): string {
  return verdict === "POSSIBLE" ? "text-emerald-400" : verdict === "IMPOSSIBLE" ? "text-rose-400" : verdict === "UNKNOWN" ? "text-amber-400" : "text-[var(--muted)]";
}

export function AppShell() {
  const store = useAppStore();
  const [selectedNode, setSelectedNode] = useState<ProofNodeData | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [structureMode, setStructureMode] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);

  useEffect(() => {
    const resolved = store.theme === "system" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : store.theme;
    document.documentElement.dataset.theme = resolved;
  }, [store.theme]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("tmam-focused-ui") ?? "null") as { code?: string; cap?: number; theme?: "dark" | "light" | "system"; advanced?: boolean } | null;
      if (saved?.code) store.setCode(saved.code);
      if (saved?.cap) store.setCap(saved.cap);
      if (saved?.theme) store.setTheme(saved.theme);
      if (typeof saved?.advanced === "boolean") setAdvanced(saved.advanced);
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    localStorage.setItem("tmam-focused-ui", JSON.stringify({ code: store.code, cap: store.cap, theme: store.theme, advanced }));
  }, [advanced, store.cap, store.code, store.theme]);

  const run = useCallback(async (mode: AnalyzeMode) => {
    if (store.running) return;
    const code = store.code.trim();
    if (!code) { store.setError("도형 코드를 입력하세요."); return; }
    store.setMode(mode); store.setError(null); store.setProgress(null); setSelectedNode(null);
    if (mode === "proof") store.setWorkspaceTab("proof");
    else store.setWorkspaceTab("shape");
    const { jobId, promise } = solverClient.analyze(code, store.cap, mode, (progress) => store.setProgress(progress));
    store.setRunning(true, jobId);
    try {
      const result = await promise;
      store.setResult(result); store.setProgress(null);
      setDetailsOpen(mode === "type");
      await saveHistory({
        createdAt: Date.now(), code: result.originalCode, normalizedCode: result.normalizedCode,
        cap: result.cap, verdict: result.verdict, shapeType: result.shapeType,
        route: result.route, elapsedMs: result.timing.totalMs, favorite: false, result,
      });
      window.dispatchEvent(new Event("tmam-history"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes("CANCELLED")) store.setError(message);
    } finally { store.setRunning(false); }
  }, [store]);

  const cancel = useCallback(() => {
    if (store.activeJobId) solverClient.cancel(store.activeJobId);
  }, [store.activeJobId]);

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); void run(event.shiftKey ? "type" : "fast"); }
      if (event.altKey && event.key === "Enter") { event.preventDefault(); void run("proof"); }
      if (event.key === "Escape") { setDetailsOpen(false); setHistoryOpen(false); setSettingsOpen(false); setToolsOpen(false); setSelectedNode(null); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [run]);

  const useTarget = (code: string, cap = Math.max(store.cap, simplifyExactCode(code).split(":").length), proof = false) => {
    store.setCode(code); store.setCap(cap); store.setWorkspaceTab("shape"); setHistoryOpen(false);
    if (proof) window.setTimeout(() => void run("proof"), 10);
  };

  const resultLine = useMemo(() => {
    if (store.running) return <><span className="font-semibold text-[var(--text)]">{store.progress?.message ?? "실행 중"}</span><span className="ml-2 text-[var(--muted)]">{store.progress?.elapsedMs?.toFixed(0) ?? 0} ms</span></>;
    if (store.error) return <span className="font-medium text-rose-400">{store.error}</span>;
    if (!store.result) return <span className="text-[var(--muted)]">도형을 입력한 뒤 빠른 판정, 상세 분석 또는 제작 과정을 실행하세요.</span>;
    const result = store.result;
    return <>
      <span className={cn("font-semibold", verdictClass(result.verdict))}>{KO_VERDICT[result.verdict]}</span>
      {result.mode !== "fast" ? <><span className="mx-2 text-[var(--border-strong)]">/</span><span>{KO_SHAPE_TYPE[result.shapeType]}</span></> : null}
      <span className="ml-2 text-[var(--muted)]">{result.timing.totalMs.toFixed(2)} ms</span>
    </>;
  }, [store.error, store.progress, store.result, store.running]);

  const shapeWorkspace = <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[380px_minmax(0,1fr)]">
    <section className="flex min-h-0 flex-col border-r border-[var(--border)] bg-[var(--surface-1)]">
      <div className="border-b border-[var(--border)] p-3">
        <label className="mb-1 block text-[11px] font-semibold">도형 코드</label>
        <textarea value={store.code} onChange={(event) => store.setCode(event.target.value)} spellCheck={false} className="h-20 w-full resize-y border border-[var(--border-strong)] bg-[var(--surface-0)] p-2 font-mono text-[11px] outline-none focus:border-[var(--accent)]" />
        <div className="mt-2 flex items-center gap-2">
          <label className="text-[10px] text-[var(--muted)]">최대 층</label>
          <input type="number" min={1} max={100} value={store.cap} onChange={(event) => store.setCap(Number(event.target.value))} className="h-7 w-16 border border-[var(--border)] bg-[var(--surface-0)] px-2 text-[11px]" />
          <label className="ml-auto flex items-center gap-1.5 text-[10px] text-[var(--muted)]"><input type="checkbox" checked={structureMode} onChange={(event) => setStructureMode(event.target.checked)} />구조만 표시</label>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-1.5">
          <Button size="sm" variant="outline" disabled={store.running} onClick={() => void run("fast")} title="가능·불가능·미확정만 판정합니다. 유형 분석과 그래프는 만들지 않습니다."><Play size={13} />판정 · 빠름</Button>
          <Button size="sm" variant="outline" disabled={store.running} onClick={() => void run("type")} title="도형 유형과 판정 근거를 분석합니다. 제작 그래프는 만들지 않습니다."><Activity size={13} />분석</Button>
          {store.running ? <Button size="sm" variant="danger" onClick={cancel}><Square size={13} />중단</Button> : <Button size="sm" variant="primary" onClick={() => void run("proof")} title="기본 입력까지의 제작 과정을 생성합니다."><Workflow size={13} />제작 과정</Button>}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <button type="button" onClick={() => setEditorOpen((value) => !value)} className="flex w-full items-center border-b border-[var(--border)] px-3 py-2 text-left text-[11px] font-semibold hover:bg-[var(--surface-2)]">
          직접 편집기 <ChevronDown size={13} className={cn("ml-auto transition-transform", editorOpen && "rotate-180")} />
        </button>
        {editorOpen ? <ShapeEditor code={store.code} cap={store.cap} onChange={store.setCode} compact exactMode={!structureMode} /> : <p className="px-3 py-3 text-[10px] leading-5 text-[var(--muted)]">격자 편집이 필요할 때만 열 수 있습니다.</p>}
      </div>
    </section>

    <section className="flex min-h-0 flex-col bg-[var(--surface-0)]">
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-6">
        <ShapeRenderer code={store.code} structuralOnly={structureMode} showQuadrants maxLayers={20} large />
      </div>
      <div className="flex min-h-11 shrink-0 items-center border-t border-[var(--border)] bg-[var(--surface-1)] px-4 text-[11px]">
        <div className="flex min-w-0 flex-1 items-center">{resultLine}</div>
        {store.result?.mode !== "fast" ? <Button size="xs" variant="ghost" onClick={() => setDetailsOpen(true)}>상세 보기<ChevronRight size={12} /></Button> : null}
        {store.result?.proof ? <Button size="xs" variant="ghost" onClick={() => store.setWorkspaceTab("proof")}>제작 과정 열기<ChevronRight size={12} /></Button> : null}
      </div>
    </section>
  </div>;

  const workspace = store.workspaceTab === "shape" ? shapeWorkspace
    : store.workspaceTab === "proof" ? <div className="relative h-full min-h-0"><SmartProofCanvas graph={store.result?.proof ?? null} onNodeSelect={(node) => { setSelectedNode(node); if (node) setDetailsOpen(true); }} /></div>
    : store.workspaceTab === "lab" ? <OperationsLab cap={store.cap} onUseTarget={useTarget} />
    : store.workspaceTab === "batch" ? <BatchPanel defaultCap={store.cap} onUseTarget={(code) => useTarget(code)} />
    : store.workspaceTab === "compare" ? <ComparePanel cap={store.cap} currentCode={store.code} />
    : <ResearchPanel result={store.result} progress={store.progress} logs={[]} />;

  return <div className="legacy-shell flex h-dvh min-h-[600px] flex-col overflow-hidden bg-[var(--surface-0)] text-[var(--text)]">
    <header className="legacy-menubar flex h-12 shrink-0 items-center border-b border-[var(--border)] bg-[var(--surface-1)] px-2">
      <button type="button" onClick={() => store.setWorkspaceTab("shape")} className="mr-3 flex items-center gap-2 px-1">
        <span className="grid h-7 w-7 place-items-center bg-[var(--accent)] text-[var(--accent-contrast)]"><Workflow size={15} /></span>
        <span className="hidden text-left sm:block"><b className="block text-[11px]">Shapez2 TMAM</b><span className="block text-[9px] text-[var(--muted)]">CPCP 제작 도구 · Web</span></span>
      </button>
      <nav className="flex h-full min-w-0 items-center">
        <button type="button" onClick={() => { store.setWorkspaceTab("shape"); setToolsOpen(false); }} className={cn("relative flex h-full shrink-0 items-center gap-1.5 px-3 text-[11px] text-[var(--muted)] hover:text-[var(--text)]", store.workspaceTab === "shape" && "text-[var(--text)] after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-[var(--accent)]")}><Layers3 size={14} />도형</button>
        <button type="button" onClick={() => { store.setWorkspaceTab("proof"); setToolsOpen(false); }} className={cn("relative flex h-full shrink-0 items-center gap-1.5 px-3 text-[11px] text-[var(--muted)] hover:text-[var(--text)]", store.workspaceTab === "proof" && "text-[var(--text)] after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-[var(--accent)]")}><Workflow size={14} />제작 과정</button>
        <div className="relative h-full">
          <button type="button" onClick={() => setToolsOpen((value) => !value)} className={cn("flex h-full items-center gap-1.5 px-3 text-[11px] text-[var(--muted)] hover:text-[var(--text)]", ["lab", "batch", "compare"].includes(store.workspaceTab) && "text-[var(--text)]")}><Menu size={14} />도구<ChevronDown size={12} /></button>
          {toolsOpen ? <div className="absolute left-0 top-full z-40 min-w-40 border border-[var(--border)] bg-[var(--surface-1)] py-1 shadow-xl">
            {toolTabs.map((tab) => <button key={tab.key} type="button" onClick={() => { store.setWorkspaceTab(tab.key); setToolsOpen(false); }} className={cn("flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]", store.workspaceTab === tab.key && "text-[var(--text)]")}>{tab.icon}{tab.label}</button>)}
          </div> : null}
        </div>
        {advanced ? <button type="button" onClick={() => { store.setWorkspaceTab("research"); setToolsOpen(false); }} className={cn("relative flex h-full shrink-0 items-center gap-1.5 px-3 text-[11px] text-[var(--muted)]", store.workspaceTab === "research" && "text-[var(--text)] after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-[var(--accent)]")}><Activity size={14} />연구</button> : null}
      </nav>
      <div className="ml-auto flex items-center gap-0.5">
        <button type="button" onClick={() => setAdvanced((value) => !value)} className={cn("h-7 border px-2 text-[10px]", advanced ? "border-[var(--accent)] text-[var(--text)]" : "border-[var(--border)] text-[var(--muted)]")}>고급</button>
        <IconButton label="기록" onClick={() => setHistoryOpen(true)}><History size={14} /></IconButton>
        <IconButton label="설정" onClick={() => setSettingsOpen(true)}><Settings size={14} /></IconButton>
      </div>
    </header>

    <main className="min-h-0 flex-1">{workspace}</main>

    <footer className="flex h-6 shrink-0 items-center border-t border-[var(--border)] bg-[var(--surface-1)] px-3 text-[9px] text-[var(--muted)]">
      <span>{store.running ? store.progress?.message ?? "실행 중" : "브라우저에서 로컬 실행"}</span>
      {advanced && store.result ? <span className="ml-auto">상태 {store.result.diagnostics.statesVisited.toLocaleString()} · 후보 {store.result.diagnostics.candidatesChecked.toLocaleString()} · {KO_MODE[store.result.mode]}</span> : null}
    </footer>

    {detailsOpen ? <div className="fixed inset-0 z-50 bg-black/45" onMouseDown={(event) => { if (event.currentTarget === event.target) { setDetailsOpen(false); setSelectedNode(null); } }}>
      <aside className="absolute inset-y-0 right-0 w-[min(92vw,390px)] border-l border-[var(--border)] bg-[var(--surface-1)] shadow-2xl">
        <div className="flex h-11 items-center border-b border-[var(--border)] px-3"><b className="text-[12px]">{selectedNode ? "공정 항목" : "상세 분석"}</b><span className="ml-auto"><IconButton label="닫기" onClick={() => { setDetailsOpen(false); setSelectedNode(null); }}><X size={14} /></IconButton></span></div>
        <div className="h-[calc(100%-44px)]"><AnalysisPanel result={store.result} selectedNode={selectedNode} /></div>
      </aside>
    </div> : null}

    {historyOpen ? <div className="fixed inset-0 z-50 bg-black/55 p-4" onMouseDown={(event) => { if (event.currentTarget === event.target) setHistoryOpen(false); }}><div className="mx-auto flex h-[min(720px,92vh)] max-w-4xl flex-col border border-[var(--border)] bg-[var(--surface-1)]"><div className="flex h-11 items-center border-b border-[var(--border)] px-3"><b className="text-[12px]">분석 기록</b><span className="ml-auto"><IconButton label="닫기" onClick={() => setHistoryOpen(false)}><X size={14} /></IconButton></span></div><div className="min-h-0 flex-1"><HistoryPanel embedded onUse={useTarget} /></div></div></div> : null}

    {settingsOpen ? <div className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-4" onMouseDown={(event) => { if (event.currentTarget === event.target) setSettingsOpen(false); }}><div className="w-full max-w-sm border border-[var(--border)] bg-[var(--surface-1)]"><div className="flex h-11 items-center border-b border-[var(--border)] px-3"><b className="text-[12px]">설정</b><span className="ml-auto"><IconButton label="닫기" onClick={() => setSettingsOpen(false)}><X size={14} /></IconButton></span></div><div className="p-3"><p className="mb-2 text-[10px] text-[var(--muted)]">화면 테마</p><div className="grid grid-cols-3 gap-1"><Button size="sm" variant={store.theme === "dark" ? "primary" : "outline"} onClick={() => store.setTheme("dark")}><Moon size={12} />어둡게</Button><Button size="sm" variant={store.theme === "light" ? "primary" : "outline"} onClick={() => store.setTheme("light")}><Sun size={12} />밝게</Button><Button size="sm" variant={store.theme === "system" ? "primary" : "outline"} onClick={() => store.setTheme("system")}><Settings size={12} />시스템</Button></div><p className="mt-4 border-t border-[var(--border)] pt-3 text-[10px] leading-5 text-[var(--muted)]">Ctrl+Enter: 빠른 판정<br />Ctrl+Shift+Enter: 상세 분석<br />Alt+Enter: 제작 과정</p></div></div></div> : null}
  </div>;
}
