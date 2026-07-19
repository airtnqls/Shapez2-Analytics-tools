"use client";

import { useState } from "react";
import { ArrowLeftRight, CheckCircle2, Play, XCircle } from "lucide-react";
import { SolverClient } from "@/lib/solver-client";
import type { AnalysisResult } from "@/lib/types";
import { Badge, Button, Metric, Panel, SectionTitle } from "./ui";
import { ShapeEditor } from "./shape-editor";
import { ShapeRenderer } from "./shape-renderer";

function ResultCard({ title, result }: { title: string; result: AnalysisResult | null }) {
  return <Panel>
    <SectionTitle title={title} action={result ? <Badge tone={result.verdict === "POSSIBLE" ? "positive" : result.verdict === "IMPOSSIBLE" ? "negative" : "unknown"}>{result.verdict}</Badge> : null} />
    <div className="p-4">
      {result ? <div className="space-y-3">
        <ShapeRenderer code={result.originalCode} showCode />
        <div className="flex flex-wrap gap-2"><Badge tone="accent">{result.shapeType}</Badge><Badge>{result.route}</Badge></div>
        <div className="grid grid-cols-2 gap-2"><Metric label="Height" value={result.facts.height} /><Metric label="Time" value={`${result.timing.totalMs.toFixed(1)} ms`} /></div>
        <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3 text-xs leading-5 text-[var(--muted)]">{result.reason}</div>
      </div> : <div className="grid min-h-[360px] place-items-center text-center text-sm text-[var(--muted)]">아직 분석되지 않았습니다.</div>}
    </div>
  </Panel>;
}

export function ComparePanel({ cap: initialCap, currentCode }: { cap: number; currentCode: string }) {
  const [codeA, setCodeA] = useState(currentCode);
  const [codeB, setCodeB] = useState("PPPP:cSSS:S-S-:SScS");
  const [capA, setCapA] = useState(initialCap);
  const [capB, setCapB] = useState(5);
  const [a, setA] = useState<AnalysisResult | null>(null);
  const [b, setB] = useState<AnalysisResult | null>(null);
  const [running, setRunning] = useState(false);

  const run = async () => {
    setRunning(true);
    const ca = new SolverClient();
    const cb = new SolverClient();
    try {
      const [ra, rb] = await Promise.all([
        ca.analyze(codeA, capA, "type").promise,
        cb.analyze(codeB, capB, "type").promise,
      ]);
      setA(ra); setB(rb);
    } finally {
      ca.terminate(); cb.terminate(); setRunning(false);
    }
  };

  const differences = a && b ? [
    ["판정", a.verdict, b.verdict],
    ["도형 유형", a.shapeType, b.shapeType],
    ["판정 경로", a.route, b.route],
    ["높이", a.facts.height, b.facts.height],
    ["점유 칸", a.facts.occupiedCells, b.facts.occupiedCells],
    ["물리 안정", a.facts.stable, b.facts.stable],
    ["Half 계열", a.facts.half, b.facts.half],
    ["교환 가능", a.facts.swappable, b.facts.swappable],
    ["쌓기 가능", a.facts.stackable, b.facts.stackable],
    ["PP 깊이", a.facts.ppDepth ?? "—", b.facts.ppDepth ?? "—"],
    ["Receipt rank σ", a.facts.receiptRank, b.facts.receiptRank],
    ["PP 연쇄 상한", a.facts.ppChainUpperBound, b.facts.ppChainUpperBound],
  ] : [];

  return <div className="h-full overflow-y-auto p-3">
    <div className="grid gap-3 xl:grid-cols-2">
      {[{ title: "도형 A", code: codeA, cap: capA, setCode: setCodeA, setCap: setCapA }, { title: "도형 B", code: codeB, cap: capB, setCode: setCodeB, setCap: setCapB }].map((item) => <Panel key={item.title}>
        <SectionTitle title={item.title} />
        <div className="space-y-3 p-4">
          <div className="grid grid-cols-[1fr_86px] gap-2"><input value={item.code} onChange={(event) => item.setCode(event.target.value)} className="h-10 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 font-mono text-xs outline-none focus:border-[var(--accent)]" /><input type="number" value={item.cap} min={1} max={100} onChange={(event) => item.setCap(Number(event.target.value) || 1)} className="h-10 rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 text-xs outline-none" /></div>
          <ShapeEditor code={item.code} cap={item.cap} onChange={item.setCode} compact />
        </div>
      </Panel>)}
    </div>
    <div className="my-3 flex justify-center"><Button variant="primary" disabled={running} onClick={() => void run()}><Play size={15} />{running ? "비교 분석 중…" : "두 도형 분석"}</Button></div>
    <div className="grid gap-3 xl:grid-cols-2"><ResultCard title="A 결과" result={a} /><ResultCard title="B 결과" result={b} /></div>
    {differences.length ? <Panel className="mt-3">
      <SectionTitle icon={<ArrowLeftRight size={15} />} title="차이점" />
      <div className="overflow-auto"><table className="w-full text-xs"><thead className="bg-[var(--surface-2)] text-[var(--muted)]"><tr><th className="p-3 text-left">항목</th><th className="p-3 text-left">A</th><th className="p-3 text-left">B</th><th className="p-3">일치</th></tr></thead><tbody>{differences.map(([label, va, vb]) => { const same = String(va) === String(vb); return <tr key={String(label)} className="border-t border-[var(--border)]"><td className="p-3 font-semibold">{String(label)}</td><td className="p-3">{String(va)}</td><td className="p-3">{String(vb)}</td><td className="p-3 text-center">{same ? <CheckCircle2 size={15} className="mx-auto text-emerald-400" /> : <XCircle size={15} className="mx-auto text-rose-400" />}</td></tr>; })}</tbody></table></div>
    </Panel> : null}
  </div>;
}
