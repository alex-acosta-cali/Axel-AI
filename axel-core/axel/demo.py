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
    cerrar_recordatorio,
    recordatorio_dia,
)
from axel.connectors import whatsapp
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import _reporte, inventario_filas, pedidos_filas, process

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
    ) or "<tr><td colspan='4'>Hoy no hay pedidos.</td></tr>"
    return f"<table><tr><th>Hora Cali</th><th>Cliente</th><th>Pedido</th><th>Estado</th></tr>{filas}</table>"


def _tabla_inventario() -> str:
    """Muro 65: máximo 15 productos, igual que el comando inventario. Solo lectura, solo local."""
    filas = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in fila) + "</tr>" for fila in inventario_filas(memory)
    ) or "<tr><td colspan='4'>No hay productos.</td></tr>"
    return f"<table><tr><th>Código</th><th>Nombre</th><th>Stock</th><th>Disponible</th></tr>{filas}</table>"


def _canal_txt(canal: str) -> str:
    """Solo WhatsApp es canal vivo. Panel y prueba son internos. Sin canal guardado, nada."""
    canal = str(canal or "")
    return "WhatsApp" if canal == "whatsapp" else ("interno" if canal else "")


def _chats() -> tuple[str, str]:
    """Lista de clientes con su último mensaje, y un hilo de solo lectura por cliente. Sin caja de enviar."""
    filas, hilos = [], []
    for i, c in enumerate(memory.list_conversaciones(20)):
        cel = "".join(ch for ch in str(c.get("phone") or "") if ch.isdigit())
        quien = html.escape(str(c.get("name") or (f"…{cel[-4:]}" if cel else "sin nombre")))
        hora = _creada_cali(str(c.get("created_at") or "")).strftime("%d/%m %H:%M")
        # Datos borrados: los mensajes siguen en la base, pero el panel no los lee.
        borrado = bool(c.get("datos_borrados"))
        ultimo = "Datos borrados" if borrado else html.escape(str(c.get("text") or ""))
        filas.append(
            f"<button class='chat' data-abre='hilo-{i}'>"
            f"<span class='chat-1'><b>{quien}</b><span>{hora}</span></span>"
            f"<span class='chat-2'>{ultimo}</span>"
            f"<span class='chat-3'>{_canal_txt(c.get('channel'))}</span></button>"
        )
        burbujas = "<p class='vacio'>Datos borrados</p>" if borrado else "".join(
            f"<div class='msj {'axel' if m.get('direction') == 'out' else 'cliente'}'>"
            f"{html.escape(str(m.get('text') or ''))}"
            f"<small>{'AXEL · ' if m.get('direction') == 'out' else ''}"
            f"{_creada_cali(str(m.get('created_at') or '')).strftime('%d/%m %H:%M')}</small></div>"
            for m in memory.list_mensajes(str(c.get("customer_id") or ""), 20)
        )
        hilos.append(
            f"<dialog class='bloque' id='hilo-{i}'><div class='ventana'>"
            f"<div class='bloque-cab'><div class='bloque-t'>{quien} <i>{_canal_txt(c.get('channel'))}</i></div>"
            "<form method='dialog'><button class='cerrar' aria-label='Cerrar'>×</button></form></div>"
            f"<div class='hilo'>{burbujas}</div><p class='ficha'>Solo lectura.</p></div></dialog>"
        )
    lista = "".join(filas) or "<p class='vacio'>Al día. Nadie espera.</p>"
    return f"<div class='chats'>{lista}</div>", "".join(hilos)


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
        tabla = "".join(items) or "<tr><td colspan='7'>Al día. Nadie espera.</td></tr>"
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
        pendientes = "".join(pend) or "<tr><td colspan='4'>Nada por aprobar.</td></tr>"
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
        # Una sola lista de clientes. Canal: WhatsApp o vacío. Sin ID. Última vez = último mensaje por WhatsApp.
        wa = {str(u.get("customer_id")): u.get("last_in") for u in memory.list_whatsapp_customers(500)}
        cli = []
        for u in memory.list_customers(20):
            cid = str(u.get("customer_id") or "")
            ult = memory.last_reserva(cid)
            ult_txt = franja_fila(ult) if ult else "—"
            escribio = _creada_cali(str(wa[cid])).strftime("%d/%m %H:%M") if wa.get(cid) else "—"
            cli.append(
                "<tr>"
                f"<td>{html.escape(str(u.get('name') or '—'))}</td>"
                f"<td>{'WhatsApp' if cid in wa else ''}</td>"
                f"<td>{html.escape(str(u.get('phone') or '—'))}</td>"
                f"<td>{html.escape(ult_txt)}</td>"
                f"<td>{html.escape(escribio)}</td>"
                "</tr>"
            )
        tabla_cli = "".join(cli) or "<tr><td colspan='5'>Sin clientes</td></tr>"
        n_pend = len(memory.list_pending())
        # Piel del diseño: número grande = citas de hoy; debajo lo anotado hoy, sin cobro (pedido no es cobro).
        ahora = _ahora_cali()
        hoy = ahora.date()
        citas_hoy = sum(1 for c in memory.list_confirmed_reservas(500) if (w := cuando_fila(c)) and w[0] == hoy)
        pedidos = memory.list_pedidos(500)
        anotado_hoy = sum(
            int(p["precio"]) for p in pedidos
            if (p.get("estado") or "anotado") != "rechazado"
            and _creada_cali(str(p.get("created_at") or "")).date() == hoy
        )
        en_curso = sum(1 for p in pedidos if (p.get("estado") or "anotado") not in {"entregado", "rechazado"})
        negocio = html.escape(str(kb.load_kb().get("negocio") or ""))
        punto = "<i class='punto' aria-label='hay por aprobar'></i>" if n_pend else ""
        # Muro 72: tres bloques (Día, Conversaciones, Aprobaciones), inventario abajo. Cada uno es una ventana (dialog).
        # Catálogo vive en Mi negocio; Envíos en Registro, la puerta del operador.
        aviso_pend = f"<span class='marca'>{n_pend}</span>" if n_pend else "<span class='marca cero'>0</span>"
        cerrar = "<form method='dialog'><button class='cerrar' aria-label='Cerrar'>×</button></form>"
        chats, hilos = _chats()
        return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ΛXEL panel</title>
<style>
:root{{--fondo:#0b3d2e;--caja:#134a3b;--borde:#2b5f4e;--texto:#f4efe4;--tenue:#b9c9c0;--dorado:#c9a85c;
--ok:#a8dcb0;--mal:#f2a08f;--oscuro:#0a2f24}}
*{{box-sizing:border-box}}
body{{font-family:"Segoe UI",system-ui,sans-serif;background:var(--fondo);color:var(--texto);margin:0;padding:20px 16px 180px}}
main{{max-width:720px;margin:0 auto}}
.arriba{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}}
.marca-axel{{display:flex;flex-direction:column;gap:6px}}
.marca-axel h1{{margin:0;font-size:30px;letter-spacing:.32em;font-weight:300;color:var(--texto)}}
.marca-axel h1::first-letter{{color:var(--dorado)}}
.negocio{{font-size:17px}}
.hora{{color:var(--tenue);font-size:14px;padding-top:6px}}
.grande{{margin:28px 0 0;font-size:96px;line-height:1;font-weight:300;color:var(--dorado);font-variant-numeric:tabular-nums}}
.grande-t{{margin:4px 0 0;color:var(--tenue)}}
.anotado{{display:inline-block;margin:14px 0 0;border:1px solid var(--dorado);color:var(--dorado);border-radius:999px;padding:4px 14px;font-size:15px}}
.tarjetas{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:24px 0 0}}
.tarjeta{{background:var(--caja);border:1px solid var(--borde);border-radius:18px;padding:16px 8px;text-align:center;color:var(--tenue);font:inherit;font-size:14px;min-height:44px}}
.tarjeta b{{display:block;font-size:40px;font-weight:300;color:var(--texto);margin-bottom:4px}}
.otros{{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 0}}
.otro{{background:none;border:1px solid var(--borde);border-radius:999px;color:var(--tenue);font:inherit;font-size:14px;padding:10px 18px}}
.local{{color:var(--tenue);font-size:12px;margin:22px 0 0}}
.puertas{{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);display:flex;gap:4px;background:var(--oscuro);
border:1px solid var(--borde);border-radius:999px;padding:6px;width:min(560px,calc(100% - 32px))}}
.puertas button{{flex:1;background:none;border:0;border-radius:999px;color:var(--texto);font:inherit;font-size:15px;padding:12px 6px;min-height:44px;cursor:pointer}}
.puertas button:hover,.puertas button:focus-visible,.tarjeta:hover,.otro:hover{{background:var(--caja);border-color:var(--dorado)}}
.punto{{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--dorado);margin-left:6px;vertical-align:middle}}
dialog.bloque{{background:var(--fondo);color:var(--texto);border:1px solid var(--borde);border-radius:22px;padding:0;
width:min(960px,calc(100% - 24px));max-height:calc(100vh - 24px)}}
dialog.bloque::backdrop{{background:rgba(4,20,15,.7)}}
.ventana{{padding:6px 20px 24px}}
.bloque-cab{{display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:var(--fondo);padding-top:10px}}
.bloque-cab form{{margin:0}}
.bloque-t{{display:flex;align-items:center;gap:10px;font-size:26px;font-weight:600;margin:6px 0}}
.cerrar{{width:44px;height:44px;border-radius:50%;font-size:22px;padding:0}}
h2{{font-size:15px;font-weight:600;margin:22px 0 10px;color:var(--dorado);letter-spacing:.04em}}
.tabla{{overflow-x:auto;background:var(--caja);border-radius:16px;padding:4px 12px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{border-bottom:1px solid var(--borde);padding:9px 8px;text-align:left;vertical-align:top}}
tr:last-child td{{border-bottom:0}}
th{{color:var(--tenue);font-weight:500;font-size:12px;letter-spacing:.04em}}
pre{{background:var(--caja);border-radius:16px;padding:14px;white-space:pre-wrap;margin:0;font-family:inherit;font-size:14px}}
.ok{{color:var(--ok)}} .tomada{{color:var(--mal)}} .paso{{color:var(--tenue)}}
.marca{{background:var(--dorado);color:#1c1606;border-radius:999px;padding:1px 10px;font-size:13px}}
.marca.cero{{background:var(--borde);color:var(--tenue)}}
.ficha{{color:var(--tenue);font-size:14px;margin:18px 0 0}}
.bloque-t i{{font-style:normal;font-size:14px;font-weight:400;color:var(--tenue)}}
.chats{{display:flex;flex-direction:column;background:var(--caja);border-radius:16px;overflow:hidden}}
.chat{{display:flex;flex-direction:column;gap:3px;text-align:left;background:none;border:0;border-bottom:1px solid var(--borde);
border-radius:0;padding:12px 14px;min-height:44px;width:100%}}
.chat:last-child{{border-bottom:0}}
.chat:hover,.chat:focus-visible{{background:var(--fondo)}}
.chat-1{{display:flex;justify-content:space-between;gap:10px}} .chat-1 span{{color:var(--tenue);font-size:13px}}
.chat-2{{color:var(--tenue);font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.chat-3{{color:var(--tenue);font-size:12px}}
.vacio{{color:var(--tenue);padding:14px;margin:0}}
.hilo{{display:flex;flex-direction:column;gap:10px;margin:14px 0 0}}
.msj{{max-width:78%;padding:10px 14px;border-radius:18px;white-space:pre-wrap;font-size:15px;line-height:1.4}}
.msj small{{display:block;margin-top:4px;font-size:12px;opacity:.75;text-align:right}}
.msj.cliente{{align-self:flex-start;border:1px solid var(--borde)}}
.msj.axel{{align-self:flex-end;background:var(--texto);color:#13241d}}
.lambda{{align-self:center;color:var(--dorado);font-size:20px;padding:0 6px 0 12px}}
form.escribir{{position:fixed;left:50%;bottom:86px;transform:translateX(-50%);display:flex;gap:8px;margin:0;
width:min(560px,calc(100% - 32px))}}
form.escribir input{{flex:1;min-width:0;padding:12px 16px;border-radius:999px;border:1px solid var(--borde);background:var(--caja);color:var(--texto);font:inherit}}
button{{padding:8px 16px;border-radius:999px;border:1px solid var(--borde);background:var(--caja);color:var(--texto);cursor:pointer;font:inherit}}
button:hover{{border-color:var(--dorado)}}
button[value=approved]{{background:var(--dorado);border-color:var(--dorado);color:#1c1606;font-weight:600}}
@media (max-width:520px){{.grande{{font-size:76px}} .tarjeta b{{font-size:32px}} dialog.bloque{{width:100%;max-height:100vh;border-radius:0}}}}
</style></head><body><main>
<header class="arriba">
<div class="marca-axel"><h1>ΛXEL</h1><span class="negocio">{negocio}</span></div>
<span class="hora">Cali {ahora.strftime('%H:%M')}</span>
</header>

<p class="grande">{citas_hoy}</p>
<p class="grande-t">citas hoy</p>
<p class="anotado">Anotado hoy, sin cobro · {kb.precio_txt(anotado_hoy)}</p>

<div class="tarjetas">
<button class="tarjeta" data-abre="dia"><b>{citas_hoy}</b>citas hoy</button>
<button class="tarjeta" data-abre="dia"><b>{en_curso}</b>pedidos en curso</button>
<button class="tarjeta" data-abre="aprobaciones"><b>{n_pend}{punto}</b>por aprobar</button>
</div>
<div class="otros">
<button class="otro" data-abre="mi-negocio">Mi negocio</button>
<button class="otro" data-abre="inventario">Inventario</button>
<button class="otro" data-abre="registro">Registro · operador</button>
</div>
<p class="local">panel local · solo 127.0.0.1</p>

<nav class="puertas" aria-label="Puertas">
<span class="lambda" aria-hidden="true">Λ</span>
<button data-abre="dia">Día</button>
<button data-abre="conversaciones">Conversaciones</button>
<button data-abre="aprobaciones">Aprobaciones{punto}</button>
</nav>

<dialog class="bloque" id="dia"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">Día</div>{cerrar}</div>
<h2>Reporte de hoy</h2>
<pre>{html.escape(_reporte(memory))}</pre>
<h2>Citas</h2>
<div class="tabla"><table><tr><th>Cuando</th><th>Cliente</th><th>Qué dijo</th></tr>{tabla_citas}</table></div>
<h2>Cupos de la semana</h2>
<div class="tabla">{_tabla_cupos()}</div>
<h2>Pedidos</h2>
<div class="tabla">{_tabla_pedidos()}</div>
</div></dialog>

<dialog class="bloque" id="conversaciones"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">Conversaciones</div>{cerrar}</div>
<h2>Chats</h2>
{chats}
<h2>Clientes</h2>
<div class="tabla"><table><tr><th>Nombre</th><th>Canal</th><th>Celular</th><th>Última cita</th><th>Última vez</th></tr>{tabla_cli}</table></div>
</div></dialog>
{hilos}

<dialog class="bloque" id="aprobaciones"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">Aprobaciones {aviso_pend}</div>{cerrar}</div>
<h2>Pendientes</h2>
<div class="tabla"><table><tr><th>Evento</th><th>Intent</th><th>Pedido</th><th>Decisión</th></tr>{pendientes}</table></div>
</div></dialog>

<dialog class="bloque" id="inventario"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">Inventario</div>{cerrar}</div>
<h2>Inventario</h2>
<div class="tabla">{_tabla_inventario()}</div>
</div></dialog>

<dialog class="bloque" id="mi-negocio"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">Mi negocio</div>{cerrar}</div>
<h2>Catálogo</h2>
<div class="tabla">{_tabla_catalogo()}</div>
</div></dialog>

<dialog class="bloque" id="registro"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">Registro</div>{cerrar}</div>
<h2>Envíos</h2>
<div class="tabla">{_tabla_envios()}</div>
<h2>Últimos</h2>
<div class="tabla"><table><tr><th>Cuando</th><th>Canal</th><th>Agente</th><th>Nivel</th><th>Aprobación</th><th>Entró</th><th>Respondió</th></tr>{tabla}</table></div>
<p class="ficha"><b>Ficha panel:</b> {ficha_html}</p>
</div></dialog>
</main>

<form class="escribir" method="post" action="/panel">
<input name="text" placeholder="Escribe a AXEL" aria-label="Escribe a AXEL" />
<button type="submit">Enviar</button>
</form>
<script>
document.querySelectorAll("[data-abre]").forEach(function (b) {{
  b.addEventListener("click", function () {{ document.getElementById(b.dataset.abre).showModal(); }});
}});
document.querySelectorAll("dialog").forEach(function (d) {{
  d.addEventListener("click", function (e) {{ if (e.target === d) d.close(); }});
}});
</script>
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
            payload={"foto": data.get("foto") is True},
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
                reply = (out.get("reply_text") or "")[:3500]
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
            # Recordatorio del día al dueño: hora Cali, solo citas de hoy, una vez aunque AXEL se reinicie.
            # El día se marca después de intentar el envío. Si Meta falla, la fila queda 'fallo' y no se reintenta.
            ahora = _ahora_cali()
            texto = recordatorio_dia(memory, ahora)
            if texto:
                try:
                    estado = notify.enviar(memory, "recordatorio_dia", os.getenv("WA_OWNER_PHONE") or "", texto)
                    print("RECORDATORIO", estado)
                finally:
                    cerrar_recordatorio(memory, ahora)
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