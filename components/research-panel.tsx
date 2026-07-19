"use client";

import { useMemo } from "react";
import { Braces, CheckCircle2, Database, FlaskConical, Gauge, Sigma } from "lucide-react";
import type { AnalysisResult, ProgressMessage } from "@/lib/types";
import { Badge, Metric, Panel, SectionTitle } from "./ui";

export function ResearchPanel({ result, progress, logs }: { result: AnalysisResult | null; progress: ProgressMessage | null; logs: string[] }) {
  const coverage = useMemo(() => [
    ["구조 parser / 색상 단순화", "완료"],
    ["정방향 physics", "완료"],
    ["Corner / Half", "완료"],
    ["Swappable", "완료"],
    ["StackClosure(Swappable)", "완료"],
    ["Claw 40,171", "인증 표"],
    ["Hybrid 367", "인증 표"],
    ["PP chain 종료성 σ≤4L", "증명됨"],
    ["브라우저 Rank0 Pin Push frontier", "완료"],
    ["PP-essential overflow 종단 정리", "완료"],
    ["일반 PP 음성 verifier", "완료"],
  ] as const, []);

  return <div className="h-full overflow-y-auto p-3">
    <div className="grid gap-3 xl:grid-cols-[1fr_.9fr]">
      <Panel>
        <SectionTitle icon={<FlaskConical size={15} />} title="연구자 진단" action={<Badge tone={result?.facts.coverage === "complete" ? "positive" : "unknown"}>{result?.facts.coverage === "complete" ? "완료" : result?.facts.coverage === "partial" ? "부분" : "대기"}</Badge>} />
        <div className="grid grid-cols-2 gap-2 p-4 lg:grid-cols-4">
          <Metric label="백엔드" value={<span className="text-sm">{result?.diagnostics.backend ?? "브라우저 코어"}</span>} />
          <Metric label="상태" value={result?.diagnostics.statesVisited.toLocaleString() ?? 0} />
          <Metric label="후보" value={result?.diagnostics.candidatesChecked.toLocaleString() ?? 0} />
          <Metric label="캐시" value={result?.diagnostics.cacheHit ? "적중" : "미적중"} />
        </div>
        <div className="px-4 pb-4">
          <div className="grid gap-2 sm:grid-cols-2">
            {coverage.map(([name, status]) => <div key={name} className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"><span>{name}</span><Badge tone="positive">{status}</Badge></div>)}
          </div>
          <div className="mt-4 rounded-md border border-emerald-500/30 bg-emerald-500/8 p-3 text-xs leading-5 text-emerald-300">
            <div className="mb-1 flex items-center gap-2 font-semibold"><CheckCircle2 size={14} />PP closure 완료</div>
            Bottom Pin Receipt Rank로 상위 receipt chain을 선형 압축하고, Rank0 frontier가 Swappable/Stackable predecessor를 복원합니다. 모든 경로 소진 시 완전 음성 certificate를 반환합니다.
          </div>
        </div>
      </Panel>
      <Panel>
        <SectionTitle icon={<Sigma size={15} />} title="PP Receipt Rank" />
        <div className="space-y-3 p-4">
          <div className="grid grid-cols-2 gap-2">
            <Metric label="σ(target)" value={result?.facts.receiptRank ?? 0} detail={result ? `[${result.facts.receiptProfile.join(", ")}]` : "bottom P runs"} />
            <Metric label="PP chain ≤" value={result?.facts.ppChainUpperBound ?? 0} detail="부모에서 엄격히 감소" />
            <Metric label="정방향 batch ≤" value={result?.facts.ppBatchUpperBound ?? 0} detail="4L − 1" />
            <Metric label="종료성" value={<span className="text-sm">{result?.facts.ppTerminationProof ?? "증명됨"}</span>} />
          </div>
          <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3 text-xs leading-5 text-[var(--muted)]">
            회전·대칭은 σ를 보존하고, Stack은 σ를 감소시키지 않으며, 비퇴화 Pin Push는 σ를 최소 1 증가시킵니다. 따라서 역방향 PP base chain은 자연수 σ에서 엄격히 감소하여 최대 4L단계에 종료합니다.
          </div>
          <div className="rounded-md border border-emerald-500/30 bg-emerald-500/8 p-3 text-xs text-emerald-300">PP 정규형 closure와 음성 verifier가 활성화되어 있습니다.</div>
        </div>
      </Panel>
    </div>
    <div className="mt-3 grid gap-3 xl:grid-cols-[.9fr_1.1fr]">
      <Panel>
        <SectionTitle icon={<Gauge size={15} />} title="실행 텔레메트리" />
        <div className="space-y-3 p-4">
          <div className="grid grid-cols-2 gap-2">
            <Metric label="전체" value={`${(result?.timing.totalMs ?? progress?.elapsedMs ?? 0).toFixed(1)} ms`} />
            <Metric label="표 로드" value={`${(result?.timing.tableLoadMs ?? 0).toFixed(1)} ms`} />
            <Metric label="계열 판정" value={`${(result?.timing.familyMs ?? 0).toFixed(1)} ms`} />
            <Metric label="제작 과정" value={`${(result?.timing.proofMs ?? 0).toFixed(1)} ms`} />
          </div>
          {progress ? <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
            <div className="flex items-center justify-between text-xs"><span className="font-semibold">{progress.phase}</span><span className="text-[var(--muted)]">{progress.current.toLocaleString()} / {progress.total.toLocaleString()}</span></div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-4)]"><div className="h-full rounded-full bg-[var(--accent)] transition-all" style={{ width: `${progress.total ? Math.min(100, progress.current / progress.total * 100) : 0}%` }} /></div>
            <div className="mt-2 text-xs text-[var(--muted)]">{progress.message}</div>
          </div> : null}
          <div className="rounded-md border border-[var(--border)] bg-[var(--surface-0)] p-3 text-xs">
            <div className="mb-2 flex items-center gap-2 font-semibold"><Database size={14} />불러온 데이터</div>
            {(result?.diagnostics.tablesLoaded ?? ["known-samples-132", "claw-40171", "hybrid-367"]).map((item) => <div key={item} className="flex items-center gap-2 py-1 text-[var(--muted)]"><CheckCircle2 size={13} className="text-emerald-400" />{item}</div>)}
          </div>
        </div>
      </Panel>
      <Panel>
        <SectionTitle icon={<Braces size={15} />} title="작업 로그" />
        <div className="max-h-[360px] overflow-auto bg-[#050a13] p-4 font-mono text-[11px] leading-5 text-slate-300">
          {logs.length ? logs.map((line, index) => <div key={`${index}-${line}`}><span className="mr-3 text-slate-600">{String(index + 1).padStart(3, "0")}</span>{line}</div>) : <div className="text-slate-600">아직 작업 이벤트가 없습니다.</div>}
        </div>
      </Panel>
    </div>
  </div>;
}
