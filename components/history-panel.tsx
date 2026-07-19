"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock3, Heart, History, Play, Search, Star, Trash2 } from "lucide-react";
import { db } from "@/lib/db";
import type { HistoryRecord } from "@/lib/types";
import { Badge, Button, IconButton, SectionTitle } from "./ui";
import { ShapeRenderer } from "./shape-renderer";

const examples = [
  { name: "클로", code: "-PPP:SS-P:---P:c--P:cS-S", cap: 5 },
  { name: "클로 변형", code: "PPPP:-PSS:-P--:-ScS", cap: 5 },
  { name: "스왑 가능형", code: "PPPP:cSSS:S-S-:SScS", cap: 5 },
  { name: "하프", code: "cS--:SS--:-S--:cS--", cap: 5 },
  { name: "어려운 불가능 도형", code: "c---:cS--:SSS-:S-SS:-SS-:--SS:cSS-:c-SS:cSS-", cap: 9 },
];

export function HistoryPanel({ onUse, embedded = false }: { onUse: (code: string, cap: number, proof?: boolean) => void; embedded?: boolean }) {
  const [items, setItems] = useState<HistoryRecord[]>([]);
  const [query, setQuery] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);

  const refresh = useCallback(async () => {
    const rows = await db.history.orderBy("createdAt").reverse().limit(100).toArray();
    setItems(rows);
  }, []);

  useEffect(() => {
    void refresh();
    const listener = () => void refresh();
    window.addEventListener("tmam-history", listener);
    return () => window.removeEventListener("tmam-history", listener);
  }, [refresh]);

  const toggleFavorite = async (record: HistoryRecord) => {
    if (!record.id) return;
    await db.history.update(record.id, { favorite: !record.favorite });
    await refresh();
  };

  const remove = async (id?: number) => {
    if (!id) return;
    await db.history.delete(id);
    await refresh();
  };

  const filtered = items.filter((item) => {
    if (favoritesOnly && !item.favorite) return false;
    const q = query.trim().toLowerCase();
    return !q || `${item.code} ${item.normalizedCode} ${item.shapeType} ${item.route} ${item.note ?? ""}`.toLowerCase().includes(q);
  });

  return <div className="flex h-full min-h-0 flex-col">
    {!embedded ? <SectionTitle icon={<History size={14} />} title="분석 기록" action={<IconButton label="즐겨찾기만" onClick={() => setFavoritesOnly((value) => !value)}>{favoritesOnly ? <Star size={14} fill="currentColor" /> : <Star size={14} />}</IconButton>} /> : null}
    <div className="flex h-10 shrink-0 items-center gap-1.5 border-b border-[var(--border)] px-2">
      <div className="flex min-w-0 flex-1 items-center border border-[var(--border-strong)] bg-[var(--surface-0)] px-2"><Search size={13} className="text-[var(--muted)]" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="코드·유형·경로 검색" className="h-7 min-w-0 flex-1 bg-transparent px-2 text-[11px] outline-none" /></div>
      <IconButton label="즐겨찾기만" onClick={() => setFavoritesOnly((value) => !value)}>{favoritesOnly ? <Star size={14} fill="currentColor" /> : <Star size={14} />}</IconButton>
    </div>
    <div className="shrink-0 border-b border-[var(--border)]">
      <div className="px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[.1em] text-[var(--muted)]">예제</div>
      <div className="grid grid-cols-1 divide-y divide-[var(--border)] border-t border-[var(--border)]">
        {examples.map((example) => <button key={example.name} type="button" onClick={() => onUse(example.code, example.cap)} className="grid grid-cols-[72px_minmax(0,1fr)_36px] items-center gap-2 px-2 py-1.5 text-left hover:bg-[var(--surface-2)]">
          <span className="text-[10px] font-semibold">{example.name}</span>
          <code className="truncate text-[9px] text-[var(--muted)]">{example.code}</code>
          <span className="text-right text-[9px] text-[var(--muted)]">C{example.cap}</span>
        </button>)}
      </div>
    </div>
    <div className="min-h-0 flex-1 overflow-y-auto">
      {filtered.map((record) => <div key={record.id ?? `${record.normalizedCode}-${record.createdAt}`} className="group grid grid-cols-[68px_minmax(0,1fr)_32px] gap-2 border-b border-[var(--border)] px-2 py-2 hover:bg-[var(--surface-2)]">
        <button type="button" onClick={() => onUse(record.code, record.cap)} className="grid place-items-center"><ShapeRenderer code={record.code} tiny maxLayers={5} className="max-h-[82px] overflow-hidden" /></button>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5"><Badge tone={record.verdict === "POSSIBLE" ? "positive" : record.verdict === "IMPOSSIBLE" ? "negative" : "unknown"}>{record.shapeType}</Badge><span className="text-[9px] text-[var(--muted)]">{record.elapsedMs.toFixed(1)} ms</span></div>
          <code className="mt-1 block truncate text-[10px]">{record.normalizedCode}</code>
          <div className="mt-1 flex items-center gap-1 text-[9px] text-[var(--muted)]"><Clock3 size={10} />{new Date(record.createdAt).toLocaleString()}</div>
          <div className="mt-1.5 flex gap-1">
            <Button size="xs" variant="ghost" onClick={() => onUse(record.code, record.cap)}><Play size={11} />분석</Button>
            <Button size="xs" variant="ghost" onClick={() => onUse(record.code, record.cap, true)}>제작 과정</Button>
          </div>
        </div>
        <div className="flex flex-col items-center opacity-55 transition-opacity group-hover:opacity-100">
          <IconButton label="즐겨찾기" onClick={() => void toggleFavorite(record)}>{record.favorite ? <Heart size={13} fill="currentColor" className="text-rose-400" /> : <Heart size={13} />}</IconButton>
          <IconButton label="삭제" onClick={() => void remove(record.id)}><Trash2 size={13} /></IconButton>
        </div>
      </div>)}
      {!filtered.length ? <div className="grid min-h-48 place-items-center text-center text-xs text-[var(--muted)]"><div><History className="mx-auto mb-2 opacity-55" size={24} /><p>저장된 분석이 없습니다.</p></div></div> : null}
    </div>
  </div>;
}
