# 클라이언트 전용 아키텍처

```text
Next.js static UI
  ├─ Shape editor / renderer
  ├─ Proof canvas / Batch / Compare
  ├─ IndexedDB history
  └─ SolverClient
       └─ solver.worker.js
            ├─ structural parser
            ├─ forward physics
            ├─ Corner/Half/Swap/Stack classifier
            ├─ frozen Claw/Hybrid lookup + replay
            └─ Proof / negative certificate builder
```

## 계산 격리

분류는 모두 Web Worker에서 실행됩니다. UI main thread와 solver state가 분리되므로 긴 작업 중에도 편집·스크롤·탭 전환이 가능합니다. 진행 이벤트는 phase/current/total/statesVisited 형식이며, 취소는 cooperative flag를 먼저 보낸 뒤 Batch 중단에서는 worker 자체를 종료합니다.

## 배포

Next.js는 `output: export`를 사용합니다. 운영 서버는 HTML/JS/CSS/worker/gzip JSON만 전달하며 solver endpoint나 DB가 없습니다. 브라우저 기록은 IndexedDB에만 저장됩니다.

## 향후 WASM backend

현재 TypeScript research core와 향후 Rust/C++ WASM core는 동일한 메시지 계약을 사용합니다.

```ts
{ type: "analyze", jobId, mode, code, cap }
{ type: "progress", jobId, phase, current, total, ... }
{ type: "result", jobId, result: AnalysisResult }
```

따라서 UI의 Proof canvas, Batch, history, certificate viewer를 수정하지 않고 worker implementation만 교체할 수 있습니다.

## 대형 Proof 대응

- Proof는 트리 대신 공유 DAG로 저장
- 입력 연산 접기
- Tree 보기는 필요할 때만 clone
- node layout은 canvas 표시 시 계산
- shape SVG는 compact mode 지원
- worker 결과와 UI layout을 분리
