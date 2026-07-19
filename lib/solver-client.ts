"use client";

import type {
  AnalysisResult,
  AnalyzeMode,
  OperationName,
  OperationResult,
  ProgressMessage,
  WorkerOutbound,
} from "./types";

interface PendingJob {
  resolve: (result: AnalysisResult) => void;
  reject: (error: Error) => void;
  onProgress?: (progress: ProgressMessage) => void;
}

interface PendingOperation {
  resolve: (result: OperationResult) => void;
  reject: (error: Error) => void;
}

function inputLayerCount(code: string): number {
  return Math.max(1, code.split(":").filter(Boolean).length);
}

export class SolverClient {
  private worker: Worker | null = null;
  private pending = new Map<string, PendingJob>();
  private operationPending = new Map<string, PendingOperation>();

  private ensureWorker(): Worker {
    if (this.worker) return this.worker;
    this.worker = new Worker("/solver.worker.js", { type: "classic", name: "shapez2-tmam-solver" });
    this.worker.addEventListener("message", (event: MessageEvent<WorkerOutbound>) => {
      const message = event.data;
      if (message.type === "operation-result") {
        const pending = this.operationPending.get(message.jobId);
        if (!pending) return;
        this.operationPending.delete(message.jobId);
        pending.resolve(message.result);
        return;
      }

      const pending = this.pending.get(message.jobId);
      const operation = this.operationPending.get(message.jobId);
      if (!pending && !operation) return;
      if (message.type === "progress") {
        pending?.onProgress?.(message);
      } else if (message.type === "result") {
        this.pending.delete(message.jobId);
        pending?.resolve(message.result);
      } else if (message.type === "cancelled") {
        this.pending.delete(message.jobId);
        this.operationPending.delete(message.jobId);
        pending?.reject(new Error("CANCELLED"));
        operation?.reject(new Error("CANCELLED"));
      } else if (message.type === "error") {
        this.pending.delete(message.jobId);
        this.operationPending.delete(message.jobId);
        pending?.reject(new Error(message.error));
        operation?.reject(new Error(message.error));
      }
    });
    this.worker.addEventListener("error", (event) => {
      const error = new Error(event.message || "Solver worker 오류");
      for (const pending of this.pending.values()) pending.reject(error);
      for (const pending of this.operationPending.values()) pending.reject(error);
      this.pending.clear();
      this.operationPending.clear();
      this.worker?.terminate();
      this.worker = null;
    });
    return this.worker;
  }

  private analyzeInWorker(jobId: string, code: string, cap: number, mode: AnalyzeMode, onProgress?: (progress: ProgressMessage) => void): Promise<AnalysisResult> {
    const worker = this.ensureWorker();
    return new Promise<AnalysisResult>((resolve, reject) => {
      this.pending.set(jobId, { resolve, reject, onProgress });
      worker.postMessage({ type: "analyze", jobId, mode, code, cap });
    });
  }

  analyze(code: string, cap: number, mode: AnalyzeMode, onProgress?: (progress: ProgressMessage) => void): { jobId: string; promise: Promise<AnalysisResult> } {
    const jobId = crypto.randomUUID();
    const layers = inputLayerCount(code);
    const baseCap = Math.max(cap, layers);
    const promise = this.analyzeInWorker(jobId, code, baseCap, mode, onProgress).then(async (initial) => {
      if (layers === baseCap && initial.verdict === "IMPOSSIBLE" && initial.route === "pp-closure-exhausted") {
        const retry = await this.analyzeInWorker(jobId, code, baseCap + 1, mode, onProgress);
        if (retry.verdict === "POSSIBLE") {
          retry.diagnostics.warnings.push(`최종 도형은 ${layers}층이지만 Pin Push 전구체 재생에 작업층 1개가 필요하여 Cap ${baseCap + 1}을 사용했습니다.`);
          return retry;
        }
      }
      return initial;
    });
    return { jobId, promise };
  }

  operate(input: { operation: OperationName; inputA: string; inputB?: string; cap: number; paintColor?: string; crystalColor?: string }): Promise<OperationResult> {
    const jobId = crypto.randomUUID();
    const worker = this.ensureWorker();
    return new Promise<OperationResult>((resolve, reject) => {
      this.operationPending.set(jobId, { resolve, reject });
      worker.postMessage({
        type: "operate",
        jobId,
        ...input,
        inputBPresent: input.operation === "stack" || input.operation === "swap",
      });
    });
  }

  cancel(jobId: string): void {
    this.worker?.postMessage({ type: "cancel", jobId });
  }

  terminate(): void {
    this.worker?.terminate();
    this.worker = null;
    for (const pending of this.pending.values()) pending.reject(new Error("WORKER_TERMINATED"));
    for (const pending of this.operationPending.values()) pending.reject(new Error("WORKER_TERMINATED"));
    this.pending.clear();
    this.operationPending.clear();
  }

  warmup(): void {
    const worker = this.ensureWorker();
    worker.postMessage({ type: "warmup", jobId: `warmup-${crypto.randomUUID()}` });
  }
}

export const solverClient = new SolverClient();
