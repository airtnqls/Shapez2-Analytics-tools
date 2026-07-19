"use client";

import { create } from "zustand";
import type { AnalysisResult, AnalyzeMode, ProgressMessage } from "./types";

export type WorkspaceTab = "shape" | "proof" | "lab" | "batch" | "compare" | "research";

interface AppState {
  code: string;
  cap: number;
  mode: AnalyzeMode;
  result: AnalysisResult | null;
  progress: ProgressMessage | null;
  running: boolean;
  activeJobId: string | null;
  error: string | null;
  workspaceTab: WorkspaceTab;
  leftOpen: boolean;
  rightOpen: boolean;
  bottomOpen: boolean;
  commandOpen: boolean;
  theme: "dark" | "light" | "system";
  setCode: (code: string) => void;
  setCap: (cap: number) => void;
  setMode: (mode: AnalyzeMode) => void;
  setResult: (result: AnalysisResult | null) => void;
  setProgress: (progress: ProgressMessage | null) => void;
  setRunning: (running: boolean, jobId?: string | null) => void;
  setError: (error: string | null) => void;
  setWorkspaceTab: (tab: WorkspaceTab) => void;
  toggleLeft: () => void;
  toggleRight: () => void;
  toggleBottom: () => void;
  setCommandOpen: (open: boolean) => void;
  setTheme: (theme: "dark" | "light" | "system") => void;
}

export const useAppStore = create<AppState>((set) => ({
  code: "-PPP:SS-P:---P:c--P:cS-S",
  cap: 5,
  mode: "fast",
  result: null,
  progress: null,
  running: false,
  activeJobId: null,
  error: null,
  workspaceTab: "shape",
  leftOpen: true,
  rightOpen: false,
  bottomOpen: false,
  commandOpen: false,
  theme: "light",
  setCode: (code) => set({ code }),
  setCap: (cap) => set({ cap: Math.max(1, Math.min(100, Math.round(cap) || 1)) }),
  setMode: (mode) => set({ mode }),
  setResult: (result) => set({ result }),
  setProgress: (progress) => set({ progress }),
  setRunning: (running, jobId = null) => set({ running, activeJobId: running ? jobId : null }),
  setError: (error) => set({ error }),
  setWorkspaceTab: (workspaceTab) => set({ workspaceTab }),
  toggleLeft: () => set((state) => ({ leftOpen: !state.leftOpen })),
  toggleRight: () => set((state) => ({ rightOpen: !state.rightOpen })),
  toggleBottom: () => set((state) => ({ bottomOpen: !state.bottomOpen })),
  setCommandOpen: (commandOpen) => set({ commandOpen }),
  setTheme: (theme) => set({ theme }),
}));
