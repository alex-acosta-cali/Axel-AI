"""Servidor minimo sin FastAPI. Escucha en http://127.0.0.1:8090"""

from __future__ import annotations

import hmac
import html
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from datetime import datetime, timedelta, timezone

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
from axel.orchestrator import (
    anotado_hoy,
    enviar_alerta_cierre,
    inventario_filas,
    pedidos_de_hoy,
    pedidos_filas,
    process,
)

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
    return f"<table><tr><th>{_a('Día')}</th>{cab}</tr>{''.join(filas)}</table>{fuera}"


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
        ("Tono", kb.tono()),
        ("Política de cancelación", (datos.get("politicas") or {}).get("cancelacion") or "—"),
        ("Política de garantía", (datos.get("politicas") or {}).get("garantia") or "—"),
    ]
    # Muro B: los servicios viven en Inventario. Mi negocio no repite esa tabla.
    datos_html = "".join(f"<tr><th>{_a(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in filas)
    return f"<table>{datos_html}</table>"


def _stock_txt(s: dict) -> str:
    valor = s.get("stock")
    return str(valor) if isinstance(valor, int) and not isinstance(valor, bool) else ""


def _tabla_servicios() -> str:
    """Servicios de la KB: nombre, precio, stock e imagen. Muro C: el dueño edita precio y stock aquí; se guardan
    en servicios[] de kb.json, el mismo campo que cambia WhatsApp. Sin stock: sin tope. No sube fotos."""
    filas = []
    for i, s in enumerate(kb.servicios()):
        nombre = html.escape(str(s["nombre"]))
        fid = f"srv-{i}"
        filas.append(
            "<tr>"
            f"<td>{nombre}</td>"
            f"<td><input form='{fid}' name='precio' inputmode='numeric' value='{int(s.get('precio') or 0)}'"
            f" aria-label='Precio de {nombre}'/></td>"
            f"<td><input form='{fid}' name='stock' inputmode='numeric' value='{_stock_txt(s)}' placeholder='sin tope'"
            f" aria-label='Stock de {nombre}'/></td>"
            f"<td>{'con imagen' if s.get('imagen') else 'sin imagen'}</td>"
            f"<td><form id='{fid}' method='post' action='/servicio'><input type='hidden' name='nombre' value='{nombre}'/>"
            f"<button type='submit'>{_a('Guardar')}</button></form></td>"
            "</tr>"
        )
    cuerpo = "".join(filas) or "<tr><td colspan='5'>Sin servicios</td></tr>"
    cab = "".join(f"<th>{_a(c)}</th>" for c in ("Servicio", "Precio", "Stock", "Imagen", ""))
    return f"<table><tr>{cab}</tr>{cuerpo}</table>"


# Muro C: avisos fijos tras guardar desde el panel. Solo códigos conocidos: nada del formulario se refleja.
AVISOS = {
    "servicio_ok": "Servicio guardado.",
    "servicio_agotado": "Servicio guardado. Stock 0: no se vende.",
    "precio_vacio": "Precio vacío: el precio no se guardó.",
    "precio_mal": "Precio no válido. No se guardó nada.",
    "stock_mal": "Stock no válido. No se guardó nada.",
    "servicio_no": "No existe ese servicio.",
    "franjas_ok": "Franjas guardadas. Una cita ya confirmada no se borra: si no cae en una franja, queda fuera de franja.",
    "franjas_fuera": "Franjas guardadas. Alguna queda fuera del horario y no se ofrece. Las citas confirmadas no se borran.",
    "franjas_mal": "Franja no válida: horas de 0 a 23, separadas por coma. No se guardó.",
}


def guardar_servicio(nombre: str, precio_raw: str, stock_raw: str) -> str:
    """Precio y stock de un servicio desde el panel. Mismo campo que WhatsApp (kb.set_price / kb.set_stock).
    Precio vacío no se guarda. Algo inválido: no se guarda nada. Devuelve un código de AVISOS."""
    s = kb.buscar_servicio(nombre)
    if not s:
        return "servicio_no"
    precio_raw, stock_raw = (precio_raw or "").strip(), (stock_raw or "").strip()
    precio = None
    if precio_raw:
        if not re.fullmatch(r"\$?\s*\d[\d.]*", precio_raw) or int(precio_raw.strip("$ ").replace(".", "")) <= 0:
            return "precio_mal"
        precio = int(precio_raw.strip("$ ").replace(".", ""))
    stock = None
    if stock_raw:
        if not stock_raw.isdigit():
            return "stock_mal"
        stock = int(stock_raw)
    if precio is not None:
        kb.set_price(str(s["nombre"]), str(precio))
    if stock is not None:
        kb.set_stock(str(s["nombre"]), stock)
    if precio is None:
        return "precio_vacio"
    return "servicio_agotado" if stock == 0 else "servicio_ok"


def guardar_franjas(raw: str) -> str:
    """Franjas desde Mi negocio: '8, 12, 16' (o 8:30). Horas 0 a 23. Repetidas se ignoran. Una inválida: no se
    guarda nada. Las citas confirmadas no se tocan. Devuelve un código de AVISOS."""
    horas = []
    partes = [p.strip() for p in (raw or "").split(",") if p.strip()]
    for p in partes:
        m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", p)
        if not m or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
            return "franjas_mal"
        horas.append((int(m.group(1)), int(m.group(2) or 0)))
    if not horas:
        return "franjas_mal"
    kb.set_franjas(horas)
    abre, cierra = kb.get_hours()
    return "franjas_fuera" if any(not abre <= h < cierra for h in set(horas)) else "franjas_ok"


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
    cab = "".join(f"<th>{_a(c)}</th>" for c in ("Hora Cali", "Para qué", "Estado", "A quién"))
    return f"<table><tr>{cab}</tr>{cuerpo}</table>"


def _tabla_pedidos() -> str:
    """Últimos 15 pedidos, igual que el comando pedidos. Solo lectura."""
    filas = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in fila) + "</tr>" for fila in pedidos_filas(memory)
    ) or "<tr><td colspan='4'>Hoy no hay pedidos.</td></tr>"
    cab = "".join(f"<th>{_a(c)}</th>" for c in ("Hora Cali", "Cliente", "Pedido", "Estado"))
    return f"<table><tr>{cab}</tr>{filas}</table>"


def _tabla_inventario() -> str:
    """Muro 65: máximo 15 productos, igual que el comando inventario. Solo lectura, solo local."""
    filas = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in fila) + "</tr>" for fila in inventario_filas(memory)
    ) or "<tr><td colspan='4'>No hay productos.</td></tr>"
    cab = "".join(f"<th>{_a(c)}</th>" for c in ("Código", "Nombre", "Stock", "Disponible"))
    return f"<table><tr>{cab}</tr>{filas}</table>"


_LETRA_A = "aAáÁ"


def _a(titulo: str) -> str:
    """Rótulo fijo: cada a/A se dibuja como la Λ dorada de la marca. La palabra no se parte (nowrap) y el
    lector de pantalla lee la letra real. Solo para rótulos fijos, nunca para nombres ni mensajes."""
    def letra(ch: str) -> str:
        # &Lambda; y no la letra suelta: la consola de Windows (cp1252) no imprime Λ.
        return f"<span class='a' aria-hidden='true'>&Lambda;</span><span class='sr'>{ch}</span>" if ch in _LETRA_A else html.escape(ch)

    return " ".join(
        f"<span class='palabra'>{''.join(letra(ch) for ch in p)}</span>" if any(ch in _LETRA_A for ch in p) else html.escape(p)
        for p in titulo.split(" ")
    )


def _canal_txt(canal: str) -> str:
    """Solo WhatsApp es canal vivo. Panel y prueba son internos. Sin canal guardado, nada."""
    canal = str(canal or "")
    return "WhatsApp" if canal == "whatsapp" else ("interno" if canal else "")


def _quien_txt(c: dict) -> str:
    cel = "".join(ch for ch in str(c.get("phone") or "") if ch.isdigit())
    return html.escape(str(c.get("name") or (f"…{cel[-4:]}" if cel else "sin nombre")))


def _hilo(hid: str, cid: str, quien: str, canal: str, borrado: bool) -> str:
    """Hilo de solo lectura de un cliente. Datos borrados: los mensajes siguen en la base, pero el panel no los lee."""
    burbujas = "<p class='vacio'>Datos borrados</p>" if borrado else "".join(
        f"<div class='msj {'axel' if m.get('direction') == 'out' else 'cliente'}'>"
        f"{html.escape(str(m.get('text') or ''))}"
        f"<small>{'AXEL · ' if m.get('direction') == 'out' else ''}"
        f"{_creada_cali(str(m.get('created_at') or '')).strftime('%d/%m %H:%M')}</small></div>"
        for m in memory.list_mensajes(cid, 20)
    ) or "<p class='vacio'>Al día. Nadie espera.</p>"
    return (
        f"<dialog class='bloque' id='{hid}'><div class='ventana'>"
        f"<div class='bloque-cab'><div class='bloque-t'>{quien} <i>{_canal_txt(canal)}</i></div>"
        "<form method='dialog'><button class='cerrar' aria-label='Cerrar'>×</button></form></div>"
        f"<div class='hilo'>{burbujas}</div><p class='ficha'>Solo lectura.</p></div></dialog>"
    )


def _chats_y_hilos(extra: list[str] = ()) -> tuple[str, str, dict[str, str]]:
    """Lista de clientes con su último mensaje y un hilo de solo lectura por cliente. Sin caja de enviar.
    'extra': clientes (p. ej. con aprobación pendiente) que necesitan hilo aunque no estén en la lista.
    Devuelve también customer_id -> id del hilo."""
    filas, hilos, mapa = [], [], {}
    for i, c in enumerate(memory.list_conversaciones(20)):
        cid = str(c.get("customer_id") or "")
        quien = _quien_txt(c)
        hora = _creada_cali(str(c.get("created_at") or "")).strftime("%d/%m %H:%M")
        borrado = bool(c.get("datos_borrados"))
        ultimo = "Datos borrados" if borrado else html.escape(str(c.get("text") or ""))
        filas.append(
            f"<button class='chat' data-abre='hilo-{i}'>"
            f"<span class='chat-1'><b>{quien}</b><span>{hora}</span></span>"
            f"<span class='chat-2'>{ultimo}</span>"
            f"<span class='chat-3'>{_canal_txt(c.get('channel'))}</span></button>"
        )
        hilos.append(_hilo(f"hilo-{i}", cid, quien, str(c.get("channel") or ""), borrado))
        mapa[cid] = f"hilo-{i}"
    for j, cid in enumerate(x for x in dict.fromkeys(extra) if x and x not in mapa):
        c = memory.get_customer(cid) or {}
        canal = "whatsapp" if cid in memory.clientes_de_canal("whatsapp") else ""
        hilos.append(_hilo(f"hilo-x{j}", cid, _quien_txt(c), canal, bool(c.get("datos_borrados"))))
        mapa[cid] = f"hilo-x{j}"
    lista = "".join(filas) or "<p class='vacio'>Al día. Nadie espera.</p>"
    return f"<div class='chats'>{lista}</div>", "".join(hilos), mapa


def _chats() -> tuple[str, str]:
    lista, hilos, _ = _chats_y_hilos()
    return lista, hilos


_CERRAR = "<form method='dialog'><button class='cerrar' aria-label='Cerrar'>×</button></form>"


# Muro E: lo que pide el cliente, en palabras del dueño. Intent desconocido: se nombra tal cual.
_PIDE = {"reembolso": "reembolso", "descuento": "descuento", "borrar_datos": "borrar sus datos",
         "referencia": "una referencia sin inventario", "queja": "atención a una queja"}
# Solo si el cliente lo escribió: daño, pérdida o mal servicio.
_MENCIONA = (
    ("daño", re.compile(r"\bdañ(?:o|os|ado|ada|ados|adas)\b|\bdano\b|\bdanad[oa]s?\b", re.I)),
    ("pérdida", re.compile(r"\bp[eé]rdid[oa]s?\b|\bperd(?:í|i)\b|\bse perdi[oó]\b", re.I)),
    ("mal servicio", re.compile(r"\bmal servicio\b|\bmala atenci[oó]n\b", re.I)),
)
ATRASO_HORAS = 4


def _pedido_anotado(cid: str, pedidos: list[dict]) -> dict | None:
    """El pedido más nuevo del cliente que sigue anotado. Otro estado no cuenta."""
    return next((p for p in pedidos if str(p.get("customer_id")) == cid and (p.get("estado") or "anotado") == "anotado"), None)


def _resumen(intent: str, texto: str, pedido: dict | None) -> str:
    """'Pide reembolso. No hay pedido anotado.' + lo que el cliente mencionó. Nada inventado."""
    partes = [f"Pide {_PIDE.get(intent, intent or 'revisión')}."]
    partes.append(f"Pedido anotado: {pedido['servicio']} {kb.precio_txt(pedido['precio'])}." if pedido
                  else "No hay pedido anotado.")
    dichos = [nombre for nombre, rx in _MENCIONA if rx.search(texto or "")]
    if dichos:
        partes.append(f"Menciona {', '.join(dichos)}.")
    return " ".join(partes)


def _atrasado(creado_utc: str, ahora_utc: datetime) -> bool:
    try:
        return ahora_utc - datetime.fromisoformat(creado_utc) > timedelta(hours=ATRASO_HORAS)
    except ValueError:
        return False


_AVISO_TXT = {"enviado": "avisado", "fallo": "fallo", "fuera_24h": "fuera de 24 h",
              "sin_celular": "sin celular", "omitido_dueno": "omitido"}


def _cierre(d: dict, envios: list[dict]) -> str:
    """Hora de apertura, hora de decisión y cómo quedó el aviso al cliente (fila n3_cliente de Avisos entre la
    apertura y la decisión, al celular del cliente). Sin esa fila: 'sin aviso'."""
    quedo = "aprobada" if d.get("status") == "approved" else "rechazada"
    abre = _creada_cali(str(d.get("created_at") or "")).strftime("%d/%m %H:%M") if d.get("created_at") else "—"
    decide = _creada_cali(str(d["decided_at"])).strftime("%d/%m %H:%M") if d.get("decided_at") else "—"
    cel = "".join(ch for ch in str((memory.get_customer(str(d.get("customer_id") or "")) or {}).get("phone") or "")
                  if ch.isdigit())[-10:]
    desde, hasta = str(d.get("created_at") or ""), str(d.get("decided_at") or "")
    aviso = next(
        (e for e in envios
         if e.get("tipo") == "n3_cliente" and cel and str(e.get("destino") or "")[-10:] == cel
         and hasta and desde <= str(e.get("created_at") or "") <= hasta),
        None,
    )
    estado = _AVISO_TXT.get(str(aviso.get("estado")), str(aviso.get("estado"))) if aviso else "sin aviso"
    return f"{quedo} · abierto {abre} · decidido {decide} · {estado}"


def _corto(texto: str, n: int = 60) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


def _tabla_eventos(limit: int = 15) -> str:
    """Muro F: Registro en Inicio, Gestión o Fin, con un resumen corto. Inicio = primer mensaje del cliente.
    Gestión = pendiente del dueño. Fin = aprobado, rechazado o entregado. No repite el hilo. Solo lectura."""
    eventos = []  # (hora UTC 'AAAA-MM-DD HH:MM:SS', tipo, cid, resumen)
    for m in memory.list_inicios(limit):
        texto = "Datos borrados" if m.get("datos_borrados") else _corto(m.get("text"))
        eventos.append((str(m.get("created_at") or ""), "Inicio", str(m.get("customer_id") or ""), texto))
    for p in memory.list_pending():
        eventos.append((str(p.get("created_at") or ""), "Gestión", str(p.get("customer_id") or ""),
                        f"Pide {_PIDE.get(str(p.get('intent') or ''), p.get('intent') or 'revisión')}. Espera tu sí."))
    for d in memory.list_decididas(limit):
        quedo = "aprobado" if d.get("status") == "approved" else "rechazado"
        pide = _PIDE.get(str(d.get("intent") or ""), d.get("intent") or "revisión")
        eventos.append((str(d.get("decided_at") or d.get("created_at") or ""), "Fin", str(d.get("customer_id") or ""),
                        f"Pidió {pide}: {quedo}."))
    for p in memory.list_pedidos(100):
        if p.get("estado") == "entregado":
            eventos.append((str(p.get("created_at") or ""), "Fin", str(p.get("customer_id") or ""),
                            f"Pedido entregado: {p['servicio']} {kb.precio_txt(p['precio'])}."))
    eventos.sort(key=lambda e: e[0], reverse=True)

    def quien(cid: str) -> str:
        return _quien_txt(memory.get_customer(cid) or {})

    filas = "".join(
        "<tr>"
        f"<td>{_creada_cali(hora).strftime('%d/%m %H:%M') if hora else '—'}</td>"
        f"<td>{tipo}</td><td>{quien(cid)}</td><td>{html.escape(resumen)}</td>"
        "</tr>"
        for hora, tipo, cid, resumen in eventos[:limit]
    ) or "<tr><td colspan='4'>Al día. Nadie espera.</td></tr>"
    cab = "".join(f"<th>{_a(c)}</th>" for c in ("Hora Cali", "Etapa", "Cliente", "Resumen"))
    return f"<table><tr>{cab}</tr>{filas}</table>"


def _casillas(citas_hoy: list[dict], pedidos: list[dict], pendientes: list[dict]) -> tuple[str, str]:
    """Muro D: cuatro casillas del home y una ventana por casilla con sus clientes y canal.
    Reserva/Pedido = citas confirmadas de hoy / pedidos anotados hoy (sin rechazados). Gestionado = lo anotado hoy.
    En proceso = pendientes del dueño + pedidos abiertos (no entregados ni rechazados). Cerrado = entregados de hoy:
    no es un pago verificado. Canal: WhatsApp si tiene esa identidad; si no, vacío."""
    wa = memory.clientes_de_canal("whatsapp")
    hoy_vivos = [p for p in pedidos_de_hoy(pedidos) if (p.get("estado") or "anotado") != "rechazado"]
    abiertos = [p for p in pedidos if (p.get("estado") or "anotado") not in {"entregado", "rechazado"}]
    cerrados = [p for p in pedidos_de_hoy(pedidos) if p.get("estado") == "entregado"]
    suma = lambda filas: kb.precio_txt(sum(int(p["precio"]) for p in filas))

    def nombre(fila: dict) -> str:
        cid = str(fila.get("customer_id") or "")
        return html.escape(str(fila.get("name") or (memory.get_customer(cid) or {}).get("name") or "sin nombre"))

    def canal(fila: dict) -> str:
        return "WhatsApp" if str(fila.get("customer_id") or "") in wa else ""

    def pedido(p: dict) -> list[str]:
        return [nombre(p), canal(p), html.escape(f"{p['servicio']} {kb.precio_txt(p['precio'])}"),
                html.escape(str(p.get("estado") or "anotado"))]

    def cita(c: dict) -> list[str]:
        h, m = cuando_fila(c)[1:]
        return [nombre(c), canal(c), f"cita {h}:{m:02d}", "confirmada"]

    def pendiente(p: dict) -> list[str]:
        return [nombre(p), canal(p), html.escape(str(p.get("requested_action") or "")), "espera tu sí"]

    def ventana(vid: str, titulo: str, filas: list[list[str]], nota: str = "") -> str:
        cuerpo = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas) \
            or "<tr><td colspan='4'>Al día. Nadie espera.</td></tr>"
        cab = "".join(f"<th>{_a(c)}</th>" for c in ("Cliente", "Canal", "Qué", "Estado"))
        return (f"<dialog class='bloque' id='{vid}'><div class='ventana'>"
                f"<div class='bloque-cab'><div class='bloque-t'>{_a(titulo)}</div>{_CERRAR}</div>"
                f"{f'<p class=ficha>{_a(nota)}</p>' if nota else ''}"
                f"<div class='tabla'><table><tr>{cab}</tr>{cuerpo}</table></div></div></dialog>")

    casillas = [
        ("casilla-reserva", "Reserva/Pedido", f"{len(citas_hoy)}/{len(hoy_vivos)}", "citas / pedidos de hoy",
         [cita(c) for c in citas_hoy] + [pedido(p) for p in hoy_vivos], ""),
        ("casilla-gestionado", "Gestionado", f"{len(hoy_vivos)} · {suma(hoy_vivos)}", "anotado hoy, sin rechazados",
         [pedido(p) for p in hoy_vivos], ""),
        ("casilla-proceso", "En proceso", f"{len(pendientes) + len(abiertos)} · {suma(abiertos)}",
         "por aprobar y pedidos sin entregar", [pendiente(p) for p in pendientes] + [pedido(p) for p in abiertos], ""),
        ("casilla-cerrado", "Cerrado", f"{len(cerrados)} · {suma(cerrados)}", "entregados hoy",
         [pedido(p) for p in cerrados], "No es un pago verificado."),
    ]
    botones = "".join(
        f"<button class='casilla' data-abre='{vid}'><span class='casilla-t'>{_a(titulo)}</span>"
        f"<b>{html.escape(cifra)}</b><span>{_a(sub)}</span></button>"
        for vid, titulo, cifra, sub, _, _ in casillas
    )
    ventanas = "".join(ventana(vid, titulo, filas, nota) for vid, titulo, _, _, filas, nota in casillas)
    return f"<div class='casillas'>{botones}</div>", ventanas


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

    def _panel(self, aviso: str = "") -> str:
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
        # Ladrillo 7: el nombre y la fila son texto. Solo los botones Aprobar y Rechazar deciden.
        def _cliente_txt(cid: str) -> str:
            return html.escape(str((memory.get_customer(cid) or {}).get("name") or "sin nombre"))

        # Muro E: Pendientes y Decididas con las mismas columnas. Pedido = el último pedido ANOTADO del cliente.
        # Resumen = del texto del cliente y del pedido; no se inventa. Chat abre su hilo de solo lectura.
        pend_filas = memory.list_pending()
        dec_filas = memory.list_decididas(10)
        chats, hilos, hilo_de = _chats_y_hilos([str(p.get("customer_id") or "") for p in pend_filas + dec_filas])
        todos_pedidos = memory.list_pedidos(500)
        envios = memory.list_envios(500)
        ahora_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        def _fila_aprob(p: dict, ultima: str) -> str:
            cid = str(p.get("customer_id") or "")
            ped = _pedido_anotado(cid, todos_pedidos)
            ped_txt = f"{html.escape(str(ped['servicio']))} {kb.precio_txt(ped['precio'])}" if ped else "sin pedido"
            chat = (f"<button type='button' class='ir-chat' data-abre='{hilo_de[cid]}'>{_a('Chat')}</button>"
                    if cid in hilo_de else "")
            return (
                "<tr>"
                f"<td class='nombre'>{_cliente_txt(cid)}</td>"
                f"<td>{html.escape(str(p.get('event_id') or ''))}</td>"
                f"<td>{html.escape(str(p.get('intent') or ''))}</td>"
                f"<td class='pedido'>{ped_txt}</td>"
                f"<td class='resumen'>{html.escape(_resumen(str(p.get('intent') or ''), str(p.get('requested_action') or ''), ped))}</td>"
                f"<td>{chat}</td>"
                f"{ultima}</tr>"
            )

        pend = []
        for p in pend_filas:
            eid = html.escape(str(p.get("event_id") or ""))
            atrasado = _atrasado(str(p.get("created_at") or ""), ahora_utc)
            pend.append(_fila_aprob(p, (
                "<td>" + ("<span class='atrasado'>atrasado</span> " if atrasado else "")
                + f"<form method='post' action='/decidir' style='display:inline'>"
                f"<input type='hidden' name='event_id' value='{eid}'/>"
                f"<button type='submit' name='decision' value='approved'>{_a('Aprobar')}</button> "
                f"<button type='submit' name='decision' value='rejected'>{_a('Rechazar')}</button>"
                f"</form></td>"
            )))
        pendientes = "".join(pend) or "<tr><td colspan='7'>Nada por aprobar.</td></tr>"
        decididas = "".join(
            _fila_aprob(d, f"<td class='cierre'>{html.escape(_cierre(d, envios))}</td>") for d in dec_filas
        ) or "<tr><td colspan='7'>Nada decidido aún.</td></tr>"
        def _cab(*cols: str) -> str:
            return "<tr>" + "".join(f"<th>{_a(c)}</th>" for c in cols) + "</tr>"

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
        # La ficha del panel (alex_pc, canal panel) es el dueño: no sale en la lista. La ficha no se borra.
        wa = {str(u.get("customer_id")): u.get("last_in") for u in memory.list_whatsapp_customers(500)}
        internos = memory.clientes_de_canal("panel")
        cli = []
        for u in memory.list_customers(20 + len(internos)):
            cid = str(u.get("customer_id") or "")
            if cid in internos:
                continue
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
        ahora = _ahora_cali()
        hoy = ahora.date()
        citas_de_hoy = [c for c in memory.list_confirmed_reservas(500) if (w := cuando_fila(c)) and w[0] == hoy]
        citas_hoy = len(citas_de_hoy)
        pedidos = memory.list_pedidos(500)
        entregados = [p for p in pedidos_de_hoy(pedidos) if p.get("estado") == "entregado"]
        casillas, ventanas_casilla = _casillas(citas_de_hoy, pedidos, pend_filas)
        negocio = html.escape(str(kb.load_kb().get("negocio") or ""))
        punto = "<i class='punto' aria-label='hay por aprobar'></i>" if n_pend else ""
        # Muro 72: tres bloques (Día, Conversaciones, Aprobaciones), inventario abajo. Cada uno es una ventana (dialog).
        # Catálogo vive en Mi negocio; Avisos (antes Envíos) y Eventos en Registro, la puerta del operador.
        aviso_pend = f"<span class='marca'>{n_pend}</span>" if n_pend else "<span class='marca cero'>0</span>"
        cerrar = "<form method='dialog'><button class='cerrar' aria-label='Cerrar'>×</button></form>"
        return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ΛXEL panel</title>
<style>
:root{{--fondo:#0b3d2e;--caja:#134a3b;--borde:#2b5f4e;--texto:#f4efe4;--tenue:#b9c9c0;--dorado:#c9a85c;
--ok:#a8dcb0;--mal:#f2a08f;--oscuro:#0a2f24}}
*{{box-sizing:border-box}}
body{{font-family:"Segoe UI",system-ui,sans-serif;background:var(--fondo);color:var(--texto);margin:0;padding:20px 16px 200px}}
main{{max-width:720px;margin:0 auto}}
.arriba{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}}
.marca-axel{{display:flex;flex-direction:column;gap:6px}}
.marca-axel h1{{margin:0;font-size:30px;letter-spacing:.32em;font-weight:300;color:var(--texto)}}
.marca-axel h1::first-letter{{color:var(--dorado)}}
.negocio{{font-size:17px}}
.hora{{color:var(--tenue);font-size:14px;padding-top:6px}}
.casillas{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:24px 0 0}}
.casilla{{display:flex;flex-direction:column;gap:6px;align-items:flex-start;text-align:left;background:var(--caja);
border:1px solid var(--borde);border-radius:18px;padding:16px;color:var(--tenue);font:inherit;font-size:13px;min-height:44px}}
.casilla-t{{color:var(--texto);font-size:15px;font-weight:600}}
.casilla b{{font-size:30px;font-weight:300;color:var(--dorado);font-variant-numeric:tabular-nums}}
.casilla:hover,.casilla:focus-visible{{border-color:var(--dorado)}}
.tarjetas{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:24px 0 0}}
.tarjeta{{background:var(--caja);border:1px solid var(--borde);border-radius:18px;padding:16px 8px;text-align:center;color:var(--tenue);font:inherit;font-size:14px;min-height:44px}}
.tarjeta b{{display:block;font-size:40px;font-weight:300;color:var(--texto);margin-bottom:4px}}
.reporte{{grid-template-columns:repeat(4,1fr);margin:0}}
.reporte b{{font-size:26px;overflow-wrap:anywhere}}
.a{{color:var(--dorado)}}
.palabra{{white-space:nowrap}}
.atrasado{{display:inline-block;border:1px solid var(--mal);color:var(--mal);border-radius:999px;padding:1px 10px;font-size:12px}}
.aviso{{border:1px solid var(--dorado);color:var(--texto);border-radius:14px;padding:10px 14px;margin:12px 0}}
form.editar{{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 0 0}}
form.editar label{{width:100%;color:var(--tenue);font-size:14px}}
form.editar input,.tabla input{{min-width:0;padding:8px 12px;border-radius:10px;border:1px solid var(--borde);background:var(--fondo);color:var(--texto);font:inherit}}
form.editar input{{flex:1}} .tabla input{{width:7.5em}}
.sr{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}}
@media (max-width:620px){{.reporte{{grid-template-columns:repeat(2,1fr)}}}}
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
.barra{{position:fixed;left:50%;bottom:84px;transform:translateX(-50%);width:min(560px,calc(100% - 32px))}}
form.escribir{{display:flex;gap:8px;margin:0}}
.aviso-barra{{margin:4px 0 0;color:var(--tenue);font-size:12px;text-align:center}}
form.escribir input{{flex:1;min-width:0;padding:12px 16px;border-radius:999px;border:1px solid var(--borde);background:var(--caja);color:var(--texto);font:inherit}}
button{{padding:8px 16px;border-radius:999px;border:1px solid var(--borde);background:var(--caja);color:var(--texto);cursor:pointer;font:inherit}}
button:hover{{border-color:var(--dorado)}}
button[value=approved]{{background:var(--dorado);border-color:var(--dorado);color:#1c1606;font-weight:600}}
@media (max-width:520px){{.casilla b{{font-size:24px}} .tarjeta b{{font-size:32px}} dialog.bloque{{width:100%;max-height:100vh;border-radius:0}}}}
</style></head><body><main>
<header class="arriba">
<div class="marca-axel"><h1>ΛXEL</h1><span class="negocio">{negocio}</span></div>
<span class="hora">Cali {ahora.strftime('%H:%M')}</span>
</header>

{casillas}
<p class="ficha">{_a("Envíos de producto, repartidor y contra entrega: aún no")}</p>
<div class="otros">
<button class="otro" data-abre="mi-negocio">{_a("Mi negocio")}</button>
<button class="otro" data-abre="inventario">{_a("Inventario")}</button>
<button class="otro" data-abre="registro">{_a("Registro · operador")}</button>
</div>
<p class="local">panel local · solo 127.0.0.1</p>

<nav class="puertas" aria-label="Puertas">
<span class="lambda" aria-hidden="true">Λ</span>
<button data-abre="dia">{_a("Día")}</button>
<button data-abre="conversaciones">{_a("Conversaciones")}</button>
<button data-abre="aprobaciones">{_a("Aprobaciones")}{punto}</button>
</nav>

<dialog class="bloque" id="dia"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">{_a("Día")}</div>{cerrar}</div>
<h2>Reporte de hoy</h2>
<div class="tarjetas reporte">
<div class="tarjeta"><b>{citas_hoy}</b>{_a("citas hoy")}</div>
<div class="tarjeta"><b>{kb.precio_txt(anotado_hoy(pedidos))}</b>{_a("anotado, sin cobro")}</div>
<div class="tarjeta"><b>{len(entregados)}</b>{_a("entregados")} · {kb.precio_txt(sum(int(p["precio"]) for p in entregados))}</div>
<div class="tarjeta"><b>{n_pend}</b>{_a("por aprobar")}</div>
</div>
<h2>{_a("Citas")}</h2>
<div class="tabla"><table>{_cab("Cuando", "Cliente", "Qué dijo")}{tabla_citas}</table></div>
{f'<h2>{_a("Cupos de la semana")}</h2><div class="tabla">{_tabla_cupos()}</div>' if kb.agenda() else ""}
<h2>Pedidos</h2>
<div class="tabla">{_tabla_pedidos()}</div>
</div></dialog>
{ventanas_casilla}

<dialog class="bloque" id="conversaciones"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">{_a("Conversaciones")}</div>{cerrar}</div>
<h2>{_a("Chats")}</h2>
{chats}
<h2>Clientes</h2>
<div class="tabla"><table>{_cab("Nombre", "Canal", "Celular", "Última cita", "Última vez")}{tabla_cli}</table></div>
</div></dialog>
{hilos}

<dialog class="bloque" id="aprobaciones"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">{_a("Aprobaciones")} {aviso_pend}</div>{cerrar}</div>
<h2>Pendientes</h2>
<div class="tabla"><table>{_cab("Cliente", "Evento", "Intent", "Pedido", "Resumen", "Chat", "Decisión")}{pendientes}</table></div>
<h2>{_a("Decididas")}</h2>
<div class="tabla"><table>{_cab("Cliente", "Evento", "Intent", "Pedido", "Resumen", "Chat", "Cierre")}{decididas}</table></div>
<p class="ficha">{_a("AXEL no mueve dinero.")}</p>
</div></dialog>

<dialog class="bloque" id="inventario"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">{_a("Inventario")}</div>{cerrar}</div>
<h2>{_a("Servicios")}</h2>
{f'<p class="aviso" role="status">{AVISOS[aviso]}</p>' if aviso.startswith(("servicio", "precio", "stock")) and aviso in AVISOS else ""}
<div class="tabla">{_tabla_servicios()}</div>
<h2>{_a("Inventario")}</h2>
<div class="tabla">{_tabla_inventario()}</div>
</div></dialog>

<dialog class="bloque" id="mi-negocio"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">Mi negocio</div>{cerrar}</div>
<h2>{_a("Datos del negocio")}</h2>
<div class="tabla">{_tabla_catalogo()}</div>
{f'<p class="aviso" role="status">{AVISOS[aviso]}</p>' if aviso.startswith("franjas") and aviso in AVISOS else ""}
<form class="editar" method="post" action="/franjas">
<label for="franjas">{_a("Franjas: horas de 0 a 23, separadas por coma")}</label>
<input id="franjas" name="franjas" value="{html.escape(", ".join(_hhmm(f) for f in _franjas_kb()))}" inputmode="numeric"/>
<button type="submit">{_a("Guardar")}</button>
</form>
<p class="ficha">{_a("Redes: aún no")}</p>
<p class="ficha">{_a("Publicar: aún no")}</p>
<p class="ficha">{_a("Otro WhatsApp: aún no")}</p>
</div></dialog>

<dialog class="bloque" id="registro"><div class="ventana">
<div class="bloque-cab"><div class="bloque-t">{_a("Registro")}</div>{cerrar}</div>
<h2>Eventos</h2>
<div class="tabla">{_tabla_eventos()}</div>
<h2>{_a("Avisos")}</h2>
<div class="tabla">{_tabla_envios()}</div>
<h2>Últimos</h2>
<div class="tabla"><table>{_cab("Cuando", "Canal", "Agente", "Nivel", "Aprobación", "Entró", "Respondió")}{tabla}</table></div>
<p class="ficha"><b>Ficha panel:</b> {ficha_html}</p>
</div></dialog>
</main>

<div class="barra">
<form class="escribir" method="post" action="/panel">
<input name="text" placeholder="Escribe a AXEL" aria-label="Escribe a AXEL" />
<button type="submit">{_a("Enviar")}</button>
</form>
<p class="aviso-barra">Un comando de dueño puede avisar al cliente. No le escribe texto libre.</p>
</div>
<script>
document.querySelectorAll("[data-abre]").forEach(function (b) {{
  b.addEventListener("click", function () {{ document.getElementById(b.dataset.abre).showModal(); }});
}});
document.querySelectorAll("dialog").forEach(function (d) {{
  d.addEventListener("click", function (e) {{ if (e.target === d) d.close(); }});
}});
// Después de guardar, vuelve a la ventana donde estaba (#inventario, #mi-negocio) y limpia la dirección.
var volver = location.hash && document.getElementById(location.hash.slice(1));
if (volver && volver.tagName === "DIALOG") volver.showModal();
if (location.search || location.hash) history.replaceState(null, "", "/");
// Recarga cada 20 s. Espera si hay una ventana abierta o si el dueño está escribiendo, para no perderle nada.
setInterval(function () {{
  var campo = document.querySelector("form.escribir input");
  var escribiendo = campo && (campo.value || document.activeElement === campo);
  if (!document.querySelector("dialog[open]") && !escribiendo) location.reload();
}}, 20000);
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
        if urlparse(self.path).path in ("/", "/index.html"):
            aviso = (parse_qs(urlparse(self.path).query).get("aviso") or [""])[0]
            self._html(200, self._panel(aviso))
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

    def _decidir(self, event_id: str, decision: str) -> None:
        """Solo un botón decide: sin decision válida o sin pendiente, nada cambia. Va por el mismo camino que
        'aprobar N' / 'rechazar N' del dueño: aviso al cliente (queda en Avisos) y luego se resuelve."""
        if decision not in {"approved", "rejected"}:
            return
        fila = next((p for p in memory.list_pending() if str(p.get("event_id")) == event_id), None)
        if fila is None:
            return
        verbo = "aprobar" if decision == "approved" else "rechazar"
        self._run({"text": f"{verbo} {fila['n']}", "channel": "panel", "channel_user_id": "alex_pc"})

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
            self._decidir((form.get("event_id") or [""])[0], (form.get("decision") or [""])[0])
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path in ("/servicio", "/franjas"):
            # Muro C: el dueño edita desde el panel. Vuelve a la misma ventana con un aviso fijo.
            form = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
            campo = lambda k: (form.get(k) or [""])[0]
            if self.path == "/servicio":
                codigo, ventana = guardar_servicio(campo("nombre"), campo("precio"), campo("stock")), "inventario"
            else:
                codigo, ventana = guardar_franjas(campo("franjas")), "mi-negocio"
            self.send_response(303)
            self.send_header("Location", f"/?aviso={codigo}#{ventana}")
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
        try:
            # Muro G: a la hora de cierre, una vez al día, pendientes y pedidos anotados al dueño. AXEL no cobra.
            estado = enviar_alerta_cierre(memory)
            if estado:
                print("ALERTA CIERRE", estado)
        except Exception as exc:
            print("ALERTA CIERRE error:", exc)


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