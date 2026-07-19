"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { GripVertical, Plus, Redo2, RotateCw, Trash2, Undo2 } from "lucide-react";
import type { Cell } from "@/lib/types";
import { displayLayers } from "@/lib/shape";
import { Button, IconButton } from "./ui";

 type TokenRow = [string, string, string, string];

const palette = [
  { cell: "-" as Cell, label: "빈칸" },
  { cell: "S" as Cell, label: "조각" },
  { cell: "P" as Cell, label: "핀" },
  { cell: "c" as Cell, label: "결정" },
];
const ordinaryTypes = ["C", "R", "S", "W"];
const colorOptions = [["u", "무색"], ["r", "빨강"], ["g", "초록"], ["b", "파랑"], ["c", "청록"], ["m", "자홍"], ["y", "노랑"], ["w", "흰색"], ["k", "검정"]] as const;
const colors: Record<string, string> = { r: "#e33", g: "#3d3", b: "#33e", m: "#d3d", c: "#3dd", y: "#dd3", u: "#bbb", w: "#fff", k: "#222" };

function structural(token: string): Cell {
  const type = token[0] ?? "-";
  if (type === "-") return "-";
  if (type === "P" || type === "p") return "P";
  if (type === "c") return "c";
  return "S";
}
function parseTokenRows(code: string): TokenRow[] {
  const layers = displayLayers(code).map((layer) => layer.cells.map((cell) => {
    if (cell.structural === "-") return "--";
    if (cell.structural === "P") return cell.raw.length === 2 ? cell.raw : "P-";
    if (cell.structural === "c") return cell.raw.length === 2 ? cell.raw : "cu";
    return cell.raw.length === 2 ? cell.raw : "Su";
  }) as TokenRow);
  while (layers.length && layers[layers.length - 1].every((token) => structural(token) === "-")) layers.pop();
  return layers.length ? layers : [["--", "--", "--", "--"]];
}
function serialize(rows: TokenRow[], exactMode: boolean): string {
  const copy = rows.map((row) => [...row] as TokenRow);
  while (copy.length && copy[copy.length - 1].every((token) => structural(token) === "-")) copy.pop();
  if (!copy.length) return "";
  return copy.map((row) => exactMode ? row.map((token) => token.padEnd(2, "-").slice(0, 2)).join("") : row.map(structural).join("")).join(":");
}
function appearance(token: string): { background: string; color: string; text: string } {
  const cell = structural(token);
  if (cell === "-") return { background: "#303238", color: "#aaa", text: "" };
  if (cell === "P") return { background: "#999", color: "#111", text: "P" };
  if (cell === "c") {
    const paint = colors[token[1]] ?? "#fff";
    return { background: `linear-gradient(135deg,#cdd 0%,#cdd 49.5%,${paint} 50.5%,${paint} 100%)`, color: "#111", text: "c" };
  }
  return { background: colors[token[1]] ?? "#bbb", color: token[1] === "k" || token[1] === "b" ? "#fff" : "#111", text: (token[0] || "S").toUpperCase() };
}

export function ShapeEditor({ code, cap, onChange, compact = false, exactMode = false }: { code: string; cap: number; onChange: (code: string) => void; compact?: boolean; exactMode?: boolean }) {
  const parsed = useMemo(() => parseTokenRows(code), [code]);
  const [rows, setRows] = useState<TokenRow[]>(parsed);
  const [brush, setBrush] = useState<Cell>("S");
  const [ordinaryType, setOrdinaryType] = useState("S");
  const [color, setColor] = useState("u");
  const [undo, setUndo] = useState<string[]>([]);
  const [redo, setRedo] = useState<string[]>([]);
  const [painting, setPainting] = useState(false);
  const draggedRow = useRef<number | null>(null);

  useEffect(() => {
    const incoming = parseTokenRows(code);
    if (serialize(incoming, true) !== serialize(rows, true)) setRows(incoming);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);
  useEffect(() => {
    const stop = () => setPainting(false);
    window.addEventListener("pointerup", stop);
    return () => window.removeEventListener("pointerup", stop);
  }, []);

  const commit = (next: TokenRow[], remember = true) => {
    if (remember) { setUndo((history) => [...history.slice(-49), code]); setRedo([]); }
    const safe = next.length ? next : [["--", "--", "--", "--"] as TokenRow];
    setRows(safe); onChange(serialize(safe, exactMode));
  };
  const token = () => brush === "-" ? "--" : brush === "P" ? "P-" : brush === "c" ? `c${color}` : `${ordinaryType}${color}`;
  const paint = (layer: number, quadrant: number, remember = true) => {
    if (rows[layer]?.[quadrant] === token()) return;
    const next = rows.map((row) => [...row] as TokenRow); next[layer][quadrant] = token(); commit(next, remember);
  };
  const rotateLayer = (index: number) => { const next = rows.map((row) => [...row] as TokenRow); const [a, b, c, d] = next[index]; next[index] = [d, a, b, c]; commit(next); };
  const fillLayer = (index: number) => { const next = rows.map((row) => [...row] as TokenRow); next[index] = [token(), token(), token(), token()]; commit(next); };
  const undoAction = () => { const previous = undo.at(-1); if (previous == null) return; setUndo((h) => h.slice(0, -1)); setRedo((h) => [...h, code]); onChange(previous); };
  const redoAction = () => { const next = redo.at(-1); if (next == null) return; setRedo((h) => h.slice(0, -1)); setUndo((h) => [...h, code]); onChange(next); };
  const cellSize = compact ? 26 : 32;

  return <div className="flex min-h-0 flex-col">
    <div className="flex flex-wrap items-center gap-1 border-b border-[var(--border)] px-2 py-2">
      {palette.map((item) => <button key={item.cell} type="button" onClick={() => setBrush(item.cell)} className={`h-7 border px-2 text-[10px] ${brush === item.cell ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--text)]" : "border-[var(--border)] text-[var(--muted)]"}`}>{item.label}</button>)}
      <span className="mx-1 h-5 w-px bg-[var(--border)]" />
      {brush === "S" ? <select aria-label="조각 종류" value={ordinaryType} onChange={(e) => setOrdinaryType(e.target.value)} className="h-7 border border-[var(--border)] bg-[var(--surface-0)] px-1 text-[10px]">{ordinaryTypes.map((v) => <option key={v}>{v}</option>)}</select> : null}
      {brush === "S" || brush === "c" ? <select aria-label="색상" value={color} onChange={(e) => setColor(e.target.value)} className="h-7 border border-[var(--border)] bg-[var(--surface-0)] px-1 text-[10px]">{colorOptions.map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select> : null}
      <span className="ml-auto" />
      <IconButton label="실행 취소" disabled={!undo.length} onClick={undoAction}><Undo2 size={13} /></IconButton>
      <IconButton label="다시 실행" disabled={!redo.length} onClick={redoAction}><Redo2 size={13} /></IconButton>
    </div>

    <div className="min-h-0 overflow-auto p-2">
      <div className="mx-auto w-fit overflow-hidden border border-[#555] bg-[#25272c]">
        <div className="flex border-b border-[var(--shape-grid-strong)] bg-[var(--surface-2)] text-[8px] font-semibold text-[var(--muted)]" style={{ paddingLeft: 18 }}>
          {[1, 2, 3, 4].map((q) => <div key={q} className="grid place-items-center border-l border-[#777]" style={{ width: cellSize, height: 15 }}>{q}</div>)}
          <div style={{ width: 76 }} />
        </div>
        {[...rows].reverse().map((row, reverseIndex) => {
          const index = rows.length - reverseIndex - 1;
          return <div key={index} className="flex" draggable onDragStart={() => { draggedRow.current = index; }} onDragOver={(e) => e.preventDefault()} onDrop={() => {
            const source = draggedRow.current; if (source == null || source === index) return;
            const next = rows.map((r) => [...r] as TokenRow); const [moved] = next.splice(source, 1); next.splice(index, 0, moved); draggedRow.current = null; commit(next);
          }}>
            <button type="button" title={`L${index + 1} 끌어서 이동 / 클릭해서 전체 채우기`} onClick={() => fillLayer(index)} className="grid cursor-grab border-r border-t border-[var(--shape-grid-strong)] bg-[var(--surface-2)] text-[var(--muted)] active:cursor-grabbing" style={{ width: 18, height: cellSize, placeItems: "center" }}><GripVertical size={9} /></button>
            {row.map((item, q) => { const a = appearance(item); return <button key={q} type="button" title={`L${index + 1} Q${q + 1}: ${item}`} onPointerDown={(e) => { e.preventDefault(); setPainting(true); paint(index, q); }} onPointerEnter={() => { if (painting) paint(index, q, false); }} onContextMenu={(e) => { e.preventDefault(); const next = rows.map((r) => [...r] as TokenRow); next[index][q] = "--"; commit(next); }} className="grid border-l border-t border-[#555] font-bold" style={{ width: cellSize, height: cellSize, placeItems: "center", background: a.background, color: a.color, fontSize: 11 }}>{a.text}</button>; })}
            <div className="flex items-center border-l border-t border-[#555] bg-[var(--surface-1)] px-1" style={{ width: 76, height: cellSize }}>
              <IconButton label="층 회전" onClick={() => rotateLayer(index)}><RotateCw size={12} /></IconButton>
              <IconButton label="층 삭제" onClick={() => commit(rows.filter((_, i) => i !== index))}><Trash2 size={12} /></IconButton>
            </div>
          </div>;
        })}
      </div>
      <div className="mx-auto mt-2 flex w-fit gap-1">
        <Button size="xs" variant="outline" disabled={rows.length >= cap} onClick={() => commit([...rows, ["--", "--", "--", "--"]])}><Plus size={12} />층 추가</Button>
        <Button size="xs" variant="ghost" onClick={() => commit([["--", "--", "--", "--"]])}>초기화</Button>
      </div>
    </div>
  </div>;
}
