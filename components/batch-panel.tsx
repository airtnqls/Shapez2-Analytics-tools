"use client";

import { useMemo, useRef, useState } from "react";
import JSZip from "jszip";
import { Download, FileText, Filter, Play, RotateCcw, Square, Upload, XCircle } from "lucide-react";
import { canonicalCode, extractShapeCodes, simplifyExactCode } from "@/lib/shape";
import { cornerCheck } from "@/lib/classifier";
import { SolverClient } from "@/lib/solver-client";
import type { AnalyzeMode, BatchRow } from "@/lib/types";
import { Badge, Button, Metric, Panel, SectionTitle } from "./ui";
import { ShapeRenderer } from "./shape-renderer";

function csvEscape(value: unknown): string {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function BatchPanel({ defaultCap, onUseTarget }: { defaultCap: number; onUseTarget: (code: string) => void }) {
  const [text, setText] = useState("SSSS\nP-P-:P---:cS-S\nPPPP:-PSS:-P--:-ScS");
  const [rows, setRows] = useState<BatchRow[]>([]);
  const [mode, setMode] = useState<AnalyzeMode>("type");
  const [regex, setRegex] = useState("");
  const [workers, setWorkers] = useState(Math.max(1, Math.min(4, (typeof navigator === "undefined" ? 4 : navigator.hardwareConcurrency || 4) - 1)));
  const [running, setRunning] = useState(false);
  const [generateLayers, setGenerateLayers] = useState(3);
  const [generateLimit, setGenerateLimit] = useState(500);
  const [excludeSymmetry, setExcludeSymmetry] = useState(true);
  const [cancelled, setCancelled] = useState(false);
  const [resultFilter, setResultFilter] = useState<"all" | "possible" | "impossible" | "unknown" | "error">("all");
  const [page, setPage] = useState(0);
  const [parseError, setParseError] = useState("");
  const clientsRef = useRef<SolverClient[]>([]);
  const cancelRef = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const parse = () => {
    let query: RegExp | null = null;
    try { if (regex.trim()) query = new RegExp(regex, "i"); }
    catch (error) { setParseError(error instanceof Error ? error.message : String(error)); return; }
    setParseError("");
    const seen = new Set<string>();
    const codes = extractShapeCodes(text).map((raw) => ({ raw, code: simplifyExactCode(raw) })).filter((entry) => {
      if (!entry.code || (query && !query.test(entry.raw) && !query.test(entry.code)) || seen.has(entry.code)) return false;
      seen.add(entry.code);
      return true;
    });
    setRows(codes.map((entry, index) => ({ index, raw: entry.raw, code: entry.code, cap: Math.max(defaultCap, entry.code.split(":").length), status: "pending" })));
    setPage(0);
  };

  const summary = useMemo(() => {
    const done = rows.filter((row) => row.status === "done");
    return {
      total: rows.length,
      done: done.length,
      possible: done.filter((row) => row.result?.verdict === "POSSIBLE").length,
      impossible: done.filter((row) => row.result?.verdict === "IMPOSSIBLE").length,
      unknown: done.filter((row) => row.result?.verdict === "UNKNOWN").length,
      error: rows.filter((row) => row.status === "error").length,
    };
  }, [rows]);

  const filteredRows = useMemo(() => rows.filter((row) => {
    if (resultFilter === "all") return true;
    if (resultFilter === "error") return row.status === "error";
    return row.result?.verdict.toLowerCase() === resultFilter;
  }), [resultFilter, rows]);
  const pageSize = 100;
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const visibleRows = filteredRows.slice(page * pageSize, (page + 1) * pageSize);

  const generateCornerCandidates = async () => {
    if (running) return;
    let query: RegExp | null = null;
    if (regex.trim()) query = new RegExp(regex, "i");
    setRunning(true);
    cancelRef.current = false;
    const alphabet = ["-", "S", "P", "c"];
    const layerValues: string[] = [];
    for (let value = 0; value < 256; value += 1) {
      let n = value;
      let row = "";
      for (let q = 0; q < 4; q += 1) { row += alphabet[n & 3]; n >>= 2; }
      layerValues.push(row);
    }
    const found: string[] = [];
    const buffer: string[] = [];
    let visited = 0;
    const dfs = async (depth: number): Promise<boolean> => {
      if (cancelRef.current) return true;
      if (depth === generateLayers) {
        visited += 1;
        const code = buffer.join(":").replace(/(?::?----)+$/, "");
        if (!code) return false;
        const pillars = [0, 1, 2, 3].map((q) => buffer.map((row) => row[q]).join("").replace(/-+$/, ""));
        if (!pillars.every((pillar) => cornerCheck(pillar).accepted)) return false;
        if (query && !query.test(code)) return false;
        if (excludeSymmetry && canonicalCode(code, generateLayers) !== code) return false;
        found.push(code);
        return found.length >= generateLimit;
      }
      for (const row of layerValues) {
        buffer.push(row);
        if (await dfs(depth + 1)) { buffer.pop(); return true; }
        buffer.pop();
        if (visited > 0 && visited % 25000 === 0) await new Promise((resolve) => setTimeout(resolve, 0));
      }
      return false;
    };
    try {
      await dfs(0);
      const output = found.join("\n");
      setText(output);
      setRows(found.map((code, index) => ({ index, raw: code, code, cap: generateLayers, status: "pending" })));
    } finally {
      setRunning(false);
    }
  };

  const stop = () => {
    setCancelled(true);
    cancelRef.current = true;
    for (const client of clientsRef.current) client.terminate();
    clientsRef.current = [];
    setRows((current) => current.map((row) => row.status === "running" || row.status === "pending" ? { ...row, status: "cancelled" } : row));
    setRunning(false);
  };

  const run = async () => {
    if (!rows.length || running) return;
    setCancelled(false);
    cancelRef.current = false;
    setRunning(true);
    setRows((current) => current.map((row) => ({ ...row, status: "pending", result: undefined, error: undefined })));
    const clients = Array.from({ length: workers }, () => new SolverClient());
    clientsRef.current = clients;
    let cursor = 0;
    const runWorker = async (client: SolverClient) => {
      while (true) {
        const index = cursor++;
        if (index >= rows.length || cancelRef.current) break;
        const row = rows[index];
        setRows((current) => { const next = [...current]; next[index] = { ...next[index], status: "running" }; return next; });
        try {
          const job = client.analyze(row.code, row.cap, mode);
          const result = await job.promise;
          setRows((current) => { const next = [...current]; next[index] = { ...next[index], cap: result.cap, status: "done", result }; return next; });
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          setRows((current) => { const next = [...current]; next[index] = { ...next[index], status: message.includes("CANCEL") ? "cancelled" : "error", error: message }; return next; });
        }
      }
    };
    await Promise.all(clients.map(runWorker));
    for (const client of clients) client.terminate();
    clientsRef.current = [];
    setRunning(false);
  };

  const exportCsv = () => {
    const header = ["index", "raw", "normalized", "cap", "status", "verdict", "shapeType", "route", "reason", "elapsedMs"];
    const body = rows.map((row) => [row.index + 1, row.raw, row.code, row.cap, row.status, row.result?.verdict, row.result?.shapeType, row.result?.route, row.result?.reason, row.result?.timing.totalMs].map(csvEscape).join(","));
    downloadBlob(new Blob([[header.join(","), ...body].join("\n")], { type: "text/csv;charset=utf-8" }), "shapez2-batch.csv");
  };

  const exportZip = async () => {
    const zip = new JSZip();
    zip.file("results.json", JSON.stringify(rows, null, 2));
    zip.file("input.txt", text);
    const csv = ["index,raw,normalized,cap,status,verdict,shapeType,route,reason,elapsedMs", ...rows.map((row) => [row.index + 1, row.raw, row.code, row.cap, row.status, row.result?.verdict, row.result?.shapeType, row.result?.route, row.result?.reason, row.result?.timing.totalMs].map(csvEscape).join(","))].join("\n");
    zip.file("results.csv", csv);
    downloadBlob(await zip.generateAsync({ type: "blob", compression: "DEFLATE" }), "shapez2-batch.zip");
  };

  const readFile = async (file: File) => {
    setText(await file.text());
    setRows([]);
  };

  return <div className="grid h-full min-h-0 gap-3 overflow-y-auto p-3 xl:grid-cols-[minmax(330px,.65fr)_minmax(620px,1.35fr)]">
    <Panel onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; }} onDrop={(event) => { event.preventDefault(); const file = event.dataTransfer.files?.[0]; if (file) void readFile(file); }}>
      <SectionTitle icon={<FileText size={15} />} title="일괄 분석 / 정규식 검색" action={<Button size="sm" variant="outline" onClick={() => fileRef.current?.click()}><Upload size={14} />파일</Button>} />
      <div className="space-y-4 p-4">
        <input ref={fileRef} type="file" accept=".txt,.csv,.json,.jsonl" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void readFile(file); }} />
        <label className="block text-xs font-semibold">도형 목록 / 설명문 속 {'{도형}'} 지원</label>
        <textarea value={text} onChange={(event) => setText(event.target.value)} className="h-64 w-full resize-y rounded-md border border-[var(--border)] bg-[var(--surface-0)] p-3 font-mono text-xs leading-5 outline-none focus:border-[var(--accent)]" />
        <p className="text-[10px] text-[var(--muted)]">TXT·CSV·JSON 파일을 이 패널에 놓아도 불러옵니다. 중복 코드는 자동 제거됩니다.</p>
        {parseError ? <p className="rounded-md bg-rose-500/10 px-3 py-2 text-[10px] text-rose-600">정규식 오류: {parseError}</p> : null}
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs"><span className="mb-1 block text-[var(--muted)]">정규식 필터</span><div className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3"><Filter size={14} /><input value={regex} onChange={(event) => setRegex(event.target.value)} className="h-9 min-w-0 flex-1 bg-transparent outline-none" placeholder="예: P|cS-S" /></div></label>
          <label className="text-xs"><span className="mb-1 block text-[var(--muted)]">작업자 수</span><input type="number" min={1} max={8} value={workers} onChange={(event) => setWorkers(Math.max(1, Math.min(8, Number(event.target.value) || 1)))} className="h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 outline-none" /></label>
        </div>
        <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
          <div className="mb-2 text-xs font-semibold">Corner 규칙 통과 후보 생성기</div>
          <div className="grid grid-cols-3 gap-2">
            <label className="text-[10px] text-[var(--muted)]">층수<input type="number" min={1} max={7} value={generateLayers} onChange={(event) => setGenerateLayers(Math.max(1, Math.min(7, Number(event.target.value) || 1)))} className="mt-1 h-9 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-0)] px-2 text-xs text-[var(--text)] outline-none" /></label>
            <label className="text-[10px] text-[var(--muted)]">최대 개수<input type="number" min={1} max={5000} value={generateLimit} onChange={(event) => setGenerateLimit(Math.max(1, Math.min(5000, Number(event.target.value) || 1)))} className="mt-1 h-9 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-0)] px-2 text-xs text-[var(--text)] outline-none" /></label>
            <label className="flex items-end gap-2 pb-2 text-[10px] text-[var(--muted)]"><input type="checkbox" checked={excludeSymmetry} onChange={(event) => setExcludeSymmetry(event.target.checked)} />대칭 제외</label>
          </div>
          <Button size="sm" variant="outline" className="mt-2 w-full" disabled={running} onClick={() => void generateCornerCandidates()}>후보 생성</Button>
          <p className="mt-2 text-[10px] leading-4 text-[var(--muted)]">완전 제작 가능 집합 열거가 아니라 Corner 필요조건을 만족하는 구조 후보를 지정 개수까지 생성합니다.</p>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {(["fast", "type", "proof"] as AnalyzeMode[]).map((value) => <Button key={value} size="sm" variant={mode === value ? "primary" : "outline"} onClick={() => setMode(value)}>{value === "fast" ? "빠른 판정" : value === "type" ? "타입 분석" : "제작 과정"}</Button>)}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" onClick={parse}><RotateCcw size={15} />목록 추출</Button>
          {running ? <Button variant="danger" onClick={stop}><Square size={14} />중단</Button> : <Button variant="primary" disabled={!rows.length} onClick={() => void run()}><Play size={14} />전건 실행</Button>}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Metric label="추출" value={summary.total} />
          <Metric label="완료" value={summary.done} />
          <Metric label="오류" value={summary.error} />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Metric label="가능" value={summary.possible} />
          <Metric label="불가능" value={summary.impossible} />
          <Metric label="미완료" value={summary.unknown} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button size="sm" variant="outline" disabled={!rows.length} onClick={exportCsv}><Download size={14} />CSV</Button>
          <Button size="sm" variant="outline" disabled={!rows.length} onClick={() => void exportZip()}><Download size={14} />ZIP</Button>
        </div>
      </div>
    </Panel>
    <Panel className="min-h-[560px]">
      <SectionTitle icon={<FileText size={15} />} title={`결과 ${summary.done}/${summary.total}`} action={<><select aria-label="결과 필터" value={resultFilter} onChange={(event) => { setResultFilter(event.target.value as typeof resultFilter); setPage(0); }} className="h-7 rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-2 text-[10px]"><option value="all">전체</option><option value="possible">가능</option><option value="impossible">불가능</option><option value="unknown">미완료</option><option value="error">오류</option></select>{running ? <Badge tone="accent">실행 중</Badge> : <Badge>{rows.length ? "READY" : "EMPTY"}</Badge>}</>} />
      {rows.length ? <div className="h-1 bg-[var(--surface-3)]"><div className="h-full bg-[var(--accent)] transition-[width]" style={{ width: `${(summary.done + summary.error) / Math.max(1, summary.total) * 100}%` }} /></div> : null}
      <div className="max-h-[calc(100vh-210px)] overflow-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 bg-[var(--surface-1)] text-[10px] uppercase tracking-[.12em] text-[var(--muted)]">
            <tr><th className="p-3">#</th><th className="p-3">도형</th><th className="p-3">상태</th><th className="p-3">유형 / 경로</th><th className="p-3 text-right">시간</th></tr>
          </thead>
          <tbody>{visibleRows.map((row) => <tr key={`${row.index}-${row.code}`} className="border-t border-[var(--border)] hover:bg-[var(--surface-2)]">
            <td className="p-3 text-[var(--muted)]">{row.index + 1}</td>
            <td className="p-3"><button type="button" onClick={() => onUseTarget(row.code)} className="flex items-center gap-3 text-left"><ShapeRenderer code={row.raw} compact className="w-20" /><div className="max-w-[260px]"><code className="block truncate">{row.code}</code><span className="text-[10px] text-[var(--muted)]">최대 {row.cap}층</span></div></button></td>
            <td className="p-3">{row.status === "error" ? <Badge tone="negative">오류</Badge> : row.status === "cancelled" ? <Badge tone="unknown">취소됨</Badge> : row.status === "running" ? <Badge tone="accent">실행 중</Badge> : row.status === "done" ? <Badge tone={row.result?.verdict === "POSSIBLE" ? "positive" : row.result?.verdict === "IMPOSSIBLE" ? "negative" : "unknown"}>{row.result?.verdict}</Badge> : <Badge>대기</Badge>}</td>
            <td className="p-3"><div className="font-semibold">{row.result?.shapeType ?? "—"}</div><div className="text-[10px] text-[var(--muted)]">{row.result?.route ?? row.error ?? "대기 중"}</div></td>
            <td className="p-3 text-right font-mono">{row.result ? `${row.result.timing.totalMs.toFixed(1)} ms` : "—"}</td>
          </tr>)}</tbody>
        </table>
        {!rows.length ? <div className="grid min-h-[500px] place-items-center text-center text-sm text-[var(--muted)]"><div><XCircle className="mx-auto mb-3" size={34} /><p>왼쪽에서 목록을 추출하세요.</p></div></div> : null}
      </div>
      {filteredRows.length > pageSize ? <div className="flex h-10 items-center justify-end gap-2 border-t border-[var(--border)] px-3 text-[10px]"><Button size="xs" variant="ghost" disabled={page <= 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>이전</Button><span>{page + 1} / {pageCount}</span><Button size="xs" variant="ghost" disabled={page >= pageCount - 1} onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}>다음</Button></div> : null}
    </Panel>
  </div>;
}
