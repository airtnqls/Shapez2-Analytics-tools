"use client";

import type { AnalysisResult, ProofNodeData } from "@/lib/types";
import { KO_MODE, KO_SHAPE_TYPE, KO_VERDICT, koOperation, koRoute } from "@/lib/ko";
import { ShapeRenderer } from "./shape-renderer";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="grid grid-cols-[110px_minmax(0,1fr)] border-b border-[var(--border)] py-1.5 text-[11px]"><span className="text-[var(--muted)]">{label}</span><span className="min-w-0 break-words text-right font-medium">{value}</span></div>;
}

export function AnalysisPanel({ result, selectedNode }: { result: AnalysisResult | null; selectedNode?: ProofNodeData | null }) {
  if (selectedNode) return <div className="h-full overflow-auto p-3">
    <h2 className="mb-3 text-sm font-semibold">선택 항목</h2>
    {selectedNode.code != null ? <div className="mb-3 flex justify-center"><ShapeRenderer code={selectedNode.code} compact showCode /></div> : null}
    <Row label="종류" value={selectedNode.kind === "operation" ? "연산" : selectedNode.kind === "shape" ? "도형" : "증명 항목"} />
    <Row label="이름" value={selectedNode.operation ? koOperation(selectedNode.operation) : selectedNode.label} />
    {selectedNode.status ? <Row label="상태" value={selectedNode.status === "positive" ? "검증됨" : selectedNode.status === "negative" ? "거부됨" : selectedNode.status === "ghost" ? "미사용 출력" : "미완료"} /> : null}
    {selectedNode.metadata && Object.entries(selectedNode.metadata).map(([key, value]) => <Row key={key} label={key} value={Array.isArray(value) ? value.join(", ") : String(value)} />)}
  </div>;

  if (!result) return <div className="grid h-full place-items-center p-6 text-center text-xs text-[var(--muted)]">분석을 실행하면 상세 정보가 표시됩니다.</div>;

  return <div className="h-full overflow-auto p-3">
    <h2 className="text-sm font-semibold">분석 결과</h2>
    <p className="mt-1 text-[11px] leading-5 text-[var(--muted)]">{result.reason}</p>
    <div className="mt-3 border-t border-[var(--border)]">
      <Row label="실행 모드" value={KO_MODE[result.mode]} />
      <Row label="판정" value={KO_VERDICT[result.verdict]} />
      <Row label="도형 유형" value={KO_SHAPE_TYPE[result.shapeType]} />
      <Row label="판정 경로" value={koRoute(result.route)} />
      <Row label="실행 시간" value={`${result.timing.totalMs.toFixed(2)} ms`} />
      <Row label="높이" value={`${result.facts.height}층`} />
    </div>

    <details className="mt-3 border-t border-[var(--border)] pt-2">
      <summary className="cursor-pointer text-[11px] font-semibold">검사 항목</summary>
      <div className="mt-1">
        <Row label="물리 안정" value={result.facts.stable ? "통과" : "실패"} />
        <Row label="기본 입력" value={result.facts.basic ? "예" : "아니오"} />
        <Row label="Half" value={result.facts.half ? "예" : "아니오"} />
        <Row label="스왑 가능" value={result.facts.swappable ? "예" : "아니오"} />
        <Row label="쌓기 가능" value={result.facts.stackable ? "예" : "아니오"} />
        <Row label="Claw" value={result.facts.claw ? "예" : "아니오"} />
        <Row label="Claw Hybrid" value={result.facts.hybrid ? "예" : "아니오"} />
      </div>
    </details>

    {result.explanation.length ? <details className="mt-3 border-t border-[var(--border)] pt-2">
      <summary className="cursor-pointer text-[11px] font-semibold">판정 근거</summary>
      <ol className="mt-2 space-y-1 pl-4 text-[10px] leading-5 text-[var(--muted)]">{result.explanation.map((text, i) => <li key={i} className="list-decimal">{text}</li>)}</ol>
    </details> : null}

    <details className="mt-3 border-t border-[var(--border)] pt-2">
      <summary className="cursor-pointer text-[11px] font-semibold">성능 및 진단</summary>
      <div className="mt-1">
        <Row label="데이터 로드" value={`${result.timing.tableLoadMs.toFixed(2)} ms`} />
        <Row label="판정/분석" value={`${result.timing.familyMs.toFixed(2)} ms`} />
        <Row label="공정 생성" value={`${result.timing.proofMs.toFixed(2)} ms`} />
        <Row label="방문 상태" value={result.diagnostics.statesVisited.toLocaleString()} />
        <Row label="검사 후보" value={result.diagnostics.candidatesChecked.toLocaleString()} />
        <Row label="사용 데이터" value={result.diagnostics.tablesLoaded.join(", ") || "없음"} />
      </div>
    </details>
  </div>;
}
