"use client";

import { useEffect, useMemo, useState } from "react";
import { Command, Moon, PanelLeft, PanelRight, Play, Search, Settings, Sun, Workflow } from "lucide-react";
import type { AnalyzeMode } from "@/lib/types";
import type { WorkspaceTab } from "@/lib/store";

interface CommandItem {
  label: string;
  hint: string;
  icon: React.ReactNode;
  run: () => void;
}

export function CommandPalette({ open, onOpenChange, onRun, onTab, onToggleLeft, onToggleRight, onTheme }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRun: (mode: AnalyzeMode) => void;
  onTab: (tab: WorkspaceTab) => void;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onTheme: (theme: "dark" | "light" | "system") => void;
}) {
  const [query, setQuery] = useState("");
  useEffect(() => { if (open) setQuery(""); }, [open]);
  const items = useMemo<CommandItem[]>(() => [
    { label: "빠른 가능 여부", hint: "Ctrl + Enter", icon: <Play size={15} />, run: () => onRun("fast") },
    { label: "상세 타입 분석", hint: "Ctrl + Shift + Enter", icon: <Search size={15} />, run: () => onRun("type") },
    { label: "모든 제작 과정", hint: "Alt + Enter", icon: <Workflow size={15} />, run: () => onRun("proof") },
    { label: "제작 과정 탭", hint: "1", icon: <Workflow size={15} />, run: () => onTab("proof") },
    { label: "정방향 연산 실험실", hint: "2", icon: <Command size={15} />, run: () => onTab("lab") },
    { label: "Batch 분석", hint: "3", icon: <Command size={15} />, run: () => onTab("batch") },
    { label: "비교 모드", hint: "4", icon: <Command size={15} />, run: () => onTab("compare") },
    { label: "연구자 진단", hint: "5", icon: <Settings size={15} />, run: () => onTab("research") },
    { label: "왼쪽 패널 토글", hint: "[", icon: <PanelLeft size={15} />, run: onToggleLeft },
    { label: "오른쪽 패널 토글", hint: "]", icon: <PanelRight size={15} />, run: onToggleRight },
    { label: "다크 테마", hint: "", icon: <Moon size={15} />, run: () => onTheme("dark") },
    { label: "라이트 테마", hint: "", icon: <Sun size={15} />, run: () => onTheme("light") },
  ], [onRun, onTab, onTheme, onToggleLeft, onToggleRight]);
  if (!open) return null;
  const filtered = items.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()));
  return <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/55 px-4 pt-[12vh] backdrop-blur-sm" onMouseDown={(event) => { if (event.currentTarget === event.target) onOpenChange(false); }}>
    <div className="w-full max-w-xl overflow-hidden rounded-md border border-[var(--border)] bg-[var(--surface-1)] shadow-2xl">
      <div className="flex items-center gap-3 border-b border-[var(--border)] px-4"><Search size={18} className="text-[var(--muted)]" /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") onOpenChange(false); if (event.key === "Enter" && filtered[0]) { filtered[0].run(); onOpenChange(false); } }} placeholder="명령 검색…" className="h-14 min-w-0 flex-1 bg-transparent text-sm outline-none" /><kbd className="rounded-md border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--muted)]">ESC</kbd></div>
      <div className="max-h-[420px] overflow-y-auto p-2">{filtered.map((item) => <button type="button" key={item.label} onClick={() => { item.run(); onOpenChange(false); }} className="flex w-full items-center gap-3 rounded-md px-3 py-3 text-left text-sm hover:bg-[var(--surface-2)]"><span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--surface-3)] text-[var(--accent)]">{item.icon}</span><span className="flex-1 font-medium">{item.label}</span>{item.hint ? <kbd className="text-[10px] text-[var(--muted)]">{item.hint}</kbd> : null}</button>)}</div>
    </div>
  </div>;
}
