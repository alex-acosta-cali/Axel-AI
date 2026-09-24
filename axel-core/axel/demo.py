"""Servidor minimo sin FastAPI. Escucha en http://127.0.0.1:8090"""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

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
        pend = []
        for p in memory.list_pending():
            eid = html.escape(str(p.get("event_id") or ""))
            pend.append(
                "<tr>"
                f"<td>{eid}</td>"
                f"<td>{html.escape(str(p.get('intent') or ''))}</td>"
                f"<td>{html.escape(str(p.get('requested_action') or ''))}</td>"
                f"<td><form method='post' action='/decidir' style='display:inline'>"
                f"<input type='hidden' name='event_id' value='{eid}'/>"
                f"<button name='decision' value='approved'>Aprobar</button> "
                f"<button name='decision' value='rejected'>Rechazar</button>"
                f"</form></td></tr>"
            )
        pendientes = "".join(pend) or "<tr><td colspan='4'>Nada pendiente</td></tr>"
        ficha = memory.find_by_identity("panel", "alex_pc")
        ficha_html = (
            f"Nombre: {html.escape(str(ficha.get('name') or '—'))} · "
            f"Celular: {html.escape(str(ficha.get('phone') or '—'))} · "
            f"Correo: {html.escape(str(ficha.get('email') or '—'))} · "
            f"ID: {html.escape(str(ficha.get('customer_id') or '—'))}"
        )
        citas = []
        for c in memory.list_confirmed_reservas(8):
            citas.append(
                "<tr>"
                f"<td>{html.escape(str(c.get('created_at') or ''))}</td>"
                f"<td>{html.escape(str(c.get('name') or c.get('customer_id') or ''))}</td>"
                f"<td>{html.escape(str(c.get('summary') or ''))}</td>"
                "</tr>"
            )
        tabla_citas = "".join(citas) or "<tr><td colspan='3'>Sin citas confirmadas</td></tr>"
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
<p><b>Ficha de quien escribe en este panel:</b> {ficha_html}</p>
<form method="post" action="/panel" style="margin:16px 0">
<input name="text" placeholder="Escribe a AXEL (ej. horario o reembolso)" style="width:70%;padding:8px" />
<button type="submit" style="padding:8px 14px">Enviar</button>
</form>
<h2>Pendientes del dueño</h2>
<table>
<tr><th>Evento</th><th>Intent</th><th>Pedido</th><th>Decisión</th></tr>
{pendientes}
</table>
<h2>Citas confirmadas (piloto)</h2>
<table>
<tr><th>Cuando</th><th>Cliente</th><th>Qué dijo</th></tr>
{tabla_citas}
</table>
<h2>Últimos mensajes</h2>
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

    def _run(self, data: dict) -> dict:
        env = Envelope(
            channel=data.get("channel", "test"),
            channel_user_id=data.get("channel_user_id", "tester"),
            text=data.get("text", ""),
            phone=data.get("phone"),
            email=data.get("email"),
            name=data.get("name"),
        )
        return process(env, memory).model_dump()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) or b""
        if self.path == "/panel":
            form = parse_qs(raw.decode("utf-8", "replace"))
            text = (form.get("text") or [""])[0]
            self._run({"text": text, "channel": "panel", "channel_user_id": "alex_pc"})
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path == "/decidir":
            form = parse_qs(raw.decode("utf-8", "replace"))
            event_id = (form.get("event_id") or [""])[0]
            decision = (form.get("decision") or [""])[0]
            memory.resolve_pending(event_id, decision)
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path != "/webhooks/test":
            self._json(404, {"error": "not_found"})
            return
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "json_invalido", "hint": "usa scripts/enviar_prueba.ps1"})
            return
        self._json(200, self._run(data))

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))


def main() -> None:
    server = HTTPServer(("127.0.0.1", 8090), Handler)
    print("AXEL demo en http://127.0.0.1:8090")
    server.serve_forever()


if __name__ == "__main__":
    main()
