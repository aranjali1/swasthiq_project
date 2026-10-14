"""Standard-library HTTP server for the evaluation endpoint and local review UI."""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .agent import run

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "dist"


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/agent/run":
            return self._json(404, {"error": "not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100_000: raise ValueError("request body must be 1-100000 bytes")
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict): raise ValueError("request must be an object")
            if not isinstance(value.get("conversation_id"), str): raise ValueError("conversation_id must be a string")
            if not isinstance(value.get("today"), str): raise ValueError("today must be YYYY-MM-DD")
            from datetime import date
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value["today"]):
                raise ValueError("today must be YYYY-MM-DD")
            date.fromisoformat(value["today"])
            if not isinstance(value.get("turns"), list) or not all(isinstance(t, str) for t in value["turns"]):
                raise ValueError("turns must be an array of strings")
            self._json(200, run(value))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/examples":
            examples = []
            for item in sorted((ROOT / "conversations").glob("*.json")):
                value = json.loads(item.read_text())
                examples.append({k: value[k] for k in ("id", "description", "today", "turns")})
            return self._json(200, examples)
        target = (FRONTEND / path.lstrip("/")).resolve()
        if path == "/" or not target.is_file() or FRONTEND not in target.parents:
            target = FRONTEND / "index.html"
        if not target.is_file(): return self._json(404, {"error": "frontend not built"})
        data = target.read_bytes()
        content_type = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".vtt": "text/vtt", ".png": "image/png"}.get(target.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"SwasthiQ review app: http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__": main()
