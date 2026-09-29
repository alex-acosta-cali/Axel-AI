from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from axel.envelope import Envelope
from axel import knowledge_base as kb

_CALI = timezone(timedelta(hours=-5))
_OFERTA_CITA = re.compile(r"\s*¿[^?]*\b(reserv|agend|cupo|cita)[^?]*\?", re.I)
PEDIDO_FRASES = ("me lo llevo", "lo compro", "quiero pagar", "lo pago")


def es_pedido(text: str) -> bool:
    bajo = (text or "").lower()
    return any(p in bajo for p in PEDIDO_FRASES)


_RELLENO_PEDIDO = {"el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "por", "favor", "porfa", "pls"}


def _pedido_sin_servicio(text: str) -> str:
    """Lo que el cliente nombró después de 'me lo llevo' ('pizza'). '' si no nombró nada."""
    bajo = (text or "").lower()
    frase = next(p for p in PEDIDO_FRASES if p in bajo)
    palabras = re.findall(r"[a-záéíóúüñ0-9+]+", bajo.split(frase, 1)[1])
    return " ".join(w for w in palabras if w not in _RELLENO_PEDIDO)[:40]


def estado_cali(ahora: datetime | None = None) -> tuple[bool, str]:
    now = ahora or datetime.now(_CALI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_CALI)
    now = now.astimezone(_CALI)
    hora = now.strftime("%H:%M")
    abre, cierra = kb.get_hours()
    txt_cierra = f"{cierra[0]}:{cierra[1]:02d}"
    horario = f"lunes a sábado, {abre[0]}:{abre[1]:02d} a {txt_cierra}"
    if now.weekday() == 6:
        return False, (
            f"Hoy es domingo en Cali ({hora}). No abrimos. "
            f"El horario es {horario}."
        )
    if (now.hour, now.minute) < abre or (now.hour, now.minute) >= cierra:
        return False, (
            f"Ahora en Cali son las {hora} y estamos cerrados. "
            f"Abrimos {horario}."
        )
    return True, f"Ahora en Cali son las {hora}: estamos abiertos hasta las {txt_cierra}."


def handle(env: Envelope, memory=None) -> Envelope:
    text = (env.text or "").strip()
    bajo = text.lower()
    if env.intent == "admin_kb":
        env.result = "ok"
        if not env.reply_text:
            env.reply_text = "No pude actualizar la KB."
        return env
    if env.intent == "nota":
        env.result = "ok"
        if not env.reply_text:
            env.reply_text = "No pude anotar eso."
        return env
    if env.intent == "datos":
        partes = []
        if env.name:
            partes.append(f"nombre: {env.name}")
        if env.phone:
            partes.append(f"celular: {env.phone}")
        if env.email:
            partes.append(f"correo: {env.email}")
        env.reply_text = ("Quedó tu " + " y ".join(partes) + ".") if partes else "Recibí tus datos."
        env.result = "ok"
        return env
    if any(p in bajo for p in ("mi ficha", "quien soy", "quién soy", "mis datos")):
        notas = []
        cita = None
        if memory is not None and env.customer_id:
            notas = [str(n.get("note") or "") for n in memory.list_notes(env.customer_id, 3)]
            cita = memory.last_reserva(env.customer_id)
        env.reply_text = (
            f"Tu ficha AXEL: {env.name or 'sin nombre'}, "
            f"cel {env.phone or '—'}, correo {env.email or '—'}. "
            f"Notas: {(' | '.join(notas) if notas else 'ninguna')}. "
            f"Cita: {(cita or {}).get('summary') if cita else 'ninguna'}."
        )
        env.result = "ok"
        return env
    # Pitch y cuaderno son internos (plan, IDs de Meta): solo para el dueño.
    if env.payload.get("es_dueno"):
        pitch = kb.answer_pitch(text)
        if pitch:
            env.reply_text = pitch
            env.result = "ok"
            return env
        cuaderno = kb.answer_cuaderno(text)
        if cuaderno:
            env.reply_text = cuaderno
            env.result = "ok"
            return env
    if es_pedido(text):
        servicio = kb.servicio_en(text)
        env.result = "ok"
        if not servicio:
            env.reply_text = kb.lista_servicios() if kb.servicios() else kb.NO_HAY
            pedido = _pedido_sin_servicio(text)
            if pedido and kb.servicios():
                env.reply_text = f"No tengo {pedido}. {env.reply_text}"
            return env
        pedido = f"{servicio['nombre']} {kb.precio_txt(servicio.get('precio') or 0)}"
        env.reply_text = f"Pedido anotado: {pedido}. El dueño confirma el pago."
        env.intent = "pedido"
        if memory is not None and env.customer_id:
            memory.add_pedido(env.customer_id, str(servicio["nombre"]), int(servicio.get("precio") or 0))
        return env
    if "domingo" in bajo:
        _, msg = estado_cali()
        env.reply_text = "Los domingos no atendemos. " + msg
        env.result = "ok"
        return env
    fijo = kb.answer_ubicacion(text) or kb.answer_politica(text)
    if fijo:
        env.reply_text = fijo
        env.result = "ok"
        return env
    precio = kb.answer_servicio(text)
    if precio:
        env.reply_text = precio
        env.result = "ok"
        return env
    faq = kb.answer(text)
    if faq and not kb.agenda():
        # La FAQ puede traer "¿Quieres que te reserve un cupo?": sin agenda no se ofrece.
        faq = _OFERTA_CITA.sub("", faq).strip() or faq
    if faq:
        abierto, estado = estado_cali()
        pide_hora = any(
            k in bajo for k in ("horario", "horarios", "abren", "cierran", "abierto", "cerrado")
        )
        if pide_hora and not abierto:
            env.reply_text = estado
        elif pide_hora:
            env.reply_text = f"{faq} {estado}"
        else:
            env.reply_text = faq
        env.result = "ok"
        return env
    if env.intent == "cierre":
        env.reply_text = (
            f"Con gusto, {env.name}. Aquí estoy si me necesitas."
            if env.name
            else "Con gusto. Aquí estoy si me necesitas."
        )
        env.result = "ok"
        return env
    if env.intent == "saludo":
        abierto, estado = estado_cali()
        negocio = str(kb.load_kb().get("negocio") or "").strip()
        soy = f"soy AXEL de {negocio}." if negocio else "soy AXEL."
        base = f"Hola {env.name}, {soy}" if env.name else f"Hola, {soy}"
        if abierto:
            env.reply_text = f"{base} ¿En qué te ayudo?"
        else:
            oferta = "Puedo agendarte para mañana o responder horarios y precios." if kb.agenda() else (
                "Puedo responder horarios y precios."
            )
            env.reply_text = f"{base} {estado} {oferta}"
        env.result = "ok"
        return env
    temas = "horarios, precios, ubicación o una cita" if kb.agenda() else "horarios, precios o ubicación"
    env.reply_text = (
        "No tengo esa información en la base del negocio. "
        f"Puedo ayudarte con {temas}. "
        "Si es otra cosa, el dueño lo revisa."
    )
    env.result = "ok"
    return env