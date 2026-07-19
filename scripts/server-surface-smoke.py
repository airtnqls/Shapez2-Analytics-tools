from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for_health(base_url: str) -> dict:
    for _ in range(50):
        try:
            with urlopen(f"{base_url}/api/health", timeout=1) as response:
                return json.load(response)
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("local static host did not start")


def expect_not_found(base_url: str, path: str) -> None:
    request = Request(
        f"{base_url}{path}",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        urlopen(request, timeout=3)
    except HTTPError as error:
        if error.code == 404:
            return
        raise AssertionError(f"{path} returned {error.code}, expected 404") from error
    raise AssertionError(f"{path} unexpectedly exposed server-side compute")


def main() -> None:
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "backend.server", "--port", str(port), "--no-open"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        health = wait_for_health(base_url)
        assert health["compute"] == "client-only"
        expect_not_found(base_url, "/api/analyze")
        expect_not_found(base_url, "/api/operate")
        with urlopen(f"{base_url}/solver.worker.js", timeout=3) as response:
            assert response.headers.get("Cache-Control") == "no-cache, must-revalidate"
        print({"status": "PASS", "health": health, "computeEndpoints": "404", "workerCache": "revalidate"})
    finally:
        try:
            request = Request(f"{base_url}/api/shutdown", data=b"{}", method="POST")
            urlopen(request, timeout=2).read()
        except OSError:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
