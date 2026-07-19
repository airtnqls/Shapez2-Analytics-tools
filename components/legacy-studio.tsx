"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, ClipboardCheck,
  FileText, FlaskConical, GitBranch, Languages, ListRestart, Plus, RotateCcw,
  Save, Settings2, Share2, Square, Trash2, Workflow,
} from "lucide-react";
import { saveHistory } from "@/lib/db";
import { runZipOperation, traceZipInputs } from "@/lib/zip-api";
import { solverClient } from "@/lib/solver-client";
import type { AnalysisResult, AnalyzeMode, OperationName, ProgressMessage, ProofNodeData } from "@/lib/types";
import { KO_SHAPE_TYPE, KO_VERDICT } from "@/lib/ko";
import { AnalysisPanel } from "./analysis-panel";
import { BatchPanel } from "./batch-panel";
import { LegacyTestEditor } from "./legacy-test-editor";
import { ProofCanvas } from "./proof-canvas";
import { ShapeEditor } from "./shape-editor";
import { ShapeRenderer } from "./shape-renderer";
import { Badge, Button } from "./ui";
import { cn } from "@/lib/cn";

type MainTab = "analysis" | "batch" | "process" | "tests" | "help";

interface OutputItem { label: string; code: string }
interface OpButton { operation: string; label: string; icon?: string; needsB?: boolean }

const buildingRows: OpButton[][] = [
  [{ operation: "destroy_half", label: "반쪽 파괴", icon: "half-destroyer.png" }, { operation: "stack", label: "쌓기", icon: "stacker.png", needsB: true }],
  [{ operation: "push_pin", label: "핀 푸시", icon: "pin-pusher.png" }, { operation: "apply_physics", label: "물리 적용" }],
  [{ operation: "swap", label: "교환", icon: "swapper.png", needsB: true }, { operation: "half_cutter", label: "절단", icon: "cutter.png" }],
  [{ operation: "rotate_cw", label: "시계 회전", icon: "rotator-cw.png" }, { operation: "rotate_ccw", label: "반시계 회전", icon: "rotator-ccw.png" }],
  [{ operation: "rotate_180", label: "180° 회전", icon: "rotator-180.png" }, { operation: "classifier", label: "분류기" }],
  [{ operation: "simple_cutter", label: "단순 절단", icon: "cutter.png" }, { operation: "quad_cutter", label: "사분면 절단", icon: "cutter.png" }],
];

const reverseOps: OpButton[] = [
  { operation: "corner", label: "Corner" }, { operation: "claw", label: "Claw" },
  { operation: "hybrid", label: "Hybrid" }, { operation: "claw_hybrid", label: "Claw Hybrid" },
];
const dataOps: OpButton[] = [
  { operation: "simplify", label: "단순화" }, { operation: "detail", label: "상세화" },
  { operation: "corner_1q", label: "1Q Corner" }, { operation: "reverse", label: "역순" },
  { operation: "mirror", label: "대칭" }, { operation: "cornerize", label: "Cornerize" },
];

const tabs: Array<{ key: MainTab; label: string }> = [
  { key: "analysis", label: "분석 도구" }, { key: "batch", label: "대량 처리" },
  { key: "process", label: "공정 트리" }, { key: "tests", label: "테스트 편집기" },
  { key: "help", label: "도움말" },
];

const colorOptions = [
  ["r", "빨강", "#e33"], ["g", "초록", "#3c3"], ["b", "파랑", "#33e"],
  ["m", "자홍", "#e3e"], ["c", "청록", "#3cc"], ["y", "노랑", "#dd3"],
  ["u", "무색", "#bbb"], ["w", "흰색", "#fff"],
];

function OperationButton({ item, disabled, onClick }: { item: OpButton; disabled?: boolean; onClick: () => void }) {
  return <button type="button" disabled={disabled} onClick={onClick} title={item.label} className="legacy-op-button">
    {item.icon ? <Image src={`/legacy-icons/${item.icon}`} width={18} height={18} alt="" unoptimized /> : <span className="legacy-op-placeholder">◆</span>}
    <span>{item.label}</span>
  </button>;
}

function LegacyGroup({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return <section className={cn("legacy-group", className)}><div className="legacy-group-title">{title}</div>{children}</section>;
}

function HelpPanel({ onUse }: { onUse: (code: string) => void }) {
  const examples = [
    ["빈 도형", "----", "모든 사분면이 비어 있습니다."],
    ["기본 도형", "SSSS", "원재료에서 직접 시작할 수 있습니다."],
    ["Half", "cS--:SS--:-S--:cS--", "두 인접 기둥으로 구성된 전 레이어 Half입니다."],
    ["교환 가능형", "PPPP:cSSS:S-S-:SScS", "두 Half를 교환기로 조립합니다."],
    ["Claw", "-PPP:SS-P:---P:c--P:cS-S", "Pin Push 전구체가 인증된 도형입니다."],
  ];
  return <div className="h-full overflow-auto p-3 text-[11px]">
    <LegacyGroup title="링크"><div className="flex gap-4 p-3"><a href="https://github.com/airtnqls/Shapez2-Analytics-tools" target="_blank" rel="noreferrer">GitHub</a><a href="https://www.youtube.com/watch?v=Bs5tuStF8Wc" target="_blank" rel="noreferrer">YouTube</a></div></LegacyGroup>
    <LegacyGroup title="분류 소개" className="mt-3"><div className="divide-y divide-[var(--border)]">{examples.map(([name, code, description]) => <button type="button" key={name} onClick={() => onUse(code)} className="grid w-full grid-cols-[150px_190px_minmax(0,1fr)] items-center gap-4 p-3 text-left hover:bg-[#f4f8fc]"><b>{name}</b><ShapeRenderer code={code} compact /><span>{description}</span></button>)}</div></LegacyGroup>
  </div>;
}

export function LegacyStudio() {
  const [inputs, setInputs] = useState(["-PPP:SS-P:---P:c--P:cS-S", "SSSS"]);
  const [cap, setCap] = useState(5);
  const [activeTab, setActiveTab] = useState<MainTab>("analysis");
  const [outputs, setOutputs] = useState<OutputItem[]>([]);
  const [resultMessage, setResultMessage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<ProofNodeData | null>(null);
  const [running, setRunning] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressMessage | null>(null);
  const [paintColor, setPaintColor] = useState("r");
  const [crystalColor, setCrystalColor] = useState("r");
  const [autoApply, setAutoApply] = useState(false);
  const [logs, setLogs] = useState<string[]>(["Shapez2Analyzer Web 시작", "ZIP client worker 준비"]);
  const [verboseLog, setVerboseLog] = useState(true);
  const [logOpen, setLogOpen] = useState(true);
  const [operationBusy, setOperationBusy] = useState("");
  const [history, setHistory] = useState<string[][]>([["-PPP:SS-P:---P:c--P:cS-S", "SSSS"]]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const [editorOpen, setEditorOpen] = useState(true);
  const [urlReady, setUrlReady] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);
  const proofAttemptRef = useRef("");

  const inputA = inputs[0] ?? "";
  const inputB = inputs[1] ?? "";
  const log = useCallback((message: string) => setLogs((items) => [...items.slice(-499), `${new Date().toLocaleTimeString("ko-KR", { hour12: false })}  ${message}`]), []);

  useEffect(() => {
    document.documentElement.dataset.theme = "light";
    const params = new URLSearchParams(window.location.search);
    const value = params.get("value");
    const inputBValue = params.get("b");
    const sharedCap = Number(params.get("cap"));
    const sharedTab = params.get("tab");
    if (value) {
      const next = [value, inputBValue ?? "SSSS"];
      setInputs(next);
      setHistory([next]);
      setHistoryIndex(0);
    }
    if (Number.isFinite(sharedCap) && sharedCap > 0) setCap(Math.max(1, Math.min(999, sharedCap)));
    if (sharedTab && tabs.some((tab) => tab.key === sharedTab)) setActiveTab(sharedTab as MainTab);
    setUrlReady(true);
  }, []);

  useEffect(() => {
    if (!urlReady) return;
    const params = new URLSearchParams();
    params.set("value", inputA);
    if (inputB) params.set("b", inputB);
    params.set("cap", String(cap));
    params.set("tab", activeTab);
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}${window.location.hash}`);
  }, [activeTab, cap, inputA, inputB, urlReady]);

  const copyShareLink = useCallback(async () => {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(window.location.href);
    else {
      const textarea = document.createElement("textarea");
      textarea.value = window.location.href;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.append(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    setShareCopied(true);
    log("현재 입력과 화면 상태를 공유 링크로 복사했습니다.");
    window.setTimeout(() => setShareCopied(false), 1400);
  }, [log]);

  const commitInputs = useCallback((next: string[]) => {
    setInputs(next);
    setHistory((items) => [...items.slice(0, historyIndex + 1), next]);
    setHistoryIndex((index) => index + 1);
  }, [historyIndex]);

  const updateInput = (index: number, value: string) => setInputs((items) => items.map((item, itemIndex) => itemIndex === index ? value : item));
  const applyOutputs = useCallback((items = outputs) => {
    if (!items.length) return;
    const next = [...inputs];
    items.forEach((item, index) => { if (index < 6) next[index] = item.code; });
    next.length = Math.max(2, items.length);
    commitInputs(next);
    log(`출력을 입력에 적용: ${items.map((item, index) => `${String.fromCharCode(65 + index)}=${item.code}`).join(", ")}`);
  }, [commitInputs, inputs, log, outputs]);

  const runOperation = useCallback(async (item: OpButton | string) => {
    const operation = typeof item === "string" ? item : item.operation;
    if (!inputA.trim() || operationBusy) return;
    setOperationBusy(operation);
    setResultMessage("");
    try {
      if (operation === "classifier") {
        const classification = await solverClient.analyze(inputA, Math.max(cap, inputA.split(":").length), "type").promise;
        setResult(classification);
        setOutputs([]);
        setResultMessage(`${KO_VERDICT[classification.verdict]} · ${KO_SHAPE_TYPE[classification.shapeType]} · ${classification.reason}`);
        log(`classifier: ZIP ${classification.verdict} / ${classification.shapeType} / ${classification.route}`);
        setActiveTab("analysis");
        return;
      }
      if (["corner", "claw", "hybrid", "claw_hybrid"].includes(operation)) {
        const traced = await traceZipInputs(inputA, Math.max(cap, inputA.split(":").length));
        const nextOutputs = traced.inputs.flatMap((node, index) => node.code ? [{ label: `ZIP ${traced.operation} 입력 ${String.fromCharCode(65 + index)}`, code: node.code }] : []);
        setOutputs(nextOutputs);
        setResultMessage(`ZIP proof DAG 직전 연산: ${traced.operation}`);
        setResult((current) => current ? { ...current, proof: traced.graph } : current);
        log(`${operation}: ZIP proof의 ${traced.operation} 입력 ${nextOutputs.length}개`);
        if (autoApply && nextOutputs.length) applyOutputs(nextOutputs);
        setActiveTab("analysis");
        return;
      }
      const response = await runZipOperation({ operation: operation as OperationName, inputA, inputB, cap: Math.max(cap, inputA.split(":").length, inputB.split(":").length), paintColor, crystalColor });
      const nextOutputs = response.outputs.map((code, index) => ({ label: `출력 ${String.fromCharCode(65 + index)}`, code }));
      setOutputs(nextOutputs);
      setResultMessage(response.message === "완료" ? "" : response.message);
      log(`${operation}: ${response.message}${nextOutputs.length ? ` · ${nextOutputs.map((output) => output.code).join(" / ")}` : ""}`);
      if (autoApply && nextOutputs.length) applyOutputs(nextOutputs);
      setActiveTab("analysis");
      window.setTimeout(() => outputRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 20);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setResultMessage(message);
      log(`오류: ${message}`);
    } finally { setOperationBusy(""); }
  }, [applyOutputs, autoApply, cap, crystalColor, inputA, inputB, log, operationBusy, paintColor]);

  const runAnalysis = useCallback(async (mode: AnalyzeMode) => {
    if (!inputA.trim() || running) return;
    if (mode === "proof") setActiveTab("process");
    setRunning(true);
    setSelectedNode(null);
    setProgress(null);
    const job = solverClient.analyze(inputA, Math.max(cap, inputA.split(":").length), mode, setProgress);
    setActiveJobId(job.jobId);
    try {
      const value = await job.promise;
      setResult(value);
      setResultMessage(`${KO_VERDICT[value.verdict]} · ${KO_SHAPE_TYPE[value.shapeType]} · ${value.reason}`);
      log(`${mode}: C${value.cap} · ${value.verdict} / ${value.shapeType} / ${value.route} (${value.timing.totalMs.toFixed(1)}ms)`);
      await saveHistory({ createdAt: Date.now(), code: value.originalCode, normalizedCode: value.normalizedCode, cap: value.cap, verdict: value.verdict, shapeType: value.shapeType, route: value.route, elapsedMs: value.timing.totalMs, favorite: false, result: value });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes("CANCELLED")) { setResultMessage(message); log(`분석 오류: ${message}`); }
    } finally { setRunning(false); setActiveJobId(null); setProgress(null); }
  }, [cap, inputA, log, running]);

  useEffect(() => {
    if (activeTab !== "process" || running || (result?.proof && result.originalCode === inputA)) return;
    const requestKey = `${inputA}|${Math.max(cap, inputA.split(":").length)}`;
    if (!inputA.trim() || proofAttemptRef.current === requestKey) return;
    proofAttemptRef.current = requestKey;
    const timer = window.setTimeout(() => void runAnalysis("proof"), 0);
    return () => window.clearTimeout(timer);
  }, [activeTab, cap, inputA, result?.originalCode, result?.proof, runAnalysis, running]);

  const selectTab = (tab: MainTab) => {
    setActiveTab(tab);
    if (tab === "process" && (!result?.proof || result.originalCode !== inputA)) proofAttemptRef.current = "";
  };

  const useTarget = (code: string) => {
    const next = [...inputs]; next[0] = code; commitInputs(next);
    setActiveTab("analysis");
  };

  const analysisContent = <div className="legacy-analysis-tab flex h-full min-h-0 flex-col p-2">
    <LegacyGroup title="출력" className="min-h-0 flex-1">
      <div ref={outputRef} className="flex min-h-[280px] flex-wrap items-start gap-4 overflow-auto p-4">
        {inputs.filter(Boolean).map((code, index) => <div key={`input-${index}`} className="legacy-shape-card"><div className="legacy-shape-card-title">입력 {String.fromCharCode(65 + index)} · 드래그 가능</div><ShapeRenderer code={code} showCode dragEnabled onCodeDrop={(dropped) => updateInput(index, dropped)} /></div>)}
        {outputs.length ? <div className="legacy-output-divider" /> : null}
        {outputs.map((output) => <button type="button" key={output.label} className="legacy-shape-card text-left" onClick={() => useTarget(output.code)}><div className="legacy-shape-card-title">{output.label} · 입력으로 드래그</div><ShapeRenderer code={output.code} showCode dragEnabled /></button>)}
        {!inputs.some(Boolean) && !outputs.length ? <p className="m-auto text-[var(--muted)]">왼쪽에서 도형을 입력하세요.</p> : null}
      </div>
      {resultMessage ? <div className="border-t border-[var(--border)] bg-[#f7f7f7] px-3 py-2 text-[11px]">{resultMessage}</div> : null}
    </LegacyGroup>
    <button type="button" onClick={() => setEditorOpen((value) => !value)} className="mt-2 flex h-8 items-center border border-[var(--border)] bg-white px-3 text-[11px]"><FlaskConical size={13} className="mr-2" />도형 직접 편집<ChevronDown size={13} className={cn("ml-auto", editorOpen && "rotate-180")} /></button>
    {editorOpen ? <div className="max-h-[360px] overflow-auto border-x border-b border-[var(--border)] bg-white"><ShapeEditor code={inputA} cap={Math.max(cap, inputA.split(":").filter(Boolean).length)} onChange={(value) => updateInput(0, value)} exactMode /></div> : null}
  </div>;

  const centerContent = activeTab === "analysis" ? analysisContent
    : activeTab === "batch" ? <BatchPanel defaultCap={cap} onUseTarget={useTarget} />
    : activeTab === "process" ? <ProofCanvas graph={result?.proof ?? null} onNodeSelect={setSelectedNode} />
    : activeTab === "tests" ? <LegacyTestEditor onLog={log} />
    : <HelpPanel onUse={useTarget} />;

  return <div className="legacy-web-shell flex h-dvh min-h-[650px] flex-col overflow-hidden bg-[var(--surface-0)] text-[var(--text)]">
    <header className="legacy-titlebar flex h-10 shrink-0 items-center border-b border-[var(--border)] bg-[var(--surface-1)] px-3">
      <Image src="/legacy-icons/globe.png" width={18} height={18} alt="" unoptimized />
      <b className="ml-2 text-[12px]">Shapez2Analyzer Web</b><span className="ml-2 text-[10px] text-[var(--muted)]">ZIP client worker · 공유 가능한 공정 DAG</span>
      <div className="ml-auto flex items-center gap-2 text-[10px]"><Button size="xs" variant="ghost" onClick={() => void copyShareLink()}><Share2 size={12} />{shareCopied ? "복사됨" : "링크 복사"}</Button><Languages size={13} /><select defaultValue="ko"><option value="ko">한국어</option><option value="en">English</option></select><Settings2 size={13} /><span>설정 C{cap}{result && result.cap !== cap ? ` · 분석 C${result.cap}` : ""}</span></div>
    </header>

    <div className={cn("grid min-h-0 flex-1", logOpen ? "grid-cols-[330px_minmax(520px,1fr)_290px]" : "grid-cols-[330px_minmax(520px,1fr)_28px]") }>
      <aside className="legacy-left-panel min-h-0 overflow-y-auto border-r border-[#bcbcbc] bg-[#f5f5f5] p-2">
        <div className="mb-2 flex items-center gap-2 text-[11px]"><Languages size={14} /><span>언어</span><select className="ml-auto" defaultValue="ko"><option value="ko">한국어</option><option value="en">English</option></select></div>
        <LegacyGroup title="모드"><div className="legacy-form-grid p-2"><label>최대 층</label><input type="number" min={1} max={999} value={cap} onChange={(event) => setCap(Math.max(1, Number(event.target.value) || 1))} /><label>최대 사분면</label><input value="4" disabled /></div></LegacyGroup>
        <LegacyGroup title="입력" className="mt-2"><div className="grid gap-1 p-2">{inputs.map((value, index) => <div key={index} className="grid grid-cols-[22px_minmax(0,1fr)_24px] items-center gap-1"><b>{String.fromCharCode(65 + index)}</b><input className="font-mono text-[10px]" value={value} onChange={(event) => updateInput(index, event.target.value)} onBlur={() => { if (history[historyIndex]?.join("\n") !== inputs.join("\n")) commitInputs([...inputs]); }} /><button type="button" disabled={inputs.length <= 2} onClick={() => commitInputs(inputs.filter((_, itemIndex) => itemIndex !== index))}>×</button></div>)}<div className="flex gap-1 pt-1"><Button size="xs" disabled={historyIndex <= 0} onClick={() => { const index = historyIndex - 1; setHistoryIndex(index); setInputs(history[index]); }}><ChevronLeft size={12} />Undo</Button><Button size="xs" disabled={historyIndex >= history.length - 1} onClick={() => { const index = historyIndex + 1; setHistoryIndex(index); setInputs(history[index]); }}>Redo<ChevronRight size={12} /></Button><Button size="xs" disabled={inputs.length >= 6} onClick={() => commitInputs([...inputs, ""])}><Plus size={12} />입력</Button></div></div></LegacyGroup>

        <LegacyGroup title="건물 작동" className="mt-2"><div className="grid gap-1 p-2">{buildingRows.map((row, index) => <div className="grid grid-cols-2 gap-1" key={index}>{row.map((item) => <OperationButton key={item.operation} item={item} disabled={Boolean(operationBusy) || (item.needsB && !inputB)} onClick={() => void runOperation(item)} />)}</div>)}
          <div className="grid grid-cols-[64px_1fr] gap-1"><select value={paintColor} onChange={(event) => setPaintColor(event.target.value)}>{colorOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><OperationButton item={{ operation: "paint", label: "도색", icon: "painter.png" }} disabled={Boolean(operationBusy)} onClick={() => void runOperation("paint")} /></div>
          <div className="grid grid-cols-[64px_1fr] gap-1"><select value={crystalColor} onChange={(event) => setCrystalColor(event.target.value)}>{colorOptions.filter(([value]) => value !== "u").map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><OperationButton item={{ operation: "crystal_generator", label: "결정 생성", icon: "crystal-generator.png" }} disabled={Boolean(operationBusy)} onClick={() => void runOperation("crystal_generator")} /></div>
          <div className="grid grid-cols-2 gap-1 pt-1"><Button size="sm" disabled={!outputs.length} onClick={() => applyOutputs()}>출력 적용</Button><label className="flex items-center justify-center gap-1 text-[10px]"><input type="checkbox" checked={autoApply} onChange={(event) => setAutoApply(event.target.checked)} />자동 적용</label></div>
        </div></LegacyGroup>

        <LegacyGroup title="역연산" className="mt-2"><div className="grid grid-cols-2 gap-1 p-2">{reverseOps.map((item) => <OperationButton key={item.operation} item={item} disabled={Boolean(operationBusy)} onClick={() => void runOperation(item)} />)}</div></LegacyGroup>
        <LegacyGroup title="데이터 처리" className="mt-2"><div className="grid grid-cols-2 gap-1 p-2">{dataOps.map((item) => <OperationButton key={item.operation} item={item} disabled={Boolean(operationBusy)} onClick={() => void runOperation(item)} />)}</div></LegacyGroup>
        <LegacyGroup title="ZIP 판정" className="mt-2"><div className="grid grid-cols-3 gap-1 p-2"><Button size="xs" disabled={running} onClick={() => void runAnalysis("fast")}>빠른 판정</Button><Button size="xs" disabled={running} onClick={() => void runAnalysis("type")}>상세 분석</Button>{running ? <Button size="xs" variant="danger" onClick={() => { if (activeJobId) solverClient.cancel(activeJobId); }}><Square size={11} /></Button> : <Button size="xs" variant="primary" onClick={() => void runAnalysis("proof")}><Workflow size={11} />공정</Button>}</div></LegacyGroup>
      </aside>

      <main className="flex min-h-0 min-w-0 flex-col bg-[var(--surface-1)]">
        <nav className="legacy-main-tabs flex h-8 shrink-0 items-end border-b border-[var(--border)] bg-[var(--surface-1)] px-1">{tabs.map((tab) => <button type="button" key={tab.key} onClick={() => selectTab(tab.key)} className={cn(activeTab === tab.key && "active")}>{tab.label}</button>)}</nav>
        <div className="min-h-0 flex-1">{centerContent}</div>
      </main>

      <aside className="relative min-h-0 border-l border-[var(--border)] bg-[var(--surface-0)]">
        <button type="button" className="absolute left-0 top-1 z-10 h-7 w-7" onClick={() => setLogOpen((value) => !value)} title={logOpen ? "로그 접기" : "로그 열기"}>{logOpen ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}</button>
        {logOpen ? <div className="flex h-full min-h-0 flex-col p-2 pl-8">
          <LegacyGroup title="로그" className="flex min-h-0 flex-1 flex-col"><div className="flex items-center gap-2 border-b border-[#ccc] p-1 text-[10px]"><label><input type="checkbox" checked={verboseLog} onChange={(event) => setVerboseLog(event.target.checked)} /> 상세 로그</label><button type="button" className="ml-auto" onClick={() => setLogs([])}><Trash2 size={12} /></button></div><pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap p-2 text-[9px] leading-4">{verboseLog ? logs.join("\n") : logs.slice(-12).join("\n")}</pre></LegacyGroup>
          <LegacyGroup title={selectedNode ? "선택 공정 상세" : "분석 상세"} className="mt-2 h-[42%] min-h-[190px]"><AnalysisPanel result={result} selectedNode={selectedNode} /></LegacyGroup>
        </div> : null}
      </aside>
    </div>

    <footer className="flex h-6 shrink-0 items-center border-t border-[var(--border)] bg-[var(--surface-1)] px-2 text-[9px] text-[var(--muted)]"><span>{operationBusy ? `${operationBusy} 실행 중` : running ? progress?.message ?? "분석 중" : "준비"}</span>{result ? <span className="ml-auto"><b>{KO_VERDICT[result.verdict]}</b> · {KO_SHAPE_TYPE[result.shapeType]} · 노드 {result.proof?.nodes.length ?? 0}</span> : null}</footer>
  </div>;
}
