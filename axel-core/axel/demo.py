"""Servidor minimo sin FastAPI. Escucha en http://127.0.0.1:8090"""

from __future__ import annotations

import html
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

    def _html(self, code: int, body: str) -> None:
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _panel(self) -> str:
        rows = memory.list_audit(8)
        items = []
        for r in rows:
            items.append(
                "<tr>"
                f"<td>{html.escape(str(r.get('received_at') or ''))}</td>"
                f"<td>{html.escape(str(r.get('channel') or ''))}</td>"
                f"<td>{html.escape(str(r.get('agent') or ''))}</td>"
                f"<td>N{html.escape(str(r.get('supervision_level') or ''))}</td>"
                f"<td>{html.escape(str(r.get('approval_status') or ''))}</td>"
                f"<td>{html.escape(str(r.get('input_summary') or ''))}</td>"
                f"<td>{html.escape(str(r.get('output_summary') or ''))}</td>"
                "</tr>"
            )
        tabla = "".join(items) or "<tr><td colspan='7'>Sin eventos aún. Corre scripts/enviar_prueba.ps1</td></tr>"
        return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>AXEL vivo</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#111;color:#eee;margin:24px}}
h1{{color:#6cf}} table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{border:1px solid #444;padding:8px;text-align:left;vertical-align:top}}
th{{background:#222}} .ok{{color:#8f8}}
</style></head><body>
<h1>AXEL AI OS — panel local</h1>
<p class="ok">Servidor en http://127.0.0.1:8090 — esto no es WhatsApp, es tu PC.</p>
<p>GitHub: github.com/alex-acosta-cali/Axel-AI</p>
<table>
<tr><th>Cuando</th><th>Canal</th><th>Agente</th><th>Nivel</th><th>Aprobación</th><th>Entró</th><th>Respondió</th></tr>
{tabla}
</table>
<p>Recarga la página (F5) después de un script de prueba.</p>
</body></html>"""

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._html(200, self._panel())
            return
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

    def do_POST(self) -> None:
        if self.path != "/webhooks/test":
            self._json(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) or b"{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self._json(400, {"error": "json_invalido", "hint": "usa scripts/enviar_prueba.ps1"})
            return
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
