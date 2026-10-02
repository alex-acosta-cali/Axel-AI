from __future__ import annotations

import os
import re
from pathlib import Path

from axel import knowledge_base as kb_mod
from axel import notify
from axel.agents import atencion, escalamiento, reservas
from axel.envelope import Envelope, now_iso
from axel.knowledge_base import load_kb, set_business_name, set_hours
from axel.memory import Memory
from axel.notify import notify_owner
from axel.permissions import classify_level, needs_customer_confirm, needs_owner_approval, reason_for
from axel.router_model import route


INTENTS = [
    ("borrar_datos", re.compile(r"\b(borr|elimin)\w*\s+(mis|mi)\s+datos", re.I)),
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


# "cancelar la mesa", "reprogramar turno": verbo + (artículo) + palabra.
_CAMBIO_AGENDA = re.compile(r"\b(cancelar|anular|reprogramar|cambiar)\s+(la\s+|el\s+|mi\s+)?([a-zñ]+)")
_NO_ES_AGENDA = {"cancelar", "reprogramar", "reserva"}


def classify_intent(text: str) -> str:
    raw = _norm(text)
    if not raw:
        return "pregunta"
    cambio = _CAMBIO_AGENDA.search(raw)
    if cambio:
        palabras = {"cita"} | {_norm(p) for p in kb_mod.agenda_palabras()}
        if cambio.group(3) in palabras:
            return "cancelar" if cambio.group(1) in {"cancelar", "anular"} else "reprogramar"
        if cambio.group(2):
            # "cancelar el pedido": la palabra no es de agenda; no toca citas ni abre reserva.
            return next(
                (n for n, p in INTENTS if n not in _NO_ES_AGENDA and p.search(raw)), "pregunta"
            )
    # "mis citas", "mi turno": el cliente pregunta por sus reservas.
    mia = re.search(r"\bmis?\s+([a-zñ]+)", raw)
    if mia and (
        mia.group(1) in {"cita", "citas"}
        or mia.group(1) in {w for p in kb_mod.agenda_palabras() for w in (_norm(p), _norm(p) + "s")}
    ):
        return "mi_cita"
    intent = next((name for name, pattern in INTENTS if pattern.search(raw)), "pregunta")
    # Palabras de agenda del negocio ("mesa", "turno"): abren la reserva. Sin agenda, reservas dice que no agenda.
    if intent in {"pregunta", "saludo"} and any(
        re.search(rf"\b{re.escape(_norm(p))}\b", raw) for p in kb_mod.agenda_palabras()
    ):
        return "reserva"
    return intent


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
    "onb_reemplazo": "Ya hay servicios guardados. ¿Los reemplazo o sumo los nuevos? Responde reemplazar o sumar.",
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
    ("tono", re.compile(_ADMIN + r"tono\s+(formal|cercano)\s*\.?$", re.I)),
    ("stock", re.compile(_ADMIN + r"stock\s+(?:de\s+|del\s+)?(.+?)\s+(\d+)\s*\.?$", re.I)),
    ("quita", re.compile(_ADMIN + r"quita(?:r)?\s+(?:el\s+)?servicio\s+(.+?)\s*\.?$", re.I)),
    ("ubicacion", re.compile(_ADMIN + r"la\s+ubicaci[oó]n\s+es\s+(.+?)\s*$", re.I)),
    ("agrega_faq", re.compile(_ADMIN + r"agrega(?:r)?\s+(?:la\s+)?pregunta\s+(.+?)(?:\s+respuesta\s*:?\s*(.*?))?\s*$", re.I)),
    ("quita_faq", re.compile(_ADMIN + r"quita(?:r)?\s+(?:la\s+)?pregunta\s+(.+?)\s*\.?$", re.I)),
    ("franjas", re.compile(_ADMIN + r"franjas\s+([\d:\s,y]+?)\s*\.?$", re.I)),
    ("politica", re.compile(_ADMIN + r"pol[ií]tica\s+(?:de\s+)?(cancelaci[oó]n|garant[ií]a)\s*:?\s*(.*?)\s*$", re.I)),
    ("agenda_palabras", re.compile(_ADMIN + r"agenda\s+palabras\s*:?\s*(.*?)\s*$", re.I)),
    ("producto", re.compile(_ADMIN + r"producto\s+([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\.?$", re.I)),
    ("proveedor", re.compile(_ADMIN + r"contacto\s+(?:del\s+)?proveedor\s*:?\s*(.+?)\s*\.?$", re.I)),
]
PREGUNTA_NOMBRE = "¿Cómo quieres que te llame?"
PREGUNTA_NOMBRE_VIEJA = "¿Cómo te llamas?"
PREGUNTA_NOMBRE_FORMAL = "¿Cómo quiere que le llame?"
AVISO_DATOS = "Tus datos (nombre y celular) quedan en la ficha de este negocio. Escribe borrar mis datos y el dueño lo revisa."
AVISO_DATOS_FORMAL = "Sus datos (nombre y celular) quedan en la ficha de este negocio. Escriba borrar mis datos y el dueño lo revisa."
PREGUNTAS_NOMBRE = (PREGUNTA_NOMBRE, PREGUNTA_NOMBRE_VIEJA, PREGUNTA_NOMBRE_FORMAL)
NOMBRE_CORTO = re.compile(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ ]{2,40}")
NO_ES_NOMBRE = {"si", "no", "ok", "okay", "dale", "bien", "nada", "claro", "vale"}
# Si la respuesta empieza así, es una pregunta, un comando o una acción de agenda, no un nombre.
NO_EMPIEZA_NOMBRE = {
    "donde", "cual", "que", "cuanto", "cuando", "quiero", "hola", "precios",
    "cancelar", "reprogramar", "anular", "pedido", "pedidos", "reporte", "catalogo", "citas", "cita",
    "reserva", "turno", "mesa", "horario", "ayuda", "aprobar", "aceptar", "rechazar", "limpiar",
    "configurar", "clientes", "ficha", "envios", "inventario",
}
# "mi" suelto sí puede ser nombre ("Mi Leidy"); estas frases no.
NO_EMPIEZA_NOMBRE_FRASES = {"mi ficha", "mis citas", "mi cita", "mi reserva", "mi turno", "mi pedido", "mis pedidos"}


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
    if cual == "tono":
        tono = kb_mod.set_tono(m.group(1))
        return f"Listo, tono: {tono} ({'usted' if tono == 'formal' else 'tú'})."
    if cual == "stock":
        s = kb_mod.buscar_servicio(m.group(1))
        if not s:
            return f"No tengo el servicio {kb_mod.nombre_servicio(m.group(1))}."
        cantidad = int(m.group(2))
        kb_mod.set_stock(str(s["nombre"]), cantidad)
        return f"Listo, {s['nombre']}: stock {cantidad}." + (" Queda agotado: no se vende." if cantidad == 0 else "")
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
    if cual == "politica":
        clave = _norm(m.group(1))
        texto = kb_mod.set_politica(clave, m.group(2))
        if not texto:
            ejemplo = "Puedes cancelar hasta 1 hora antes" if clave == "cancelacion" else "7 días si el servicio no quedó bien"
            return f"Falta el texto. Ejemplo: politica {clave} {ejemplo}"
        return f"Listo, política de {clave}: {texto}"
    if cual == "agenda_palabras":
        palabras = kb_mod.set_agenda_palabras(m.group(1))
        if not palabras:
            return "Faltan las palabras. Ejemplo: agenda palabras cita reserva mesa turno"
        return f"Listo, palabras de agenda: {', '.join(palabras)}."
    if cual == "producto":
        precio = _pesos(m.group(3))
        if precio <= 0:
            return "No entendí el precio."
        p = kb_mod.set_producto(m.group(1), m.group(2), precio, int(m.group(4)))
        if not p:
            return "No entendí el producto. Ejemplo: producto CAF01 | cafe molido | 12000 | 30"
        return f"Listo, producto {p['codigo']} {p['nombre']} {kb_mod.precio_txt(p['precio'])} · stock {p['stock']}."
    if cual == "proveedor":
        numero = kb_mod.set_proveedor_contacto(m.group(1))
        if not numero:
            return "No entendí el número. Ejemplo: contacto proveedor 3001234567"
        return f"Listo, contacto proveedor: {numero}. AXEL no le escribe."
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
    lineas = [
        f"- {s['nombre']} {kb_mod.precio_txt(s.get('precio') or 0)}"
        + (f" · stock {s['stock']}{' (agotado)' if kb_mod.agotado(s) else ''}" if "stock" in s else "")
        for s in servicios
    ]
    return "\n".join(
        [
            "Catálogo:",
            f"Rubro: {datos.get('rubro') or '—'}",
            f"Agenda: {'sí' if kb_mod.agenda() else 'no'}",
            f"Palabras de agenda: {', '.join(kb_mod.agenda_palabras()) or 'ninguna'}",
            f"Tono: {kb_mod.tono()}",
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
        guardado = kb_mod.set_ubicacion(text)
        siguiente = "onb_reemplazo" if kb_mod.servicios() else "onb_servicios"
    elif paso == "onb_reemplazo":
        resp = _norm(text).strip(" .!")
        if resp in {"reemplazar", "reemplazo", "reemplazalos"}:
            kb_mod.vaciar_servicios()
            memory.set_open_task(env.customer_id or "", "onb_servicios")
            return f"Borré los servicios viejos. {ONB_PREGUNTA['onb_servicios']}"
        if resp in {"sumar", "sumo", "sumalos"}:
            memory.set_open_task(env.customer_id or "", "onb_servicios")
            return f"Dejo los servicios que hay. {ONB_PREGUNTA['onb_servicios']}"
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
    elif env.business_id != "biz_default" and (nombre or horario or comando or t in ONB_START):
        # Muro 36: solo existe la KB de biz_default. Otro id no escribe.
        env.reply_text = "Este negocio aún no tiene base propia. No guardé nada."
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


def pedidos_filas(memory: Memory, limit: int = 15) -> list[tuple[str, str, str, str]]:
    """(hora Cali, nombre o celular, 'servicio $N', anotado/entregado) de los últimos pedidos. Solo para el dueño."""
    filas = []
    for p in memory.list_pedidos(limit):
        pedido = f"#{p['pedido_id']} {p['servicio']} {kb_mod.precio_txt(p['precio'])}"
        hora = reservas._creada_cali(str(p.get("created_at") or "")).strftime("%d/%m %H:%M")
        filas.append((hora, str(p.get("name") or p.get("phone") or "sin nombre"), pedido, str(p.get("estado") or "anotado")))
    return filas


PEDIDO_LISTO_AYUDA = "Escribe pedido listo NOMBRE o las últimas 4 cifras del celular."
PEDIDO_FALTA_PAGO = "Falta marcarlo pagado."
PEDIDO_FALTA_PRODUCTO = "Falta producto."


def _pedido_listo(memory: Memory, quien: str) -> str:
    """Marca entregado un pedido abierto. Sin 'quien': solo si hay uno hoy. Nunca el de otra persona."""
    anotados = [p for p in memory.list_pedidos(500) if (p.get("estado") or "anotado") not in {"entregado", "rechazado"}]
    if not anotados:
        return "No hay pedidos anotados."
    if quien:
        cifras = _digits(quien)
        if len(cifras) == 4 and cifras == quien:
            cands = [p for p in anotados if _digits(str(p.get("phone") or "")).endswith(cifras)]
        else:
            cands = [
                p for p in anotados
                if _norm(str(p.get("name") or "")) == quien or _norm(str(p.get("name") or "")).startswith(quien + " ")
            ]
        if not cands:
            return f"No hay pedido anotado de {quien}. {PEDIDO_LISTO_AYUDA}"
        # Mismo nombre en dos clientes: no se adivina.
        if len({p["customer_id"] for p in cands}) > 1:
            return "Hay varios con ese nombre:\n" + _lista_anotados(cands) + "\nEscribe pedido listo y las últimas 4 cifras del celular."
    else:
        hoy = reservas._ahora_cali().date()
        cands = [p for p in anotados if reservas._creada_cali(str(p.get("created_at") or "")).date() == hoy]
        if not cands:
            return f"No hay pedidos anotados hoy. {PEDIDO_LISTO_AYUDA}"
        if len(cands) > 1:
            return "Pedidos anotados:\n" + _lista_anotados(cands) + f"\n{PEDIDO_LISTO_AYUDA}"
    # Muro 38: solo se entrega lo pagado o en camino. El pago lo marca el dueño.
    listos = [p for p in cands if p.get("estado") in {"pagado", "en camino"}]
    if not listos:
        return PEDIDO_FALTA_PAGO
    p = listos[0]
    # Muro 47: si el producto del inventario ya no alcanza, no se entrega.
    producto = kb_mod.producto_de_pedido(str(p["servicio"]))
    if producto and int(producto.get("stock") or 0) <= 0:
        return PEDIDO_FALTA_PRODUCTO
    if not memory.entregar_pedido(int(p["pedido_id"])):
        return PEDIDO_FALTA_PAGO
    # Muro 45: el stock del inventario baja solo al entregar. Anotar no lo toca.
    producto = kb_mod.bajar_stock(str(p["servicio"]))
    notify.aviso_cliente_listo(str(p.get("phone") or ""), str(p["servicio"]), memory, str(p["customer_id"]))
    return (
        f"Entregado: {p['servicio']} {kb_mod.precio_txt(p['precio'])} · "
        f"{p.get('name') or p.get('phone') or 'sin nombre'}. AXEL no cobra."
        + (f" Stock {producto['codigo']}: {producto['stock']}." if producto else "")
    )


def _inventario(memory: Memory) -> str:
    """Muro 51: solo el dueño. Código, nombre, stock y disponible (stock menos pedidos abiertos). Máximo 15."""
    productos = kb_mod.productos()
    if not productos:
        return "No hay productos. Ejemplo: producto CAF01 | cafe molido | 12000 | 30"
    lineas = []
    for p in productos[:15]:
        stock = int(p.get("stock") or 0)
        disponible = max(stock - memory.pedidos_abiertos(str(p["codigo"])), 0)
        lineas.append(f"- {p['codigo']} · {p['nombre']} · stock {stock} · disponible {disponible}")
    return "Inventario:\n" + "\n".join(lineas)


_CANCELAR_PEDIDO = re.compile(r"^cancelar (?:el )?pedido(?:\s+#?(\d+))?\s*\.?$")
PEDIDO_YA_VA = "Ese pedido ya va. No lo cancelo."
PEDIDO_YA_VA_CLIENTE = "Ese pedido ya va. Lo cancela el dueño."


def _codigo_txt(servicio: str) -> str:
    """Pedido del inventario: su código. Servicio sin código: su nombre."""
    return str((kb_mod.producto_de_pedido(servicio) or {}).get("codigo") or servicio)


def _cliente_cancela(memory: Memory, customer_id: str, numero: str | None) -> str:
    """Muro 56: el cliente cancela solo lo suyo, anotado o por verificar. Sin número, el más nuevo de esos.
    Pasa a rechazado y suelta la unidad. Pagado o en camino lo cancela el dueño."""
    suyos = [p for p in memory.list_pedidos(500) if p.get("customer_id") == customer_id]
    if numero:
        suyos = [p for p in suyos if int(p["pedido_id"]) == int(numero)]
        if not suyos:
            return f"No tienes pedido #{numero}."
    abiertos = [p for p in suyos if (p.get("estado") or "anotado") in {"anotado", "por verificar"}]
    if not abiertos:
        if any(p.get("estado") in {"pagado", "en camino"} for p in suyos):
            return PEDIDO_YA_VA_CLIENTE
        return "No tienes pedidos para cancelar."
    p = abiertos[0]
    if memory.cancelar_pedido(int(p["pedido_id"])) != "cancelado":
        return PEDIDO_YA_VA_CLIENTE
    return f"Cancelé tu pedido de {_codigo_txt(str(p['servicio']))}."


def _cancelar_pedido(memory: Memory, numero: str | None) -> str:
    """Muro 50: solo el dueño. Anotado o por verificar pasa a rechazado y suelta la unidad."""
    if not numero:
        return "Escribe cancelar pedido y el número del pedido (lo ves en pedidos)."
    estado = memory.cancelar_pedido(int(numero))
    if estado == "cancelado":
        # Muro 58: el cliente de ese pedido se entera.
        p = next((p for p in memory.list_pedidos(500) if int(p["pedido_id"]) == int(numero)), None)
        if p:
            notify.aviso_cliente(
                memory, "pedido_cancelado", str(p.get("phone") or ""),
                f"El dueño canceló tu pedido de {_codigo_txt(str(p['servicio']))}.", str(p["customer_id"]),
            )
        return f"Pedido #{numero} cancelado. La unidad vuelve al disponible."
    if estado in {"pagado", "en camino"}:
        return PEDIDO_YA_VA
    if estado:
        return f"El pedido #{numero} ya está {estado}. No lo cancelo."
    return f"No hay pedido #{numero}."


def _lista_anotados(pedidos: list[dict]) -> str:
    return "\n".join(
        f"- {p.get('name') or 'sin nombre'} · {p['servicio']} {kb_mod.precio_txt(p['precio'])} · "
        f"{reservas._creada_cali(str(p.get('created_at') or '')).strftime('%d/%m %H:%M')}"
        + (f" · cel …{_digits(str(p.get('phone') or ''))[-4:]}" if p.get("phone") else "")
        for p in pedidos[:10]
    )


def _reporte(memory: Memory) -> str:
    """Resumen de hoy en Cali: citas, pedidos y pendientes N3. Solo para el dueño."""
    hoy = reservas._ahora_cali().date()
    citas = []
    for c in memory.list_confirmed_reservas(500):
        cuando = reservas.cuando_fila(c)
        if cuando and cuando[0] == hoy:
            citas.append((cuando[1], cuando[2], str(c.get("name") or "sin nombre")))
    pedidos = [
        p for p in memory.list_pedidos(500)
        if reservas._creada_cali(str(p.get("created_at") or "")).date() == hoy
    ]
    lineas = [
        f"Reporte {hoy.strftime('%d/%m/%Y')} (Cali)",
        f"Citas hoy: {len(citas)}",
        *[f"- {h}:{m:02d} · {quien}" for h, m, quien in sorted(citas)[:8]],
        f"Pedidos hoy: {len(pedidos)} · total {kb_mod.precio_txt(sum(int(p['precio']) for p in pedidos))}",
        *[
            f"- {estado}s: {len(grupo)} · {kb_mod.precio_txt(sum(int(p['precio']) for p in grupo))}"
            for estado in ("anotado", "pagado", "entregado")
            for grupo in [[p for p in pedidos if (p.get("estado") or "anotado") == estado]]
        ],
        f"Pendientes N3: {len(memory.list_pending())}",
    ]
    return "\n".join(lineas)


def envios_filas(memory: Memory, limit: int = 10) -> list[tuple[str, str, str, str, str]]:
    """(hora Cali, a quién, tipo, texto corto, estado) de los últimos envíos. Solo para el dueño."""
    owner = _digits(os.getenv("WA_OWNER_PHONE") or "")
    filas = []
    for e in memory.list_envios(limit):
        destino = str(e.get("destino") or "")
        quien = "dueño" if destino and destino == owner else (f"cel …{destino[-4:]}" if destino else "—")
        hora = reservas._creada_cali(str(e.get("created_at") or "")).strftime("%d/%m %H:%M")
        filas.append((hora, quien, str(e["tipo"]), str(e.get("texto") or "")[:40], str(e["estado"])))
    return filas


_SECRETO = re.compile(r"(token|secret|password|clave|api[_-]?key)\s*[:=]|EAA[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{10,}", re.I)
# Párrafo viejo: dice que falta el servidor 24/7 (ya está en el VPS). No se muestra.
_VIEJO_24_7 = re.compile(r"24/7.*(solo nota|falta|pendiente)|HOSTING_24_7\.md", re.I)
_PIDE_ESTADO = {"estado axel", "como vas", "como va el proyecto"}


def _state_path() -> Path:
    return Path(__file__).resolve().parents[2] / "AXEL_STATE.md"


def _estado_axel() -> str:
    """Primeras 25 líneas con texto de AXEL_STATE.md, sin líneas con pinta de secreto.
    Corta en línea entera antes de 3500 letras (el webhook no manda más)."""
    try:
        lineas = _state_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return "No encuentro el estado."
    salida, largo = [], 0
    for linea in lineas:
        linea = linea.strip()
        if not linea or _SECRETO.search(linea) or _VIEJO_24_7.search(linea):
            continue
        if len(salida) == 25 or largo + len(linea) + 1 > 3500:
            break
        salida.append(linea)
        largo += len(linea) + 1
    return "\n".join(salida) or "No encuentro el estado."


def _try_owner_decision(env: Envelope, memory: Memory) -> bool:
    if not _es_dueno(env):
        return False
    t = _norm(env.text)
    if t.strip("¿?¡!. ") in _PIDE_ESTADO:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        env.reply_text = _estado_axel()
        env.result = "ok"
        env.approval_status = "na"
        return True
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
            "Comandos dueño: estado, estado axel, reporte, limpiar, pendientes, citas, clientes, pedidos, pedido pagado N, pedido listo, pedido en camino N, cancelar pedido N, inventario, envios, catalogo, "
            "aprobar N, rechazar N, ayuda, "
            "configurar, cancelar configurar, el negocio se llama NOMBRE, abrimos de H1 a H2, "
            "el rubro es X, agenda si/no, agrega servicio X a N, "
            "cambia el precio de X a N, stock X N, tono formal/cercano, quita servicio X, franjas 8 12 16,"
            "agrega pregunta X respuesta Y, quita pregunta X, la ubicacion es X, "
            "politica cancelacion X, politica garantia X, agenda palabras cita reserva mesa turno, "
            "producto COD | NOMBRE | PRECIO | STOCK, contacto proveedor NUMERO."
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
        env.reply_text = _lista_pendientes(pend) if pend else "No hay pendientes."
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
                franja = reservas.franja_fila(c)
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
    listo = re.match(r"^pedido listo(?:\s+(.+))?$", t)
    if listo:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        env.reply_text = _pedido_listo(memory, (listo.group(1) or "").strip())
        env.result = "ok"
        env.approval_status = "na"
        return True
    cancelar = _CANCELAR_PEDIDO.match(t)
    if cancelar:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        env.reply_text = _cancelar_pedido(memory, cancelar.group(1))
        env.result = "ok"
        env.approval_status = "na"
        return True
    camino = re.match(r"^pedido en camino(?:\s+#?(\d+))?\s*\.?$", t)
    if camino:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        # Muro 52: solo pagado y con contacto proveedor. No se le escribe al proveedor.
        if not kb_mod.proveedor_contacto():
            env.reply_text = "Falta el contacto proveedor."
        elif not camino.group(1):
            env.reply_text = "Escribe pedido en camino y el número del pedido (lo ves en pedidos)."
        elif memory.en_camino_pedido(int(camino.group(1))):
            # Muro 59: al cliente sí se le avisa. Al proveedor no.
            p = next((p for p in memory.list_pedidos(500) if int(p["pedido_id"]) == int(camino.group(1))), None)
            if p:
                notify.aviso_cliente(
                    memory, "pedido_en_camino", str(p.get("phone") or ""),
                    f"Tu pedido de {_codigo_txt(str(p['servicio']))} va en camino.", str(p["customer_id"]),
                )
            env.reply_text = f"Pedido #{camino.group(1)} en camino. AXEL no le escribe al proveedor."
        else:
            env.reply_text = f"No hay pedido #{camino.group(1)} pagado."
        env.result = "ok"
        env.approval_status = "na"
        return True
    pagado = re.match(r"^pedido pagado(?:\s+#?(\d+))?$", t)
    if pagado:
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        if not pagado.group(1):
            env.reply_text = "Escribe pedido pagado y el número del pedido (lo ves en pedidos)."
        elif memory.pagar_pedido(int(pagado.group(1))):
            env.reply_text = f"Pedido #{pagado.group(1)} pagado. Lo marcaste tú: AXEL no mira el banco."
        else:
            env.reply_text = f"No hay pedido #{pagado.group(1)} por pagar."
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t == "reporte":
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        env.reply_text = _reporte(memory)
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t == "pedidos":
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        lineas = [f"- {hora} · {quien} · {pedido} · {estado}" for hora, quien, pedido, estado in pedidos_filas(memory)]
        env.reply_text = "Pedidos:\n" + "\n".join(lineas) if lineas else "No hay pedidos."
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t == "inventario":
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        env.reply_text = _inventario(memory)
        env.result = "ok"
        env.approval_status = "na"
        return True
    if t == "envios":
        env.intent = "admin"
        env.agent = "escalamiento"
        env.supervision_level = 1
        lineas = [f"- {' · '.join(f)}" for f in envios_filas(memory)]
        env.reply_text = "Envíos:\n" + "\n".join(lineas) if lineas else "No hay envíos."
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
            cita = reservas.franja_fila(ult) if ult else "—"
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
    env.result = "ok"
    env.approval_status = "na"
    if not pend:
        env.reply_text = "No hay decisiones pendientes."
        return True
    # Muro 40: sin número no se decide. Nunca se toma el primero.
    numero = re.match(r"^(?:aprobar|aceptar|acepto|autorizo|autorizar|rechazar|rechazo|niego|denegar)\s+#?(\d+)\b", t)
    if not numero:
        env.reply_text = _lista_pendientes(pend)
        return True
    row = next((p for p in pend if int(p["n"]) == int(numero.group(1))), None)
    if not row:
        env.reply_text = f"No hay pendiente #{numero.group(1)}.\n" + _lista_pendientes(pend)
        return True
    decision = "approved" if si else "rejected"
    borrar = si and row.get("intent") == "borrar_datos"
    # Muro 41: aprobar una referencia lleva precio y plazo del dueño. Sin ellos no se resuelve.
    ref_ok = None
    if si and row.get("intent") == "referencia":
        ref_ok = _APROBAR_REF.match((env.text or "").strip())
        if not ref_ok or _pesos(ref_ok.group(1)) <= 0:
            env.reply_text = REF_APROBAR_AYUDA
            return True
    # Aviso al cliente antes de resolver el caso.
    cli = memory.get_customer(str(row.get("customer_id") or "")) or {}
    if ref_ok:
        codigo = str(row.get("requested_action") or "").split(" · ")[0]
        texto_cliente = (
            f"{codigo}: {kb_mod.precio_txt(_pesos(ref_ok.group(1)))}. Entrega: {ref_ok.group(2).strip()[:60]}. "
            "El dueño confirma el pedido y el pago. AXEL no cobra."
        )
    elif borrar:
        texto_cliente = "El dueño aprobó borrar tus datos. Tu nombre, correo y notas ya no quedan en la ficha."
    elif si:
        texto_cliente = "El dueño ya revisó tu caso y lo aprobó. Te escribimos si falta algo."
    else:
        texto_cliente = "El dueño revisó tu caso y por ahora no se puede. Si quieres, lo vemos de otra forma."
    notify.aviso_cliente(
        memory, "n3_cliente", str(cli.get("phone") or ""), texto_cliente, str(row.get("customer_id") or "")
    )
    memory.resolve_pending(str(row.get("event_id") or ""), decision)
    env.reply_text = (
        f"Quedó {decision} el caso {row.get('event_id')} "
        f"({row.get('intent')})."
        + (" Datos borrados: nombre, correo y notas. Pedidos, citas y auditoría se quedan." if borrar else "")
        + (f" Al cliente: {texto_cliente}" if ref_ok else "")
    )
    env.approval_status = decision
    return True


def _lista_pendientes(pend: list[dict]) -> str:
    lineas = [f"- #{p['n']} {p.get('intent')}: {p.get('requested_action')}" for p in pend[:10]]
    return "Pendientes:\n" + "\n".join(lineas) + "\nEscribe aprobar N o rechazar N."


# "ref CAF01", "código CAF01" o solo "CAF01" (letras y luego cifras).
_REFERENCIA = re.compile(
    r"^(?:(?:ref|referencia|c[oó]digo)\s*:?\s*([a-z0-9][a-z0-9-]{1,19})|([a-z]{2,}-?\d[a-z0-9-]{0,17}))\s*[.?!]?$", re.I
)
REF_SIN_INVENTARIO = "Referencia sin inventario. Falta tu sí."


def _referencia(env: Envelope, memory: Memory, codigo: str) -> None:
    """Muro 37: con inventario, precio de venta y stock. Sin inventario no hay precio ni pedido: nota al dueño."""
    codigo = codigo.upper()
    env.intent = "referencia"
    env.agent = "atencion"
    p = kb_mod.buscar_producto(codigo)
    if p:
        stock = int(p.get("stock") or 0)
        env.reply_text = f"{p['codigo']} {p['nombre']}: {kb_mod.precio_txt(p['precio'])}. " + (
            f"Stock {stock}." if stock > 0 else "Agotado."
        )
        env.supervision_level = 1
        env.result = "ok"
        env.approval_status = "na"
        env.why = "referencia en inventario"
        return
    # Solo nota en pendientes: no se envía WhatsApp ni se inventa precio.
    # Muro 46: si el dueño guardó el contacto del proveedor, la nota lo dice. AXEL no le escribe.
    proveedor = kb_mod.proveedor_contacto()
    nota = REF_SIN_INVENTARIO + (f" Proveedor: {proveedor}." if proveedor else "")
    memory.save_pending_approval(
        {
            "event_id": env.event_id,
            "customer_id": env.customer_id,
            "intent": "referencia",
            "why": REF_SIN_INVENTARIO,
            "requested_action": f"{codigo} · {nota}",
            "notify_text": nota,
            "status": "pending",
        }
    )
    env.reply_text = f"No tengo {codigo} en inventario. Le consulto al dueño y te aviso."
    env.supervision_level = 3
    env.result = "pending"
    env.approval_status = "pending_owner"
    env.why = REF_SIN_INVENTARIO


# Muro 41: "me lo llevo CAF01" / "lo compro ref CAF01".
_PEDIDO_CODIGO = re.compile(
    r"(?:me lo llevo|lo compro)\s+(?:el\s+|la\s+)?(?:(?:ref|referencia|c[oó]digo)\s*:?\s*)?([a-z0-9][a-z0-9-]{1,19})\s*[.!]?$", re.I
)


def _codigo_pedido(texto: str) -> str:
    """El código de un pedido por referencia: uno del inventario o con forma de código (letras y cifras). '' si no."""
    m = _PEDIDO_CODIGO.search((texto or "").strip())
    if not m:
        return ""
    codigo = m.group(1).upper()
    if kb_mod.buscar_producto(codigo) or re.match(r"^[A-Z]{2,}-?\d", codigo):
        return codigo
    return ""


def _pedido_codigo(env: Envelope, memory: Memory, codigo: str) -> None:
    """Muro 41: con stock se anota con el precio de venta del inventario. Sin stock no se anota.
    Sin el código en inventario no se anota: nota al dueño (muro 37)."""
    p = kb_mod.buscar_producto(codigo)
    if not p:
        _referencia(env, memory, codigo)
        return
    env.intent = "pedido"
    env.agent = "atencion"
    env.supervision_level = 1
    env.result = "ok"
    env.approval_status = "na"
    # Muro 47: disponible = stock menos pedidos abiertos de ese código. La última unidad no se vende dos veces.
    stock = int(p.get("stock") or 0) - memory.pedidos_abiertos(str(p["codigo"]))
    if stock <= 0:
        env.reply_text = f"No hay {codigo} ahora."
        env.why = "referencia sin stock disponible"
        return
    pedido = f"{p['codigo']} {p['nombre']} {kb_mod.precio_txt(p['precio'])}"
    memory.add_pedido(env.customer_id, f"{p['codigo']} {p['nombre']}", int(p["precio"]))
    env.payload["aviso_pedido"] = notify.aviso_pedido(env.name or env.phone or "sin nombre", pedido, memory)
    env.reply_text = f"Pedido anotado: {pedido}. Stock {stock}. El dueño confirma el pago."
    env.why = "pedido por referencia en inventario"


FOTO_COMPROBANTE = "Recibí el comprobante. El dueño lo verifica. AXEL no mira el banco."
FOTO_PRODUCTO = "Recibí la foto. Escribe el código o el nombre. El dueño confirma la referencia."


def _foto(env: Envelope, memory: Memory) -> None:
    """Muro 42: la foto no se lee. Con pedido anotado o por verificar es comprobante; si no, producto.
    Muro 55: el pedido sin pagar más nuevo pasa a por verificar. El pago lo marca el dueño."""
    env.intent = "foto"
    env.agent = "atencion"
    env.supervision_level = 1
    env.result = "ok"
    env.approval_status = "na"
    pedido_id = memory.foto_por_verificar(env.customer_id or "")
    env.reply_text = FOTO_COMPROBANTE if pedido_id else FOTO_PRODUCTO
    env.payload["aviso_foto"] = notify.aviso_foto(memory, pedido_id)
    env.why = "foto recibida, no leída"


_APROBAR_REF = re.compile(r"^\S+\s+#?\d+\s+\$?([\d.,]+)\s+(.+)$")
REF_APROBAR_AYUDA = "Escribe aprobar N PRECIO PLAZO. Ejemplo: aprobar 3 45000 mañana."


def pick_agent(intent: str) -> str:
    if intent in {"reserva", "reprogramar", "cancelar", "mi_cita"}:
        return "reservas"
    if intent in {"queja", "reembolso", "borrar_datos", "descuento_grande", "admin"}:
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
    if pedir_nombre and memory.last_reply(env.customer_id).endswith(PREGUNTAS_NOMBRE):
        candidato = (env.text or "").strip().rstrip(".!")
        if (
            NOMBRE_CORTO.fullmatch(candidato)
            and _nombre_usable(candidato)
            and len(candidato.split()) <= 4
            and env.intent == "pregunta"
            and _norm(candidato) not in NO_ES_NOMBRE
            and _norm(candidato).split()[0] not in NO_EMPIEZA_NOMBRE
            and " ".join(_norm(candidato).split()[:2]) not in NO_EMPIEZA_NOMBRE_FRASES
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
    ref = _REFERENCIA.match((env.text or "").strip())
    codigo = _codigo_pedido(env.text or "")
    resuelto = False
    if env.payload.get("foto") and not env.payload["es_dueno"]:
        _foto(env, memory)
        resuelto = True
    elif not env.payload["es_dueno"] and (cancela := _CANCELAR_PEDIDO.match(_norm(env.text or "").strip())):
        # Muro 56: el cliente cancela lo suyo si no está pagado. Nunca el de otro.
        env.intent = "pedido"
        env.agent = "atencion"
        env.supervision_level = 1
        env.result = "ok"
        env.approval_status = "na"
        env.reply_text = _cliente_cancela(memory, env.customer_id or "", cancela.group(1))
        env.why = "cliente cancela su pedido sin pagar"
        resuelto = True
    elif not env.payload["es_dueno"] and open_task not in {"reserva", "reprogramar"}:
        if codigo:
            _pedido_codigo(env, memory, codigo)
            resuelto = True
            if open_task == "oferta_cita":
                memory.set_open_task(env.customer_id, "")
                open_task = ""
        elif ref:
            _referencia(env, memory, ref.group(1) or ref.group(2))
            resuelto = True
    if (
        open_task in {"reserva", "reprogramar", "oferta_cita"}
        and env.intent in {"pregunta", "saludo", "venta"}
        and atencion.es_pedido(env.text)
    ):
        # Comprar no es reservar: el pedido cierra la cita a medio pedir.
        memory.set_open_task(env.customer_id, "")
        open_task = ""
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
    if not resuelto:
        env.agent = pick_agent(env.intent)
        env.supervision_level = classify_level(env.intent)
        env.why = reason_for(env.intent or "", env.supervision_level)

        decision = route(env.intent)
        env.model = decision.model
        env.model_reason = decision.reason

    if resuelto:
        pass
    elif needs_owner_approval(env.supervision_level):
        env = escalamiento.handle(env)
        notify_owner(env, memory)
    elif env.agent == "reservas" or needs_customer_confirm(env.supervision_level):
        env = reservas.handle(env, memory)
    else:
        env = atencion.handle(env, memory)
        low = (env.reply_text or "").lower()
        ofertas = ("reserve un cupo", "te reserve", "agendarte para mañana", "agendarle para mañana","reservamos mesa", "te anoto un turno")
        if any(o in low for o in ofertas):
            memory.set_open_task(env.customer_id, "oferta_cita")

    if env.result is None:
        env.result = "ok"

    # Primer mensaje de un cliente WhatsApp (sea cual sea): aviso de datos una vez, antes de la pregunta de nombre.
    if (
        env.channel == "whatsapp"
        and not env.payload["es_dueno"]
        and not memory.replied_with(env.customer_id, "borrar mis datos")
    ):
        aviso = AVISO_DATOS_FORMAL if kb_mod.tono() == "formal" else AVISO_DATOS
        env.reply_text = f"{env.reply_text or ''} {aviso}".strip()

    if (
        pedir_nombre
        and not env.name
        and env.intent in {"saludo", "pregunta"}
        and not any(memory.replied_with(env.customer_id, p) for p in PREGUNTAS_NOMBRE)
    ):
        pregunta = PREGUNTA_NOMBRE_FORMAL if kb_mod.tono() == "formal" else PREGUNTA_NOMBRE
        env.reply_text = f"{env.reply_text or ''} {pregunta}".strip()

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
        cita_at=env.payload.get("cita_at") if env.intent == "reserva" and env.result == "ok" else None,
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