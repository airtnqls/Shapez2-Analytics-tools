from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "out"


class StudioHandler(SimpleHTTPRequestHandler):
    server_version = "Shapez2TMAM/2.1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def end_headers(self) -> None:
        request_path = urlparse(self.path).path
        if request_path == "/sw.js":
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        elif request_path == "/solver.worker.js" or request_path.startswith("/data/"):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/health":
            self._json({"ok": True, "backend": "static-host+client-worker", "compute": "client-only"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/shutdown" and self.client_address[0] in {"127.0.0.1", "::1"}:
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[web] {self.address_string()} {fmt % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Shapez2 TMAM local Web GUI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if not (STATIC_ROOT / "index.html").is_file():
        parser.error("out/index.html이 없습니다. 먼저 npm run build를 실행하세요.")
    mimetypes.add_type("application/wasm", ".wasm")
    server = ThreadingHTTPServer((args.host, args.port), StudioHandler)
    server.daemon_threads = True
    url = f"http://{args.host}:{args.port}/"
    print(f"Shapez2 TMAM Web Studio: {url}")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
