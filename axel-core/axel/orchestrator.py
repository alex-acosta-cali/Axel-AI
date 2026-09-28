from __future__ import annotations

import os
import re

from axel import knowledge_base as kb_mod
from axel.agents import atencion, escalamiento, reservas
from axel.connectors.whatsapp import send_text
from axel.envelope import Envelope, now_iso
from axel.knowledge_base import load_kb, set_business_name, set_hours
from axel.memory import Memory
from axel.notify import notify_owner
from axel.permissions import classify_level, needs_customer_confirm, needs_owner_approval, reason_for
from axel.router_model import route


INTENTS = [
    ("queja", re.compile(r"queja|reclamo|molesto|pésimo|pesimo|nunca más|abogado", re.I)),
    ("reembolso", re.compile(r"reembols|rembols|devolver plata|devoluci", re.I)),
    ("cancelar", re.compile(r"cancelar (la )?cita|anular reserva", re.I)),
    ("reprogramar", re.compile(r"cambiar (la )?cita|reprogram", re.I)),
    ("mi_cita", re.compile(r"mi cita|cuando (es|queda) mi|a que hora qued|qué hora qued", re.I)),
    ("reserva", re.compile(r"reserva|agendar|cita|turno|disponib", re.I)),
    ("venta", re.compile(r"precio|cuánto|cuanto cuesta|quiero comprar|cotiz", re.I)),
    ("saludo", re.compile(r"^(hola|buenas|buen día|buenos días|hey)\b", re.I)),
    ("cierre", re.compile(r"^(gracias|graciass|listo|ok gracias|chao|adios|adiós|hasta luego|perfecto)\b", re.I)),
]


def _norm(text: str) -> str:
    raw = (text or "").lower().strip()
    table = str.maketrans("áéíóúü", "aeiouu")
    return raw.translate(table)


def classify_intent(text: str) -> str:
    raw = _norm(text)
    if not raw:
        return "pregunta"
    for name, pattern in INTENTS:
        if pattern.search(raw):
            return name
    return "pregunta"


def _digits(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


OWNER_NOMBRE = re.compile(r"^(?:axeladmin\s+)?el negocio se llama\s+(.+)$", re.I)
_HORA = r"(\d{1,2})(?::(\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?"
OWNER_HORARIO = re.compile(rf"^(?:axeladmin\s+)?abrimos de\s+{_HORA}\s+a\s+{_HORA}\s*\.?$", re.I)
ONB_HORARIO = re.compile(rf"^(?:de\s+)?{_HORA}\s+a\s+{_HORA}\s*\.?$", re.I)
ONB_START = {"configurar", "onboarding", "axeladmin configurar"}
ONB_SALIR = {"cancelar", "salir", "cancelar configuracion", "cancelar configurar"}
HORARIO_AYUDA = "Ejemplo: de 8 a 19, o de 8am a 7pm."
ONB_PREGUNTA = {
    "onb_nombre": "¿Cómo se llama el negocio?",
    "onb_rubro": "¿Cuál es el rubro? Ejemplo: barbería, cafetería, tienda.",
    "onb_agenda": "¿Agendan citas? Responde si o no.",
    "onb_horario": f"¿En qué horario abren? {HORARIO_AYUDA}",
    "onb_franjas": "¿A qué horas das citas? Ejemplo: 9 11 15",
    "onb_ubicacion": "¿Cuál es la ubicación? Ejemplo: Cra 1 #2-3 Cali",
    "onb_servicios": "Dime servicios, uno por línea: nombre precio\nEjemplo: cafe 4000\nCuando termines escribe listo.",
}
ONB_SERVICIO = re.compile(r"^(.+?)\s+\$?\s*([\d.,]+)\s*(?:pesos)?\s*\.?$", re.I)
_ADMIN = r"^(?:axeladmin\s+)?"
_PRECIO = r"\$?\s*([\d.,]+)\s*(?:pesos)?\s*\.?$"
OWNER_KB = [
    ("rubro", re.compile(_ADMIN + r"el rubro es\s+(.+)$", re.I)),
    ("agenda", re.compile(_ADMIN + r"agenda\s+(si|sí|no)\s*\.?$", re.I)),
    ("agrega", re.compile(_ADMIN + r"agrega(?:r)?\s+(?:el\s+)?servicio\s+(.+?)\s+a\s+" + _PRECIO, re.I)),
    ("precio", re.compile(_ADMIN + r"cambi(?:a|ar|o)\s+el\s+precio\s+(?:del\s+|de\s+la\s+|de\s+)?(.+?)\s+a\s+" + _PRECIO, re.I)),
    ("quita", re.compile(_ADMIN + r"quita(?:r)?\s+(?:el\s+)?servicio\s+(.+?)\s*\.?$", re.I)),
    ("ubicacion", re.compile(_ADMIN + r"la\s+ubicaci[oó]n\s+es\s+(.+?)\s*$", re.I)),
    ("agrega_faq", re.compile(_ADMIN + r"agrega(?:r)?\s+(?:la\s+)?pregunta\s+(.+?)(?:\s+respuesta\s*:?\s*(.*?))?\s*$", re.I)),
    ("quita_faq", re.compile(_ADMIN + r"quita(?:r)?\s+(?:la\s+)?pregunta\s+(.+?)\s*\.?$", re.I)),
    ("franjas", re.compile(_ADMIN + r"franjas\s+([\d:\s,y]+?)\s*\.?$", re.I)),
]
PREGUNTA_NOMBRE = "¿Cómo quieres que te llame?"
PREGUNTA_NOMBRE_VIEJA = "¿Cómo te llamas?"
NOMBRE_CORTO = re.compile(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ ]{2,40}")
NO_ES_NOMBRE = {"si", "no", "ok", "okay", "dale", "bien", "nada", "claro", "vale"}


def _nombre_usable(nombre: str | None) -> bool:
    """Al menos 2 letras. Emojis, símbolos o una sola letra no cuentan."""
    return len(re.findall(r"[a-záéíóúüñ]", (nombre or "").lower())) >= 2


def _hora(h: str, m: str | None, ampm: str | None) -> tuple[int, int] | None:
    hora, minuto = int(h), int(m or 0)
    suf = re.sub(r"[\s.]", "", ampm or "").lower()
    if suf:
        if not 1 <= hora <= 12:
            return None
        hora = hora % 12 + (12 if suf == "pm" else 0)
    if hora > 23 or minuto > 59:
        return None
    return hora, minuto


def _guardar_horario(m: re.Match) -> str:
    abre = _hora(*m.group(1, 2, 3))
    cierra = _hora(*m.group(4, 5, 6))
    if abre is None or cierra is None or cierra <= abre:
        return ""
    return set_hours(f"{abre[0]}:{abre[1]:02d}", f"{cierra[0]}:{cierra[1]:02d}")


def _comando_kb(text: str) -> tuple[str, re.Match] | None:
    for nombre, patron in OWNER_KB:
        m = patron.match(text)
        if m:
            return nombre, m
    return None


def _pesos(raw: str) -> int:
    digitos = re.sub(r"\D", "", raw or "")
    return int(digitos) if digitos else 0


def _editar_kb(cual: str, m: re.Match) -> str:
    """Aplica un comando del dueño sobre rubro, agenda, servicios o franjas. Devuelve lo que quedó."""
    if cual == "rubro":
        rubro = kb_mod.set_rubro(m.group(1))
        return f"Listo, rubro: {rubro}." if rubro else "No entendí el rubro."
    if cual == "agenda":
        activa = _norm(m.group(1)) == "si"
        kb_mod.set_agenda(activa)
        return "Listo, agenda activa." if activa else "Listo, agenda apagada. No ofrezco citas."
    if cual == "agrega":
        precio = _pesos(m.group(2))
        if precio <= 0:
            return "No entendí el precio."
        if kb_mod.buscar_servicio(m.group(1)):
            nombre = kb_mod.nombre_servicio(m.group(1))
            return f"Ya existe {nombre}. Para cambiarlo: cambia el precio de {nombre} a N."
        nombre = kb_mod.add_servicio(m.group(1), precio)
        return f"Listo, servicio {nombre} a {kb_mod.precio_txt(precio)}." if nombre else "No entendí el servicio."
    if cual == "precio":
        precio = _pesos(m.group(2))
        s = kb_mod.buscar_servicio(m.group(1))
        if not s:
            return f"No tengo el servicio {kb_mod.nombre_servicio(m.group(1))}."
        if precio <= 0:
            return "No entendí el precio."
        return f"Listo, {s['nombre']} a {kb_mod.set_price(str(s['nombre']), str(precio))}."
    if cual == "quita":
        nombre = kb_mod.nombre_servicio(m.group(1))
        return f"Listo, quité {nombre}." if kb_mod.remove_servicio(nombre) else f"No tengo el servicio {nombre}."
    if cual == "ubicacion":
        ubicacion = kb_mod.set_ubicacion(m.group(1))
        return f"Listo, ubicación: {ubicacion}" if ubicacion else "No entendí la ubicación."
    if cual == "agrega_faq":
        respuesta = (m.group(2) or "").strip()
        if not respuesta:
            return "Falta la respuesta. Ejemplo: agrega pregunta parqueadero respuesta Hay parqueadero frente al local"
        if "$" in respuesta:
            return "Los precios van en servicios: agrega servicio X a N."
        clave = kb_mod.add_faq(m.group(1), respuesta)
        return f"Listo, pregunta {clave}: {respuesta}" if clave else "No entendí la pregunta."
    if cual == "quita_faq":
        clave = kb_mod.nombre_servicio(m.group(1))
        return f"Listo, quité la pregunta {clave}." if kb_mod.remove_faq(clave) else f"No tengo la pregunta {clave}."
    guardado = _guardar_franjas(m.group(1))
    return f"Listo, {guardado}" if guardado else "No entendí las franjas. Ejemplo: franjas 8 12 16"


def _guardar_franjas(raw: str) -> str:
    """'franjas: 8:00, 12:00.' con aviso si alguna queda fuera del horario. '' si no se entienden."""
    horas = []
    for h, mi in re.findall(r"(\d{1,2})(?::(\d{2}))?", raw or ""):
        if int(h) > 23 or int(mi or 0) > 59:
            return ""
        horas.append((int(h), int(mi or 0)))
    if not horas:
        return ""
    kb_mod.set_franjas(horas)
    abre, cierra = kb_mod.get_hours()
    txt = ", ".join(f"{h}:{mi:02d}" for h, mi in sorted(set(horas)))
    fuera = [f"{h}:{mi:02d}" for h, mi in sorted(set(horas)) if not abre <= (h, mi) < cierra]
    aviso = f" Fuera del horario, no se ofrecen: {', '.join(fuera)}." if fuera else ""
    return f"franjas: {txt}.{aviso}"


def _es_dueno(env: Envelope) -> bool:
    """Dueño = canal panel, o WhatsApp desde el número WA_OWNER_PHONE."""
    if env.channel == "panel":
        return True
    if env.channel != "whatsapp":
        return False
    owner = _digits(os.getenv("WA_OWNER_PHONE") or "")
    incoming = _digits(env.channel_user_id or "")
    if len(owner) < 10 or len(incoming) < 10:
        return False
    return owner[-10:] == incoming[-10:]


def _catalogo() -> str:
    datos = load_kb()
    abre, cierra = kb_mod.get_hours()
    franjas = reservas._franjas_kb()
    fuera = [reservas._hhmm(f) for f in franjas if not abre <= f < cierra]
    franjas_txt = ", ".join(reservas._hhmm(f) for f in franjas) or "ninguna"
    if fuera:
        franjas_txt += f" (fuera de horario: {', '.join(fuera)})"
    servicios = kb_mod.servicios()
    lineas = [f"- {s['nombre']} {kb_mod.precio_txt(s.get('precio') or 0)}" for s in servicios]
    return "\n".join(
        [
            "Catálogo:",
            f"Rubro: {datos.get('rubro') or '—'}",
            f"Agenda: {'sí' if kb_mod.agenda() else 'no'}",
            f"Horario: {reservas._hhmm(abre)} a {reservas._hhmm(cierra)}",
            f"Franjas: {franjas_txt}",
            "Servicios:" if lineas else "Servicios: ninguno",
            *lineas,
        ]
    )


def _servicios_configurar(env: Envelope, memory: Memory, text: str) -> str:
    """Una línea por servicio: 'nombre precio'. 'listo' cierra el asistente con el catálogo."""
    if _norm(text).strip(" .!") == "listo":
        memory.set_open_task(env.customer_id or "", "")
        return f"Configuración terminada.\n{_catalogo()}"
    ok, malas = [], []
    for linea in (text or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        m = ONB_SERVICIO.match(linea)
        precio = _pesos(m.group(2)) if m else 0
        nombre = kb_mod.nombre_servicio(m.group(1)) if m else ""
        existe = kb_mod.buscar_servicio(nombre) if nombre else None
        if precio <= 0:
            malas.append(linea)
        elif existe:
            kb_mod.set_price(str(existe["nombre"]), str(precio))
            ok.append(f"{existe['nombre']} {kb_mod.precio_txt(precio)}")
        elif kb_mod.add_servicio(nombre, precio):
            ok.append(f"{nombre} {kb_mod.precio_txt(precio)}")
        else:
            malas.append(linea)
    partes = []
    if ok:
        partes.append(f"Guardé: {', '.join(ok)}.")
    if malas:
        partes.append(f"No entendí: {' | '.join(malas)}.")
    partes.append("Escribe más servicios o listo para terminar.")
    return " ".join(partes)


def _paso_configurar(env: Envelope, memory: Memory, paso: str, text: str) -> str:
    """Guarda la respuesta del paso y pregunta el siguiente. Si no la entiende, repite la misma pregunta."""
    guardado, siguiente = "", ""
    if paso == "onb_nombre":
        guardado, siguiente = set_business_name(text), "onb_rubro"
    elif paso == "onb_rubro":
        guardado, siguiente = kb_mod.set_rubro(text), "onb_agenda"
    elif paso == "onb_agenda":
        resp = _norm(text).strip(" .!")
        if resp in {"si", "no"}:
            kb_mod.set_agenda(resp == "si")
            guardado, siguiente = f"agenda {resp}", "onb_horario"
    elif paso == "onb_horario":
        libre = ONB_HORARIO.match(text)
        guardado = _guardar_horario(libre) if libre else ""
        siguiente = "onb_franjas" if kb_mod.agenda() else "onb_ubicacion"
    elif paso == "onb_franjas":
        guardado, siguiente = _guardar_franjas(text), "onb_ubicacion"
    elif paso == "onb_ubicacion":
        guardado, siguiente = kb_mod.set_ubicacion(text), "onb_servicios"
    elif paso == "onb_servicios":
        return _servicios_configurar(env, memory, text)
    if not guardado:
        return f"No entendí. {ONB_PREGUNTA[paso]}"
    memory.set_open_task(env.customer_id or "", siguiente)
    return f"Guardé {guardado.rstrip('.')}. {ONB_PREGUNTA[siguiente]}"


def _try_owner_setup(env: Envelope, memory: Memory) -> bool:
    """Nombre y horario del negocio: comandos directos y onboarding guiado."""
    text = (env.text or "").strip()
    t = _norm(text)
    nombre = OWNER_NOMBRE.match(text)
    horario = OWNER_HORARIO.match(text)
    comando = _comando_kb(text)
    if not _es_dueno(env):
        if not (nombre or horario or comando):
            return False
        env.reply_text = "Eso solo lo cambia el dueño."
    else:
        paso = memory.get_open_task(env.customer_id or "")
        if comando:
            env.reply_text = _editar_kb(*comando)
        elif nombre:
            guardado = set_business_name(nombre.group(1))
            env.reply_text = (
                f"Listo, el negocio quedó como {guardado}." if guardado else "No entendí el nombre del negocio."
            )
        elif horario:
            guardado = _guardar_horario(horario)
            env.reply_text = (
                f"Listo, horario guardado: {guardado}." if guardado else f"No entendí el horario. {HORARIO_AYUDA}"
            )
        elif t in ONB_START:
            memory.set_open_task(env.customer_id or "", "onb_nombre")
            env.reply_text = f"Configuremos el negocio. {ONB_PREGUNTA['onb_nombre']} Para salir: cancelar configurar."
        elif paso.startswith("onb_") and t.strip(" .!") in ONB_SALIR:
            memory.set_open_task(env.customer_id or "", "")
            env.reply_text = "Salí de la configuración. Lo que ya respondiste quedó guardado."
        elif paso in ONB_PREGUNTA:
            env.reply_text = _paso_configurar(env, memory, paso, text)
        else:
            return False
    env.intent = "admin_kb"
    env.agent = "atencion"
    env.supervision_level = 1
    env.result = "ok"
    env.approval_status = "na"
    env.why = "configuracion del negocio (KB)"
    return True


def pedidos_filas(memory: Memory, limit: int = 15) -> list[tuple[str, str, str]]:
    """(hora Cali, nombre o celular, 'servicio $N') de los últimos pedidos. Solo para el dueño."""
    filas = []
    for p in memory.list_pedidos(limit):
        pedido = re.sub(r"^Pedido piloto\s+|\s*\(sin cobro\)$", "", str(p.get("note") or ""))
        hora = reservas._creada_cali(str(p.get("created_at") or "")).strftime("%d/%m %H:%M")
        filas.append((hora, str(p.get("name") or p.get("phone") or "sin nombre"), pedido))
    return filas


def _try_owner_decision(env: Envelope, memory: Memory) -> bool:
    if not _es_dueno(env):
        return False
    owner = _digits(os.getenv("WA_OWNER_PHONE") or "")
    t = _norm(env.text)
    if t in {"estado", "axeladmin estado"}:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        n_cli = len(memory.list_customers(50))
        n_pend = len(memory.list_pending())
        n_citas = len(memory.list_confirmed_reservas(50))
        env.reply_text = (
            f"Estado piloto: {n_cli} cliente(s), "
            f"{n_citas} cita(s) confirmada(s), "
            f"{n_pend} pendiente(s) del dueño."
        )
        env.result = "ok"
        env.approval_status = "na"
        return True    
    if t in {"ayuda", "comandos", "menu dueño", "menu dueno"}:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        env.reply_text = (
            "Comandos dueño: estado, limpiar, pendientes, citas, clientes, pedidos, catalogo, "
            "aceptar/aprobar, rechazo/rechazar, ayuda, "
            "configurar, el negocio se llama NOMBRE, abrimos de H1 a H2, "
            "el rubro es X, agenda si/no, agrega servicio X a N, "
            "cambia el precio de X a N, quita servicio X, franjas 8 12 16, "
            "agrega pregunta X respuesta Y, quita pregunta X, la ubicacion es X."
        )
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t in {"limpiar", "axeladmin limpiar"}:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        n = memory.purge_ghost_customers()
        env.reply_text = f"Eliminé {n} cliente(s) fantasma."
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t in {"pendientes", "pendiente"}:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        pend = memory.list_pending()
        if not pend:
            env.reply_text = "No hay pendientes."
        else:
            lineas = [f"- {p.get('intent')}: {p.get('requested_action')}" for p in pend[:5]]
            env.reply_text = "Pendientes:\n" + "\n".join(lineas)
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t in {"recordatorios", "recordatorio", "citas"}:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        citas = memory.list_confirmed_reservas(8)
        if not citas:
            env.reply_text = "No hay citas confirmadas."
        else:
            lineas = []
            for c in citas:
                cli = memory.get_customer(str(c.get("customer_id") or "")) or {}
                franja = reservas.franja_de(str(c.get("summary") or ""), str(c.get("created_at") or ""))
                lineas.append(f"- {franja} · {c.get('name') or 'sin nombre'} · {cli.get('phone') or 'sin teléfono'}")
            env.reply_text = "Citas confirmadas:\n" + "\n".join(lineas)
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t == "catalogo":
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        env.reply_text = _catalogo()
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t == "pedidos":
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        lineas = [f"- {hora} · {quien} · {pedido}" for hora, quien, pedido in pedidos_filas(memory)]
        env.reply_text = "Pedidos:\n" + "\n".join(lineas) if lineas else "No hay pedidos."
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t == "clientes":
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        lineas = []
        for u in memory.list_whatsapp_customers(15):
            ult = memory.last_reserva(str(u.get("customer_id") or ""))
            cita = reservas.franja_de(str(ult.get("summary") or ""), str(ult.get("created_at") or "")) if ult else "—"
            lineas.append(f"- {u.get('name') or '—'} · {u.get('phone') or '—'} · {cita}")
        env.reply_text = "Clientes WhatsApp:\n" + "\n".join(lineas) if lineas else "No hay clientes de WhatsApp."
        env.result = "ok"
        env.approval_status = "na"
        return True
    no = any(k in t for k in ("rechazar", "rechazo", "niego", "denegar", "denegado", "no autorizo", "no acepto"))
    si = any(k in t for k in ("aprobar", "aceptar", "acepto", "autorizo", "autorizar", "afirmativo", "de acuerdo"))
    if no:
        si = False
    if not si and not no:
        return False
    env.intent = "admin"
    env.agent = "escalamiento"
    env.supervision_level = 1
    pend = memory.list_pending()
    if not pend:
        env.reply_text = "No hay decisiones pendientes."
        env.result = "ok"
        env.approval_status = "na"
        return True
    row = pend[0]
    decision = "approved" if si else "rejected"
    memory.resolve_pending(str(row.get("event_id") or ""), decision)
    env.reply_text = (
        f"Quedó {decision} el caso {row.get('event_id')} "
        f"({row.get('intent')})."
    )
    cli = memory.get_customer(str(row.get("customer_id") or "")) or {}
    destino = _digits(str(cli.get("phone") or ""))
    if destino and destino != owner:
        if si:
            send_text(destino, "El dueño ya revisó tu caso y lo aprobó. Te escribimos si falta algo.")
        else:
            send_text(destino, "El dueño revisó tu caso y por ahora no se puede. Si quieres, lo vemos de otra forma.")
    env.approval_status = decision
    env.result = "ok"
    return True


def pick_agent(intent: str) -> str:
    if intent in {"reserva", "reprogramar", "cancelar", "mi_cita"}:
        return "reservas"
    if intent in {"queja", "reembolso", "descuento_grande", "admin"}:
        return "escalamiento"
    if intent == "venta":
        return "atencion"
    return "atencion"


def process(env: Envelope, memory: Memory) -> Envelope:
    if not _nombre_usable(env.name):
        env.name = None
    ident = memory.identify_customer(
        business_id=env.business_id,
        channel=env.channel,
        channel_user_id=env.channel_user_id,
        phone=env.phone,
        email=env.email,
        name=env.name,
    )
    env.customer_id = ident["customer"]["customer_id"]
    if not env.name and _nombre_usable(ident["customer"].get("name")):
        env.name = ident["customer"].get("name")
    if not env.phone:
        env.phone = ident["customer"].get("phone")
    if not env.email:
        env.email = ident["customer"].get("email")
    history = memory.last_summaries(env.customer_id)
    env.known_context = [
        f"{h.get('channel')}:{h.get('intent')}:{h.get('summary')}" for h in history
    ]
    env.context_refs = [f"crm:{env.customer_id}"] + [f"hist:{h['event_id']}" for h in history]
    env.payload["identities"] = ident["identities"]
    env.payload["history"] = history
    env.payload["es_dueno"] = _es_dueno(env)

    if _try_owner_setup(env, memory) or _try_owner_decision(env, memory):
        memory.save_turn(
            customer_id=env.customer_id,
            event_id=env.event_id,
            channel=env.channel,
            intent=env.intent or "admin",
            text=env.text or "",
            reply=env.reply_text or "",
            result=env.result or "ok",
        )
        memory.write_audit(
            {
                "event_id": env.event_id,
                "received_at": env.received_at,
                "finished_at": now_iso(),
                "channel": env.channel,
                "customer_id": env.customer_id,
                "agent": env.agent,
                "model": env.model,
                "supervision_level": env.supervision_level,
                "approval_status": env.approval_status,
                "input_summary": (env.text or "")[:240],
                "output_summary": (env.reply_text or "")[:240],
                "result": env.result,
                "error": env.error,
                "why": env.why or "decision del dueno por WhatsApp",
                "data_used": ",".join(env.context_refs),
            }
        )
        return env

    env.intent = classify_intent(env.text)
    if (env.text or "").strip().upper() == "AXELADMIN ESTADO" and env.channel in {"panel", "test"}:
        n_cli = len(memory.list_customers(50))
        n_pend = len(memory.list_pending())
        n_citas = len(memory.list_confirmed_reservas(50))
        env.intent = "admin_kb"
        env.reply_text = (
            f"Estado piloto: {n_cli} cliente(s), "
            f"{n_citas} cita(s) confirmada(s), "
            f"{n_pend} pendiente(s) del dueño."
        )    
    if (env.text or "").strip().upper() == "AXELADMIN LIMPIAR" and env.channel in {"panel", "test"}:
        n = memory.purge_ghost_customers()
        env.intent = "admin_kb"
        env.reply_text = f"Eliminé {n} cliente(s) fantasma. Alex no se toca."
    llamado = re.search(r"(?:me llamo|mi nombre es)\s+([a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{2,30})", env.text or "", re.I)
    if llamado:
        nombre = llamado.group(1).strip().title()
        memory.set_customer_name(env.customer_id, nombre)
        env.name = nombre
        env.intent = "datos"
    pedir_nombre = env.channel == "whatsapp" and not env.payload["es_dueno"] and not env.name
    if pedir_nombre and memory.last_reply(env.customer_id).endswith((PREGUNTA_NOMBRE, PREGUNTA_NOMBRE_VIEJA)):
        candidato = (env.text or "").strip().rstrip(".!")
        if (
            NOMBRE_CORTO.fullmatch(candidato)
            and _nombre_usable(candidato)
            and len(candidato.split()) <= 4
            and env.intent == "pregunta"
            and _norm(candidato) not in NO_ES_NOMBRE
        ):
            nombre = " ".join(candidato.split()).title()[:40]
            memory.set_customer_name(env.customer_id, nombre)
            env.name = nombre
            env.intent = "datos"
    tel = re.search(
        r"(?:mi celular|mi telefono|mi teléfono|celular|whatsapp|el numero|el número)?\D*((?:3\d{9})|(?:\d{10}))",
        env.text or "",
        re.I,
    )
    if tel and env.intent in {"pregunta", "saludo", "datos"}:
        numero = tel.group(1)
        memory.set_customer_phone(env.customer_id, numero)
        env.phone = numero[-10:]
        env.intent = "datos"
    mail = re.search(
        r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
        env.text or "",
        re.I,
    )
    if mail and env.intent in {"pregunta", "saludo", "datos"}:
        correo = mail.group(1).lower()
        memory.set_customer_email(env.customer_id, correo)
        env.email = correo
        env.intent = "datos"
    nota = re.search(r"^(?:anota que|anota:)\s+(.+)$", (env.text or "").strip(), re.I)
    if nota and env.customer_id:
        texto = nota.group(1).strip()[:240]
        memory.add_note(env.customer_id, texto)
        env.intent = "nota"
        env.reply_text = f"Anoté en tu ficha: {texto}"
    open_task = memory.get_open_task(env.customer_id)
    if open_task == "reserva" and env.intent in {"pregunta", "saludo"}:
        env.intent = "reserva"
    if open_task == "reprogramar" and env.intent in {"pregunta", "saludo", "reserva"}:
        env.intent = "reprogramar"
    if open_task == "oferta_cita" and env.intent in {"pregunta", "saludo", "venta"}:
        if re.search(r"^(si|sí|dale|ok|okay|va|claro|reserv)", _norm(env.text or "")):
            env.intent = "reserva"
        elif re.search(r"manana|mañana|lunes|martes|miercoles|jueves|viernes|sabado|\d", _norm(env.text or "")):
            env.intent = "reserva"
        elif re.search(r"^(no|despues|después|ahora no)", _norm(env.text or "")):
            memory.set_open_task(env.customer_id, "")
            env.intent = "pregunta"
    env.agent = pick_agent(env.intent)
    env.supervision_level = classify_level(env.intent)
    env.why = reason_for(env.intent or "", env.supervision_level)

    decision = route(env.intent)
    env.model = decision.model
    env.model_reason = decision.reason

    if needs_owner_approval(env.supervision_level):
        env = escalamiento.handle(env)
        notify_owner(env, memory)
    elif env.agent == "reservas" or needs_customer_confirm(env.supervision_level):
        env = reservas.handle(env, memory)
    else:
        env = atencion.handle(env, memory)
        low = (env.reply_text or "").lower()
        if "reserve un cupo" in low or "te reserve" in low or "agendarte para mañana" in low:
            memory.set_open_task(env.customer_id, "oferta_cita")

    if env.result is None:
        env.result = "ok"

    if (
        pedir_nombre
        and not env.name
        and env.intent in {"saludo", "pregunta"}
        and not memory.replied_with(env.customer_id, PREGUNTA_NOMBRE)
        and not memory.replied_with(env.customer_id, PREGUNTA_NOMBRE_VIEJA)
    ):
        env.reply_text = f"{env.reply_text or ''} {PREGUNTA_NOMBRE}".strip()

    if env.intent == "reserva" and env.result == "pending":
        memory.set_open_task(env.customer_id, "reserva")
    elif env.intent == "reprogramar" and env.result == "pending":
        memory.set_open_task(env.customer_id, "reprogramar")
    elif env.intent in {"reserva", "reprogramar"} and env.result == "ok":
        memory.set_open_task(env.customer_id, "")
    elif env.intent in {"reembolso", "cancelar"}:
        memory.set_open_task(env.customer_id, "")

    memory.save_turn(
        customer_id=env.customer_id,
        event_id=env.event_id,
        channel=env.channel,
        intent=env.intent or "",
        text=env.text or "",
        reply=env.reply_text or "",
        result=env.result or "",
    )
    memory.write_audit(
        {
            "event_id": env.event_id,
            "received_at": env.received_at,
            "finished_at": now_iso(),
            "channel": env.channel,
            "customer_id": env.customer_id,
            "agent": env.agent,
            "model": env.model,
            "supervision_level": env.supervision_level,
            "approval_status": env.approval_status,
            "input_summary": (env.text or "")[:240],
            "output_summary": (env.reply_text or "")[:240],
            "result": env.result,
            "error": env.error,
            "why": env.why,
            "data_used": ",".join(env.context_refs),
        }
    )
    return env