"use client";

import { useMemo } from "react";
import { displayLayers, simplifyExactCode } from "@/lib/shape";
import { cn } from "@/lib/cn";

const colors: Record<string, string> = {
  r: "#e33", g: "#3d3", b: "#33e", m: "#d3d", c: "#3dd", y: "#dd3",
  u: "#bbb", w: "#fff", k: "#222", o: "#e93", p: "#e7a",
};

// Some Chromium/WebView builds strip custom DataTransfer payloads during an
// HTML5 drag. Keep a page-local fallback so shape-to-shape drops still work.
let activeDraggedShapeCode = "";

function cellAppearance(cell: ReturnType<typeof displayLayers>[number]["cells"][number], structuralOnly: boolean): { style: React.CSSProperties; text: string; dark: boolean } {
  if (cell.structural === "-") return { style: { background: "#303238" }, text: "", dark: true };
  if (cell.structural === "P") return { style: { background: "#999" }, text: "P", dark: false };
  if (cell.structural === "c") {
    const paint = structuralOnly ? "#fff" : colors[cell.color] ?? "#fff";
    return { style: { background: `linear-gradient(135deg,#cdd 0%,#cdd 49.5%,${paint} 50.5%,${paint} 100%)` }, text: "c", dark: false };
  }
  const fill = structuralOnly ? "#6b9ee8" : colors[cell.color] ?? "#bbb";
  const type = structuralOnly ? "S" : (cell.type || "S").toUpperCase();
  return { style: { background: fill }, text: type, dark: cell.color === "k" || cell.color === "b" };
}

export function ShapeRenderer({
  code,
  className,
  compact = false,
  tiny = false,
  structuralOnly = false,
  showCode = false,
  maxLayers = Number.MAX_SAFE_INTEGER,
  showQuadrants = false,
  large = false,
  dragEnabled = false,
  onCodeDrop,
}: {
  code: string;
  className?: string;
  compact?: boolean;
  tiny?: boolean;
  structuralOnly?: boolean;
  showCode?: boolean;
  maxLayers?: number;
  showQuadrants?: boolean;
  layerGap?: number;
  large?: boolean;
  dragEnabled?: boolean;
  onCodeDrop?: (code: string) => void;
}) {
  const allLayers = useMemo(() => displayLayers(code), [code]);
  const visible = useMemo(() => allLayers.slice(Math.max(0, allLayers.length - maxLayers)), [allLayers, maxLayers]);
  const normalized = useMemo(() => simplifyExactCode(code), [code]);
  const cell = tiny ? 18 : compact ? 25 : large ? 72 : 34;
  const labelWidth = tiny ? 12 : compact ? 14 : large ? 24 : 16;

  return <div
    className={cn("shape-renderer inline-flex w-fit max-w-none shrink-0 flex-col items-center justify-center", dragEnabled && "cursor-grab active:cursor-grabbing", onCodeDrop && "rounded-md outline-offset-4", className)}
    data-shape-code={code}
    draggable={dragEnabled}
    onDragStart={(event) => {
      if (!dragEnabled) return;
      activeDraggedShapeCode = code;
      event.dataTransfer.effectAllowed = "copyMove";
      event.dataTransfer.setData("application/x-shapez2-code", code);
      event.dataTransfer.setData("text/plain", code);
    }}
    onDragOver={(event) => { if (onCodeDrop) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }}
    onDrop={(event) => {
      if (!onCodeDrop) return;
      event.preventDefault();
      const dropped = event.dataTransfer.getData("application/x-shapez2-code") || event.dataTransfer.getData("text/plain") || activeDraggedShapeCode;
      if (dropped.trim()) onCodeDrop(dropped.trim());
    }}
    onDragEnd={() => { activeDraggedShapeCode = ""; }}
  >
    <div className="w-fit overflow-visible border border-[var(--shape-outline)] bg-[var(--shape-empty)]">
      {showQuadrants ? <div className="flex border-b border-[#555] bg-[#aaa] text-center text-[8px] font-semibold text-[#222]" style={{ paddingLeft: labelWidth }}>
        {[1, 2, 3, 4].map((q) => <span key={q} className="grid place-items-center border-l border-[#777]" style={{ width: cell, height: Math.max(13, cell * .45) }}>{q}</span>)}
      </div> : null}
      {visible.length ? [...visible].reverse().map((layer, reverseIndex) => {
        const originalIndex = allLayers.length - reverseIndex;
        return <div key={originalIndex} className="flex">
          <div className="grid shrink-0 place-items-center border-r border-t border-[var(--shape-grid-strong)] bg-[var(--surface-2)] text-[7px] font-semibold text-[var(--muted)]" style={{ width: labelWidth, height: cell }}><span className="-rotate-90 whitespace-nowrap">L{originalIndex}</span></div>
          {layer.cells.map((item, q) => {
            const appearance = cellAppearance(item, structuralOnly);
            return <div
              key={q}
              title={`L${originalIndex} Q${q + 1}: ${item.raw || "--"}`}
              className="grid select-none place-items-center border-l border-t border-[#555] font-bold shadow-[inset_0_0_0_1px_rgba(255,255,255,.04)]"
              style={{ width: cell, height: cell, fontSize: Math.max(9, cell * .38), color: appearance.dark ? "#fff" : "#111", ...appearance.style }}
            >{appearance.text}</div>;
          })}
        </div>;
      }) : <div className="grid text-[10px] text-[#aaa]" style={{ width: labelWidth + cell * 4, height: cell * 2.2, placeItems: "center" }}>빈 도형</div>}
    </div>
    {allLayers.length > visible.length ? <span className="mt-1 text-[9px] text-[var(--muted)]">아래 {allLayers.length - visible.length}개 층 생략</span> : null}
    {showCode ? <code title={normalized || "----"} className="mt-1 block max-w-full truncate border border-[var(--border)] bg-[var(--surface-0)] px-1.5 py-1 text-[9px] text-[var(--muted)]">{normalized || "----"}</code> : null}
  </div>;
}
