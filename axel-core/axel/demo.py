"""Servidor minimo sin FastAPI. Escucha en http://127.0.0.1:8090"""

from __future__ import annotations

import hmac
import html
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from datetime import timedelta

from axel import knowledge_base as kb
from axel import notify
from axel.agents.reservas import (
    _NOMBRE_DIA,
    _ahora_cali,
    _creada_cali,
    avisos_cita,
    cuando_fila,
    franja_fila,
    _franjas_kb,
    _hhmm,
    cupos_de,
    franjas_validas,
    paso,
)
from axel.connectors import whatsapp
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import _reporte, pedidos_filas, process

def _db_path() -> str:
    """Base fija: /opt/Axel-AI/axel-core/axel.db en el VPS; si esa carpeta no existe, junto al código.
    AXEL_DB solo para pruebas (base temporal)."""
    if os.getenv("AXEL_DB"):
        return os.environ["AXEL_DB"]
    vps = Path("/opt/Axel-AI/axel-core")
    return str((vps if vps.is_dir() else Path(__file__).resolve().parents[1]) / "axel.db")


memory = Memory(_db_path())

DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _salud_kb() -> dict:
    """kb.json existe y se lee como JSON, y cuántos servicios tiene. Sin datos del negocio."""
    try:
        datos = json.loads(kb._kb_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"kb_ok": False, "servicios": 0}
    return {"kb_ok": isinstance(datos, dict), "servicios": len(kb.servicios()) if isinstance(datos, dict) else 0}


def _quien(fila: dict) -> str:
    cli = memory.get_customer(str(fila.get("customer_id") or "")) or {}
    return str(fila.get("name") or cli.get("phone") or "sin nombre")


def _fuera_de_franja() -> list[str]:
    """Citas confirmadas que no caen en una franja visible. No se borran ni ocupan cupo."""
    validas = franjas_validas()
    hoy = _ahora_cali().date()
    lineas = []
    for c in memory.list_confirmed_reservas(500):
        summary = str(c.get("summary") or "")
        cuando = cuando_fila(c)
        if cuando and cuando[1:] in validas and cuando[0].weekday() != 6:
            continue
        if cuando and cuando[0] < hoy:
            continue
        if cuando:
            hora = f"{cuando[1]}" if cuando[2] == 0 else f"{cuando[1]}:{cuando[2]:02d}"
            que = f"{_NOMBRE_DIA[cuando[0].weekday()]} a las {hora}"
        else:
            que = f"«{summary[:60]}»"
        lineas.append(f"Fuera de franja: {que} · {_quien(c)}")
    return lineas


def _tabla_cupos() -> str:
    """Franjas de los próximos 7 días (sin domingo): LIBRE, TOMADA o PASÓ. Solo lectura."""
    franjas = franjas_validas()
    if not franjas:
        return "<p>Ninguna franja cabe en el horario de la KB.</p>"
    hoy = _ahora_cali().date()
    filas = []
    for i in range(7):
        dia = hoy + timedelta(days=i)
        if dia.weekday() == 6:
            continue
        tomadas = cupos_de(memory, dia)
        celdas = []
        for f in franjas:
            fila = tomadas.get(f)
            if fila is not None:
                celdas.append(f"<td class='tomada'>TOMADA · {html.escape(_quien(fila))}</td>")
            elif paso(dia, f):
                celdas.append("<td class='paso'>PASÓ</td>")
            else:
                celdas.append("<td class='ok'>LIBRE</td>")
        filas.append(f"<tr><td>{DIAS_ES[dia.weekday()]} {dia.strftime('%d/%m')}</td>{''.join(celdas)}</tr>")
    cab = "".join(f"<th>{_hhmm(f)}</th>" for f in franjas)
    fuera = "".join(f"<p>{html.escape(l)}</p>" for l in _fuera_de_franja())
    return f"<table><tr><th>Día</th>{cab}</tr>{''.join(filas)}</table>{fuera}"


def _tabla_catalogo() -> str:
    """Lo que AXEL sabe del negocio desde la KB. Solo lectura: se cambia con comandos del dueño."""
    datos = kb.load_kb()
    abre, cierra = kb.get_hours()
    franjas = ", ".join(_hhmm(f) for f in _franjas_kb()) or "ninguna"
    filas = [
        ("Negocio", datos.get("negocio") or "—"),
        ("Rubro", datos.get("rubro") or "—"),
        ("Agenda", "sí" if kb.agenda() else "no"),
        ("Horario", f"{_hhmm(abre)} a {_hhmm(cierra)}"),
        ("Franjas", franjas),
        ("Ubicación", datos.get("ubicacion") or "—"),
    ]
    datos_html = "".join(f"<tr><th>{k}</th><td>{html.escape(str(v))}</td></tr>" for k, v in filas)
    servicios = "".join(
        f"<tr><td>{html.escape(str(s['nombre']))}</td><td>{kb.precio_txt(s.get('precio') or 0)}</td></tr>"
        for s in kb.servicios()
    ) or "<tr><td colspan='2'>Sin servicios</td></tr>"
    return (
        f"<table>{datos_html}</table>"
        f"<table style='margin-top:8px'><tr><th>Servicio</th><th>Precio</th></tr>{servicios}</table>"
    )


def _tabla_envios() -> str:
    """Últimos 8 envíos: hora Cali, para qué, estado, a quién. Sin texto: puede traer el celular. Solo lectura."""
    digitos = lambda s: "".join(ch for ch in str(s or "") if ch.isdigit())[-10:]
    owner = digitos(os.getenv("WA_OWNER_PHONE"))
    nombres = {digitos(c.get("phone")): c.get("name") for c in memory.list_customers(500) if c.get("phone") and c.get("name")}
    filas = []
    for e in memory.list_envios(8):
        d = digitos(e.get("destino"))
        quien = "dueño" if d and d == owner else (nombres.get(d) or f"…{d[-4:]}" if d else "—")
        hora = _creada_cali(str(e.get("created_at") or "")).strftime("%d/%m %H:%M")
        filas.append(
            "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in (hora, e["tipo"], e["estado"], quien)) + "</tr>"
        )
    cuerpo = "".join(filas) or "<tr><td colspan='4'>Sin envíos.</td></tr>"
    return f"<table><tr><th>Hora Cali</th><th>Para qué</th><th>Estado</th><th>A quién</th></tr>{cuerpo}</table>"


def _tabla_pedidos() -> str:
    """Últimos 15 pedidos, igual que el comando pedidos. Solo lectura."""
    filas = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in fila) + "</tr>" for fila in pedidos_filas(memory)
    ) or "<tr><td colspan='4'>No hay pedidos.</td></tr>"
    return f"<table><tr><th>Hora Cali</th><th>Cliente</th><th>Pedido</th><th>Estado</th></tr>{filas}</table>"


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
        cita = memory.last_reserva(str(ficha.get("customer_id") or ""))
        cita_txt = franja_fila(cita) if cita else "—"
        ficha_html = (
            f"Nombre: {html.escape(str(ficha.get('name') or '—'))} · "
            f"Celular: {html.escape(str(ficha.get('phone') or '—'))} · "
            f"Correo: {html.escape(str(ficha.get('email') or '—'))} · "
            f"Cita: {html.escape(cita_txt)} · "
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
        wa = []
        for u in memory.list_whatsapp_customers(20):
            ult = memory.last_reserva(str(u.get("customer_id") or ""))
            ult_txt = franja_fila(ult) if ult else "—"
            escribio = _creada_cali(str(u["last_in"])).strftime("%d/%m %H:%M") if u.get("last_in") else "—"
            wa.append(
                "<tr>"
                f"<td>{html.escape(str(u.get('name') or '—'))}</td>"
                f"<td>{html.escape(str(u.get('phone') or '—'))}</td>"
                f"<td>{html.escape(ult_txt)}</td>"
                f"<td>{html.escape(escribio)}</td>"
                "</tr>"
            )
        tabla_wa = "".join(wa) or "<tr><td colspan='4'>Sin clientes WhatsApp</td></tr>"
        n_cli = len(memory.list_customers(50))
        n_citas = len(memory.list_confirmed_reservas(50))
        n_pend = len(memory.list_pending())
        return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>AXEL vivo</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#111;color:#eee;margin:24px}}
h1{{color:#6cf}} table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{border:1px solid #444;padding:8px;text-align:left;vertical-align:top}}
th{{background:#222}} .ok{{color:#8f8}} .tomada{{color:#f99}} .paso{{color:#888}}
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
<h2>Reporte de hoy</h2>
<pre>{html.escape(_reporte(memory))}</pre>
<h2>Envíos</h2>
{_tabla_envios()}
<h2>Clientes WhatsApp</h2>
<table><tr><th>Nombre</th><th>Celular</th><th>Última cita</th><th>Última vez que escribió</th></tr>{tabla_wa}</table>
<form method="post" action="/panel" style="margin:16px 0">
<input name="text" placeholder="Escribe a AXEL" style="width:70%;padding:8px" />
<button type="submit">Enviar</button>
</form>
<h2>Pendientes</h2>
<table><tr><th>Evento</th><th>Intent</th><th>Pedido</th><th>Decisión</th></tr>{pendientes}</table>
<h2>Clientes</h2>
<table><tr><th>Nombre</th><th>Celular</th><th>Correo</th><th>ID</th></tr>{tabla_cli}</table>
<h2>Pedidos</h2>
{_tabla_pedidos()}
<h2>Catalogo</h2>
{_tabla_catalogo()}
<h2>Cupos de la semana</h2>
{_tabla_cupos()}
<h2>Citas</h2>
<table><tr><th>Cuando</th><th>Cliente</th><th>Qué dijo</th></tr>{tabla_citas}</table>
<h2>Últimos</h2>
<table><tr><th>Cuando</th><th>Canal</th><th>Agente</th><th>Nivel</th><th>Aprobación</th><th>Entró</th><th>Respondió</th></tr>{tabla}</table>
</body></html>"""

    def _es_local(self) -> bool:
        """Local = Host 127.0.0.1/localhost y sin cabeceras de proxy. Cualquier otro Host es público.
        nginx y ngrok llegan desde 127.0.0.1: no se mira la IP."""
        host = (self.headers.get("Host") or "").lower()
        proxy = ("X-Forwarded-For", "X-Forwarded-Host", "X-Real-IP", "Forwarded")
        if "ngrok" in host or any(self.headers.get(h) for h in proxy):
            return False
        return host.rsplit(":", 1)[0] in {"127.0.0.1", "localhost"}

    def _bloqueado(self, metodo: str) -> bool:
        """Desde fuera solo /webhooks/whatsapp y GET /health. El resto: 403 solo_local."""
        if self._es_local():
            return False
        ruta = urlparse(self.path).path
        if ruta == "/webhooks/whatsapp" or (metodo == "GET" and ruta == "/health"):
            return False
        self._json(403, {"error": "solo_local"})
        return True

    def do_GET(self) -> None:
        if self._bloqueado("GET"):
            return
        if self.path in ("/", "/index.html"):
            self._html(200, self._panel())
            return
        if self.path == "/health":
            self._json(200, {"ok": True, "service": "axel-core-demo", **_salud_kb()})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/webhooks/whatsapp":
            q = parse_qs(parsed.query)
            mode = (q.get("hub.mode") or [""])[0]
            token = (q.get("hub.verify_token") or [""])[0]
            challenge = (q.get("hub.challenge") or [""])[0]
            # WA_VERIFY_TOKEN obligatorio en .env: sin valor, el verify no pasa.
            expected = os.getenv("WA_VERIFY_TOKEN") or ""
            if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
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
        if self._bloqueado("POST"):
            return
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
            # Solo Meta: firma HMAC del body crudo con WA_APP_SECRET. Sin secreto o sin firma, no se procesa.
            if not os.getenv("WA_APP_SECRET"):
                print("WA IN rechazado: falta WA_APP_SECRET en .env")
                self._json(403, {"error": "sin_secreto"})
                return
            if not whatsapp.firma_valida(raw, self.headers.get("X-Hub-Signature-256") or ""):
                print("WA IN rechazado: firma inválida o ausente")
                self._json(403, {"error": "firma_invalida"})
                return
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "json_invalido"})
                return
            msgs = whatsapp.parse_incoming(body)
            print("WA IN: mensajes=", len(msgs), "token=", bool(os.getenv("WA_ACCESS_TOKEN")))
            # Meta reintenta el mismo wamid: solo se procesa la primera vez.
            nuevos = [m for m in msgs if memory.marcar_wamid(str(m.get("raw_ref") or ""))]
            for m in msgs:
                if m not in nuevos:
                    print("WA IN repetido, se ignora:", m.get("raw_ref"))
            # 200 a Meta primero; después se procesa y se responde al cliente.
            self._json(200, {"ok": True, "parsed": len(msgs), "nuevos": len(nuevos)})
            self.wfile.flush()
            for msg in nuevos:
                print("WA TXT:", msg.get("text"), "de", msg.get("channel_user_id"))
                if msg.get("raw_ref"):
                    whatsapp.mark_read(str(msg.get("raw_ref")))
                out = self._run(msg)
                reply = (out.get("reply_text") or "")[:900]
                if reply:
                    res = whatsapp.send_text(msg.get("phone") or msg.get("channel_user_id") or "", reply)
                    print("WA OUT:", res)
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
            # Aviso al cliente 24 h y 2 h antes. Si el demo está apagado a esa hora, se pierde.
            for fila, texto in avisos_cita(memory):
                cli = memory.get_customer(str(fila.get("customer_id") or "")) or {}
                estado = notify.enviar(
                    memory, f"aviso_{fila['plazo']}", str(cli.get("phone") or ""), texto, str(fila.get("customer_id") or "")
                )
                print("AVISO CITA", fila.get("event_id"), estado, texto)
        except Exception as exc:
            print("AVISO CITA error:", exc)
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
            lineas = []
            for c in citas:
                cli = memory.get_customer(str(c.get("customer_id") or "")) or {}
                franja = franja_fila(c)
                lineas.append(f"- {franja} · {c.get('name') or 'sin nombre'} · {cli.get('phone') or 'sin teléfono'}")
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