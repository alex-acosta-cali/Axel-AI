"""Servidor minimo sin FastAPI. Escucha en http://127.0.0.1:8090"""

from __future__ import annotations

import html
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from axel.connectors import whatsapp
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
        tabla = "".join(items) or "<tr><td colspan='7'>Sin eventos aún.</td></tr>"
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
        notas = memory.list_notes(str(ficha.get("customer_id") or ""), 3)
        notas_txt = " | ".join(str(n.get("note") or "") for n in notas) or "—"
        ficha_html = (
            f"Nombre: {html.escape(str(ficha.get('name') or '—'))} · "
            f"Celular: {html.escape(str(ficha.get('phone') or '—'))} · "
            f"Correo: {html.escape(str(ficha.get('email') or '—'))} · "
            f"Notas: {html.escape(notas_txt)}"
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
        cli = []
        for u in memory.list_customers(15):
            cli.append(
                "<tr>"
                f"<td>{html.escape(str(u.get('name') or '—'))}</td>"
                f"<td>{html.escape(str(u.get('phone') or '—'))}</td>"
                f"<td>{html.escape(str(u.get('email') or '—'))}</td>"
                f"<td>{html.escape(str(u.get('customer_id') or ''))}</td>"
                "</tr>"
            )
        tabla_cli = "".join(cli) or "<tr><td colspan='4'>Sin clientes</td></tr>"
        n_cli = len(memory.list_customers(50))
        n_citas = len(memory.list_confirmed_reservas(50))
        n_pend = len(memory.list_pending())
        return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>AXEL vivo</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#111;color:#eee;margin:24px}}
h1{{color:#6cf}} table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{border:1px solid #444;padding:8px;text-align:left;vertical-align:top}}
th{{background:#222}} .ok{{color:#8f8}}
.kpis{{display:flex;gap:12px;margin:16px 0;flex-wrap:wrap}}
.kpi{{background:#1c1c1c;border:1px solid #444;padding:14px 18px;min-width:140px}}
.kpi b{{display:block;font-size:28px;color:#6cf}}
</style></head><body>
<h1>AXEL AI OS — panel local</h1>
<p class="ok">Servidor en http://127.0.0.1:8090</p>
<div class="kpis">
<div class="kpi"><b>{n_cli}</b>clientes</div>
<div class="kpi"><b>{n_citas}</b>citas</div>
<div class="kpi"><b>{n_pend}</b>pendientes</div>
</div>
<p><b>Ficha panel:</b> {ficha_html}</p>
<form method="post" action="/panel" style="margin:16px 0">
<input name="text" placeholder="Escribe a AXEL" style="width:70%;padding:8px" />
<button type="submit">Enviar</button>
</form>
<h2>Pendientes</h2>
<table><tr><th>Evento</th><th>Intent</th><th>Pedido</th><th>Decisión</th></tr>{pendientes}</table>
<h2>Clientes</h2>
<table><tr><th>Nombre</th><th>Celular</th><th>Correo</th><th>ID</th></tr>{tabla_cli}</table>
<h2>Citas</h2>
<table><tr><th>Cuando</th><th>Cliente</th><th>Qué dijo</th></tr>{tabla_citas}</table>
<h2>Últimos</h2>
<table><tr><th>Cuando</th><th>Canal</th><th>Agente</th><th>Nivel</th><th>Aprobación</th><th>Entró</th><th>Respondió</th></tr>{tabla}</table>
</body></html>"""

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._html(200, self._panel())
            return
        if self.path == "/health":
            self._json(200, {"ok": True, "service": "axel-core-demo"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/webhooks/whatsapp":
            q = parse_qs(parsed.query)
            mode = (q.get("hub.mode") or [""])[0]
            token = (q.get("hub.verify_token") or [""])[0]
            challenge = (q.get("hub.challenge") or [""])[0]
            expected = os.getenv("WA_VERIFY_TOKEN", "axel-verify")
            if mode == "subscribe" and token == expected:
                raw = challenge.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            self._json(403, {"error": "verify_token_invalido"})
            return
        if self.path.startswith("/audit/"):
            row = memory.get_audit(self.path.split("/audit/", 1)[1])
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
            self._run({"text": (form.get("text") or [""])[0], "channel": "panel", "channel_user_id": "alex_pc"})
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path == "/decidir":
            form = parse_qs(raw.decode("utf-8", "replace"))
            memory.resolve_pending((form.get("event_id") or [""])[0], (form.get("decision") or [""])[0])
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path == "/webhooks/whatsapp":
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "json_invalido"})
                return
            msgs = whatsapp.parse_incoming(body)
            print("WA IN: mensajes=", len(msgs), "token=", bool(os.getenv("WA_ACCESS_TOKEN")))
            enviados = []
            for msg in msgs:
                print("WA TXT:", msg.get("text"), "de", msg.get("channel_user_id"))
                if msg.get("raw_ref"):
                    whatsapp.mark_read(str(msg.get("raw_ref")))
                out = self._run(msg)
                reply = (out.get("reply_text") or "")[:900]
                if reply:
                    res = whatsapp.send_text(msg.get("phone") or msg.get("channel_user_id") or "", reply)
                    print("WA OUT:", res)
                    enviados.append(res)
            self._json(200, {"ok": True, "parsed": len(msgs), "sent": enviados})
            return
        if self.path != "/webhooks/test":
            self._json(404, {"error": "not_found"})
            return
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "json_invalido"})
            return
        self._json(200, self._run(data))

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))


def _recordatorio_loop() -> None:
    import time
    from datetime import date

    from axel.connectors.whatsapp import send_text

    ultimo = ""
    while True:
        time.sleep(60)
        try:
            hoy = date.today().isoformat()
            if ultimo == hoy:
                continue
            owner = (os.getenv("WA_OWNER_PHONE") or "").strip()
            if not owner:
                continue
            citas = memory.list_confirmed_reservas(8)
            if not citas:
                ultimo = hoy
                continue
            lineas = [
                f"- {c.get('name') or c.get('customer_id')}: {c.get('summary')}"
                for c in citas
            ]
            send_text(owner, "Recordatorio AXEL (hoy):\n" + "\n".join(lineas))
            print("RECORDATORIO enviado", hoy)
            ultimo = hoy
        except Exception as exc:
            print("RECORDATORIO error:", exc)


def main() -> None:
    try:
        from pathlib import Path
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(env_path)
        print("ENV:", env_path, "existe=", env_path.exists(), "token=", bool(os.getenv("WA_ACCESS_TOKEN")))
    except Exception as exc:
        print("ENV error:", exc)
    import threading

    threading.Thread(target=_recordatorio_loop, daemon=True).start()
    server = HTTPServer(("127.0.0.1", 8090), Handler)
    print("AXEL demo en http://127.0.0.1:8090")
    print("Webhook WhatsApp: POST /webhooks/whatsapp")
    server.serve_forever()


if __name__ == "__main__":
    main()