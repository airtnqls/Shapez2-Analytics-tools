"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Play, Plus, RotateCcw, Save, Trash2, Upload } from "lucide-react";
import { runZipOperation } from "@/lib/zip-api";
import { solverClient } from "@/lib/solver-client";
import type { OperationName } from "@/lib/types";
import { migrateZipTests, type ZipTestCase } from "@/lib/zip-test-migration";
import { Badge, Button } from "./ui";

interface TestRunResult {
  status: "passed" | "failed";
  actualA: string;
  actualB: string;
  error?: string;
}

const ZIP_TEST_STORAGE_KEY = "shapez2-zip-tests-v2";
const LEGACY_TEST_STORAGE_KEY = "shapez2-legacy-tests";
const ZIP_TEST_SOURCE = "/zip-tests.json";

function downloadJson(value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "shapez2-zip-tests-v2.json";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function LegacyTestEditor({ onLog }: { onLog: (message: string) => void }) {
  const [tests, setTests] = useState<ZipTestCase[]>([]);
  const [selected, setSelected] = useState(0);
  const [running, setRunning] = useState(false);
  const [summary, setSummary] = useState<{ passed: number; failed: number } | null>(null);
  const [results, setResults] = useState<Record<string, TestRunResult>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const savedV2 = localStorage.getItem(ZIP_TEST_STORAGE_KEY);
    if (savedV2) {
      try { setTests(migrateZipTests(JSON.parse(savedV2))); return; } catch {}
    }
    const legacySaved = localStorage.getItem(LEGACY_TEST_STORAGE_KEY);
    if (legacySaved) {
      try {
        const migrated = migrateZipTests(JSON.parse(legacySaved));
        setTests(migrated);
        localStorage.setItem(ZIP_TEST_STORAGE_KEY, JSON.stringify(migrated));
        onLog(`구버전 사용자 테스트 ${migrated.length}개를 ZIP v2로 복사했습니다. 원본은 보존했습니다.`);
        return;
      } catch (error) {
        onLog(`구버전 사용자 테스트 마이그레이션 실패, 원본 보존: ${String(error)}`);
      }
    }
    const controller = new AbortController();
    fetch(ZIP_TEST_SOURCE, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error(`${response.status} ${response.statusText}`); return response.json(); })
      .then((value: unknown) => setTests(migrateZipTests(value)))
      .catch((error: unknown) => { if (!(error instanceof DOMException && error.name === "AbortError")) onLog(`테스트 불러오기 실패: ${String(error)}`); });
    return () => controller.abort();
  }, [onLog]);

  const current = tests[selected];
  const categories = useMemo(() => [...new Set(tests.map((test) => test.category))], [tests]);
  const update = (patch: Partial<ZipTestCase>) => {
    setTests((items) => items.map((item, index) => index === selected ? { ...item, ...patch } : item));
    if (current) setResults((items) => Object.fromEntries(Object.entries(items).filter(([id]) => id !== current.id)));
    setSummary(null);
  };

  const clearRunState = () => {
    setSummary(null);
    setResults({});
  };

  const save = () => {
    localStorage.setItem(ZIP_TEST_STORAGE_KEY, JSON.stringify(tests));
    onLog(`${tests.length}개 테스트를 브라우저에 저장했습니다.`);
  };

  const reset = async () => {
    const value = await fetch(ZIP_TEST_SOURCE, { cache: "no-store" }).then((response) => { if (!response.ok) throw new Error(`${response.status} ${response.statusText}`); return response.json(); });
    setTests(migrateZipTests(value));
    setSelected(0);
    clearRunState();
    localStorage.removeItem(ZIP_TEST_STORAGE_KEY);
  };

  const runAll = async () => {
    if (running) return;
    setRunning(true);
    setResults({});
    setSummary(null);
    let passed = 0;
    let failed = 0;
    for (const test of tests) {
      try {
        const operation = test.operation;
        const cap = Math.max(5, test.input_a.split(":").length, (test.input_b ?? "").split(":").length);
        if (operation === "classifier") {
          const classification = await solverClient.analyze(test.input_a, cap, "type").promise;
          const expected = test.expected_a ?? "";
          const actualA = classification.shapeType;
          const ok = [classification.shapeType, classification.verdict, classification.reason].some((value) => value === expected || value.includes(expected));
          if (ok) passed += 1; else failed += 1;
          setResults((items) => ({ ...items, [test.id]: { status: ok ? "passed" : "failed", actualA, actualB: "" } }));
          continue;
        }
        const color = typeof test.params === "string" ? test.params : test.params?.color;
        const result = await runZipOperation({ operation: operation as OperationName, inputA: test.input_a, inputB: test.input_b, cap, paintColor: color || "u", crystalColor: color || "u" });
        const actualA = result.outputs[0] ?? result.message;
        const actualB = result.outputs[1] ?? "";
        const ok = actualA === (test.expected_a ?? "") && actualB === (test.expected_b ?? "");
        if (ok) passed += 1; else failed += 1;
        setResults((items) => ({ ...items, [test.id]: { status: ok ? "passed" : "failed", actualA, actualB } }));
      } catch (error) {
        failed += 1;
        const message = error instanceof Error ? error.message : String(error);
        setResults((items) => ({ ...items, [test.id]: { status: "failed", actualA: "", actualB: "", error: message } }));
      }
    }
    setSummary({ passed, failed });
    setRunning(false);
    onLog(`자동 테스트 완료: 통과 ${passed}, 실패 ${failed}`);
  };

  const importFile = async (file: File) => {
    const value = JSON.parse(await file.text()) as unknown;
    const migrated = migrateZipTests(value);
    setTests(migrated);
    setSelected(0);
    clearRunState();
    onLog(`${migrated.length}개 테스트를 ZIP v2 규격으로 가져왔습니다.`);
  };

  return <div className="legacy-test-editor flex h-full min-h-0 flex-col">
    <div className="legacy-group m-2 mb-0">
        <div className="legacy-group-title">ZIP v2 자동 테스트</div>
      <div className="flex flex-wrap items-center gap-2 p-2">
        <Button size="sm" variant="primary" disabled={running || !tests.length} onClick={() => void runAll()}><Play size={13} />{running ? "실행 중" : "전체 테스트 실행"}</Button>
        <Button size="sm" onClick={save}><Save size={13} />저장</Button>
        <Button size="sm" onClick={() => void reset()}><RotateCcw size={13} />기본값 복원</Button>
        <Button size="sm" onClick={() => fileRef.current?.click()}><Upload size={13} />가져오기</Button>
        <Button size="sm" onClick={() => downloadJson(tests)}><Download size={13} />내보내기</Button>
        <input ref={fileRef} type="file" accept=".json" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importFile(file); }} />
        <span className="ml-auto text-[11px] text-[var(--muted)]">총 {tests.length}개</span>
        {summary ? <><Badge tone="positive">통과 {summary.passed}</Badge><Badge tone={summary.failed ? "negative" : "positive"}>실패 {summary.failed}</Badge></> : null}
      </div>
    </div>
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(420px,1.35fr)_minmax(300px,.65fr)] gap-2 p-2">
      <div className="legacy-group min-h-0 overflow-auto">
        <div className="legacy-group-title">테스트 케이스 목록</div>
        <table className="legacy-table w-full text-[11px]"><thead><tr><th>결과</th><th>분류</th><th>테스트명</th><th>연산</th><th>입력</th><th>예상 출력</th><th>실제 출력</th></tr></thead><tbody>{tests.map((test, index) => <tr key={test.id} className={index === selected ? "selected" : ""} onClick={() => setSelected(index)}><td>{results[test.id] ? <Badge tone={results[test.id].status === "passed" ? "positive" : "negative"}>{results[test.id].status === "passed" ? "통과" : "실패"}</Badge> : <Badge>대기</Badge>}</td><td>{test.category}</td><td>{test.name}</td><td>{test.operation}</td><td className="max-w-44 truncate font-mono">{test.input_a}</td><td className="max-w-44 truncate font-mono">{test.expected_a}</td><td className="max-w-44 truncate font-mono text-[var(--muted)]">{results[test.id]?.error ?? results[test.id]?.actualA}</td></tr>)}</tbody></table>
      </div>
      <div className="legacy-group overflow-auto">
        <div className="legacy-group-title flex items-center"><span>테스트 편집</span><span className="ml-auto flex gap-1"><Button size="xs" onClick={() => { setTests((items) => [...items, { id: `user-${crypto.randomUUID()}`, category: categories[0] ?? "사용자", name: "새 테스트", operation: "apply_physics", input_a: "SSSS", expected_a: "SSSS" }]); setSelected(tests.length); clearRunState(); }}><Plus size={12} /></Button><Button size="xs" variant="danger" disabled={!current} onClick={() => { setTests((items) => items.filter((_, index) => index !== selected)); setSelected(Math.max(0, selected - 1)); clearRunState(); }}><Trash2 size={12} /></Button></span></div>
        {current ? <div className="grid gap-2 p-3 text-[11px]">
          <label>카테고리<input value={current.category} onChange={(event) => update({ category: event.target.value })} /></label>
          <label>테스트명<input value={current.name} onChange={(event) => update({ name: event.target.value })} /></label>
          <label>연산<select value={current.operation} onChange={(event) => update({ operation: event.target.value })}>{["apply_physics","destroy_half","stack","paint","crystal_generator","push_pin","rotate_cw","rotate_ccw","rotate_180","swap","classifier","half_cutter","simple_cutter","quad_cutter","mirror"].map((operation) => <option key={operation}>{operation}</option>)}</select></label>
          <label>입력 A<input className="font-mono" value={current.input_a} onChange={(event) => update({ input_a: event.target.value })} /></label>
          <label>입력 B<input className="font-mono" value={current.input_b ?? ""} onChange={(event) => update({ input_b: event.target.value })} /></label>
          <label>예상 출력 A<input className="font-mono" value={current.expected_a ?? ""} onChange={(event) => update({ expected_a: event.target.value })} /></label>
          <label>예상 출력 B<input className="font-mono" value={current.expected_b ?? ""} onChange={(event) => update({ expected_b: event.target.value })} /></label>
          <label>색상 매개변수<input value={typeof current.params === "string" ? current.params : current.params?.color ?? ""} onChange={(event) => update({ params: event.target.value ? { color: event.target.value } : undefined })} /></label>
          {results[current.id]?.status === "failed" ? <div className="rounded-md border border-rose-300 bg-rose-50 p-2 text-[10px] text-rose-800"><b>실패 상세</b><div className="mt-1 font-mono">예상 A: {current.expected_a ?? ""}</div><div className="font-mono">실제 A: {results[current.id].actualA}</div><div className="font-mono">예상 B: {current.expected_b ?? ""}</div><div className="font-mono">실제 B: {results[current.id].actualB}</div>{results[current.id].error ? <div className="mt-1">오류: {results[current.id].error}</div> : null}</div> : null}
        </div> : <div className="p-4 text-[var(--muted)]">테스트를 선택하세요.</div>}
      </div>
    </div>
  </div>;
}
