import argparse
import json
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from agent.config import DEFAULT_CONFIG_PATH
from agent.diagnostics import diagnostics
from agent.logging_config import logger
from agent.runtime import AnalogDvrRuntime
from agent.setup_page import build_setup_page
from agent.version import PRODUCT_NAME, VERSION


runtime: AnalogDvrRuntime


class Handler(BaseHTTPRequestHandler):
    server_version = "AnalogDvrEdge/1.0"

    def _send_json(self, data, code=200):
        raw = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str, code=200):
        raw = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/health"):
                self._send_json({"ok": True, "service": "analog-dvr-edge", "product": PRODUCT_NAME, "version": VERSION})
            elif path == "/setup":
                self._send_html(build_setup_page(PRODUCT_NAME, VERSION))
            elif path == "/version":
                self._send_json({"ok": True, "product": PRODUCT_NAME, "version": VERSION})
            elif path == "/status":
                self._send_json(runtime.status())
            elif path == "/config":
                self._send_json(runtime.public_config())
            elif path == "/probe":
                self._send_json({"ok": True, "results": runtime.public_probe()})
            elif path == "/diagnostics":
                self._send_json({"ok": True, "diagnostics": diagnostics(), "runtime": runtime.status()})
            else:
                self._send_json({"ok": False, "error": "not found"}, 404)
        except Exception as exc:
            logger.exception("GET %s failed", path)
            self._send_json({"ok": False, "error": str(exc)}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/config":
                data = self._read_json()
                runtime.save_config(data)
                self._send_json({"ok": True, "config": runtime.public_config()})
            elif path == "/probe":
                self._send_json({"ok": True, "results": runtime.public_probe()})
            elif path in ("/start", "/reload", "/workers/reload"):
                self._send_json(runtime.start())
            elif path == "/stop":
                self._send_json(runtime.stop())
            else:
                self._send_json({"ok": False, "error": "not found"}, 404)
        except Exception as exc:
            logger.exception("POST %s failed", path)
            self._send_json({"ok": False, "error": str(exc)}, 500)

    def log_message(self, fmt, *args):
        logger.info(fmt, *args)


def main() -> int:
    global runtime
    parser = argparse.ArgumentParser(description="Analog DVR edge HTTP service")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--no-autostart", action="store_true")
    args = parser.parse_args()

    runtime = AnalogDvrRuntime(args.config)
    if not args.no_autostart:
        try:
            runtime.start()
        except Exception as exc:
            logger.warning("autostart skipped: %s", exc)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)

    def stop(_signum, _frame):
        runtime.stop()
        httpd.shutdown()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("listening on %s:%s", args.host, args.port)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
