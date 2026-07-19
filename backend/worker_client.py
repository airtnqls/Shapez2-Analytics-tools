from __future__ import annotations

import atexit
import json
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable


class WorkerBackendError(RuntimeError):
    pass


class WorkerClient:
    """Persistent JSON-lines client for the ZIP-provided solver worker."""

    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.host = self.project_root / "backend" / "solver_host.mjs"
        self._process: subprocess.Popen[str] | None = None
        self._ready = threading.Event()
        self._startup_error: str | None = None
        self._jobs: dict[str, queue.Queue[dict]] = {}
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._process and self._process.poll() is None:
                return
            self._ready.clear()
            self._startup_error = None
            try:
                self._process = subprocess.Popen(
                    ["node", str(self.host)],
                    cwd=self.project_root,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as exc:
                raise WorkerBackendError(f"Node.js ZIP backend 시작 실패: {exc}") from exc
            threading.Thread(target=self._read_stdout, daemon=True).start()
            threading.Thread(target=self._read_stderr, daemon=True).start()
        if not self._ready.wait(8):
            self.close()
            raise WorkerBackendError(self._startup_error or "ZIP backend 시작 시간 초과")
        if self._startup_error:
            self.close()
            raise WorkerBackendError(self._startup_error)

    def _read_stdout(self) -> None:
        process = self._process
        if not process or not process.stdout:
            return
        for raw in process.stdout:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = message.get("type")
            if kind == "host-ready":
                self._ready.set()
                continue
            if kind == "host-error":
                self._startup_error = str(message.get("error", "ZIP backend 오류"))
                self._ready.set()
            job_id = message.get("jobId")
            if job_id:
                with self._lock:
                    target = self._jobs.get(str(job_id))
                if target:
                    target.put(message)
        self._ready.set()

    def _read_stderr(self) -> None:
        process = self._process
        if not process or not process.stderr:
            return
        for raw in process.stderr:
            if raw.strip() and not self._startup_error:
                self._startup_error = raw.strip()

    def _send(self, message: dict) -> None:
        process = self._process
        if not process or process.poll() is not None or not process.stdin:
            raise WorkerBackendError("ZIP backend가 실행 중이 아닙니다.")
        with self._write_lock:
            process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            process.stdin.flush()

    def analyze(
        self,
        code: str,
        cap: int,
        mode: str = "proof",
        timeout: float = 180.0,
        on_progress: Callable[[dict], None] | None = None,
    ) -> dict:
        self.start()
        job_id = str(uuid.uuid4())
        inbox: queue.Queue[dict] = queue.Queue()
        with self._lock:
            self._jobs[job_id] = inbox
        try:
            self._send({"type": "analyze", "jobId": job_id, "code": code, "cap": cap, "mode": mode})
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._send({"type": "cancel", "jobId": job_id})
                    raise WorkerBackendError(f"분석 시간 초과 ({timeout:.0f}초)")
                try:
                    message = inbox.get(timeout=min(remaining, 1.0))
                except queue.Empty:
                    if not self._process or self._process.poll() is not None:
                        raise WorkerBackendError("ZIP backend가 예기치 않게 종료되었습니다.")
                    continue
                kind = message.get("type")
                if kind == "progress":
                    if on_progress:
                        on_progress(message)
                elif kind == "result":
                    return message["result"]
                elif kind == "cancelled":
                    raise WorkerBackendError("분석이 취소되었습니다.")
                elif kind == "error":
                    raise WorkerBackendError(str(message.get("error", "분석 오류")))
        finally:
            with self._lock:
                self._jobs.pop(job_id, None)

    def operate(
        self,
        operation: str,
        input_a: str,
        input_b: str = "",
        cap: int = 5,
        paint_color: str = "u",
        crystal_color: str = "u",
        input_b_present: bool | None = None,
        timeout: float = 60.0,
    ) -> dict:
        self.start()
        job_id = str(uuid.uuid4())
        inbox: queue.Queue[dict] = queue.Queue()
        with self._lock:
            self._jobs[job_id] = inbox
        try:
            self._send({
                "type": "operate", "jobId": job_id, "operation": operation,
                "inputA": input_a, "inputB": input_b, "cap": int(cap),
                "inputBPresent": bool(input_b_present) if input_b_present is not None else bool(input_b),
                "paintColor": paint_color, "crystalColor": crystal_color,
            })
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkerBackendError(f"ZIP 연산 시간 초과 ({timeout:.0f}초)")
                try:
                    message = inbox.get(timeout=min(remaining, 1.0))
                except queue.Empty:
                    if not self._process or self._process.poll() is not None:
                        raise WorkerBackendError("ZIP backend가 예기치 않게 종료되었습니다.")
                    continue
                kind = message.get("type")
                if kind == "operation-result":
                    return message["result"]
                if kind == "error":
                    raise WorkerBackendError(str(message.get("error", "ZIP 연산 오류")))
                if kind == "cancelled":
                    raise WorkerBackendError("ZIP 연산이 취소되었습니다.")
        finally:
            with self._lock:
                self._jobs.pop(job_id, None)

    def close(self) -> None:
        with self._lock:
            process, self._process = self._process, None
        if not process or process.poll() is not None:
            return
        try:
            if process.stdin:
                process.stdin.write('{"type":"shutdown"}\n')
                process.stdin.flush()
                process.stdin.close()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()


worker_client = WorkerClient()
atexit.register(worker_client.close)
