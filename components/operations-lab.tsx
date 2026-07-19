"use client";

import { useMemo, useState } from "react";
import { ArrowDownToLine, Beaker, Combine, Copy, GitBranch, Layers3, RotateCw, Sparkles, Split, WandSparkles } from "lucide-react";
import { applyGravity, cutShape, generateCrystals, pushPin, stackShapes, swapShapes } from "@/lib/physics";
import { mirrorRows, parseCode, rotateRows, rowsToCode } from "@/lib/shape";
import { ShapeEditor } from "./shape-editor";
import { ShapeRenderer } from "./shape-renderer";
import { Button, IconButton, Panel, SectionTitle } from "./ui";

interface OutputShape {
  label: string;
  code: string;
  operation: string;
}

export function OperationsLab({ cap, onUseTarget }: { cap: number; onUseTarget: (code: string) => void }) {
  const [inputs, setInputs] = useState(["SS--:S---", "--SS:---S"]);
  const [outputs, setOutputs] = useState<OutputShape[]>([]);
  const letters = "ABCDEF";

  const rows = useMemo(() => inputs.map((code) => parseCode(code, cap)), [inputs, cap]);
  const setInput = (index: number, code: string) => setInputs((current) => current.map((value, i) => i === index ? code : value));
  const addInput = () => setInputs((current) => current.length >= 6 ? current : [...current, "S---"]);
  const removeInput = (index: number) => setInputs((current) => current.length <= 2 ? current : current.filter((_, i) => i !== index));

  const emit = (operation: string, values: Array<[string, ReturnType<typeof parseCode>]>) => {
    setOutputs(values.map(([label, value]) => ({ label, code: rowsToCode(value), operation })));
  };

  const unary = (operation: string, fn: (value: ReturnType<typeof parseCode>) => ReturnType<typeof parseCode>) => emit(operation, [[`${operation} 출력`, fn(rows[0])]]);

  return <div className="grid h-full min-h-0 gap-3 overflow-y-auto p-3 xl:grid-cols-[minmax(420px,1fr)_minmax(340px,.8fr)]">
    <Panel className="min-h-0">
      <SectionTitle icon={<Beaker size={15} />} title="정방향 연산 실험실" action={<Button size="sm" variant="outline" onClick={addInput}>입력 추가</Button>} />
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => unary("시계 방향 회전", (value) => rotateRows(value, 1))}><RotateCw size={14} />회전</Button>
          <Button size="sm" onClick={() => unary("대칭", mirrorRows)}><Combine size={14} />대칭</Button>
          <Button size="sm" onClick={() => unary("중력", applyGravity)}><ArrowDownToLine size={14} />중력</Button>
          <Button size="sm" onClick={() => unary("핀 밀기", (value) => pushPin(value, cap))}><WandSparkles size={14} />핀 밀기</Button>
          <Button size="sm" onClick={() => unary("결정 생성", (value) => generateCrystals(value, cap))}><Sparkles size={14} />생성기</Button>
          <Button size="sm" onClick={() => { const [a, b] = cutShape(rows[0], cap); emit("자르기", [["동쪽 출력", a], ["서쪽 출력", b]]); }}><Split size={14} />절단</Button>
          <Button size="sm" disabled={rows.length < 2} onClick={() => { const [a, b] = swapShapes(rows[0], rows[1], cap); emit("스왑", [["출력 1", a], ["출력 2", b]]); }}><GitBranch size={14} />교환</Button>
          <Button size="sm" disabled={rows.length < 2} onClick={() => emit("쌓기", [["쌓기 결과", stackShapes(rows[0], rows[1], cap)]])}><Layers3 size={14} />쌓기</Button>
        </div>
        <div className="grid gap-3 2xl:grid-cols-2">
          {inputs.map((code, index) => <div key={index} className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2"><span className="grid h-7 w-7 place-items-center rounded-lg bg-[var(--accent)] text-xs font-bold text-white">{letters[index]}</span><span className="text-xs font-semibold">입력 {letters[index]}</span></div>
              {inputs.length > 2 ? <Button size="sm" variant="ghost" onClick={() => removeInput(index)}>제거</Button> : null}
            </div>
            <input value={code} onChange={(event) => setInput(index, event.target.value)} className="mb-3 h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface-0)] px-3 font-mono text-xs outline-none focus:border-[var(--accent)]" />
            <ShapeEditor code={code} cap={cap} onChange={(value) => setInput(index, value)} compact />
          </div>)}
        </div>
      </div>
    </Panel>
    <Panel>
      <SectionTitle icon={<Sparkles size={15} />} title="출력" />
      <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
        {outputs.length ? outputs.map((output, index) => <div key={`${output.code}-${index}`} className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
          <div className="flex items-center justify-between gap-2"><div><div className="text-[10px] uppercase tracking-[.12em] text-[var(--muted)]">{output.operation}</div><div className="text-xs font-semibold">{output.label}</div></div><IconButton label="코드 복사" onClick={() => void navigator.clipboard.writeText(output.code)}><Copy size={14} /></IconButton></div>
          <ShapeRenderer code={output.code} className="my-2" showCode />
          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" variant="outline" onClick={() => setInput(0, output.code)}>입력 A로</Button>
            <Button size="sm" variant="primary" onClick={() => onUseTarget(output.code)}>목표로 분석</Button>
          </div>
        </div>) : <div className="col-span-full grid min-h-[340px] place-items-center text-center text-sm text-[var(--muted)]"><div><Beaker className="mx-auto mb-3" size={34} /><p>입력 도형을 편집하고<br />정방향 연산을 선택하세요.</p></div></div>}
      </div>
    </Panel>
  </div>;
}
