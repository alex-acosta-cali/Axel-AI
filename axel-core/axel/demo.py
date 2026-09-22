"""Servidor minimo sin FastAPI (por si pip falla). Preferir uvicorn axel.main:app."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process

memory = Memory("./axel.db")


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"ok": True, "service": "axel-core-demo"})
            return
        if self.path.startswith("/audit/"):
            event_id = self.path.split("/audit/", 1)[1]
            row = memory.get_audit(event_id)
            self._json(200, row or {"error": "not_found"})
            return
        if self.path.startswith("/audit"):
            self._json(200, {"events": memory.list_audit()})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/webhooks/test":
            self._json(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length) or b"{}")
        env = Envelope(
            channel=data.get("channel", "test"),
            channel_user_id=data.get("channel_user_id", "tester"),
            text=data.get("text", ""),
            phone=data.get("phone"),
            email=data.get("email"),
            name=data.get("name"),
        )
        out = process(env, memory)
        self._json(200, out.model_dump())

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))


def main() -> None:
    server = HTTPServer(("127.0.0.1", 8090), Handler)
    print("AXEL demo en http://127.0.0.1:8090")
    server.serve_forever()


if __name__ == "__main__":
    main()
