from __future__ import annotations

from datetime import datetime, timedelta, timezone

from axel.envelope import Envelope
from axel import knowledge_base as kb

_CALI = timezone(timedelta(hours=-5))


def estado_cali(ahora: datetime | None = None) -> tuple[bool, str]:
    now = ahora or datetime.now(_CALI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_CALI)
    now = now.astimezone(_CALI)
    hora = now.strftime("%H:%M")
    if now.weekday() == 6:
        return False, (
            f"Hoy es domingo en Cali ({hora}). No abrimos. "
            "El horario es lunes a sábado, 8:00 a 19:00."
        )
    if now.hour < 8 or now.hour >= 19:
        return False, (
            f"Ahora en Cali son las {hora} y estamos cerrados. "
            "Abrimos lunes a sábado, 8:00 a 19:00."
        )
    return True, f"Ahora en Cali son las {hora}: estamos abiertos hasta las 19:00."


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
    if any(p in bajo for p in ("me lo llevo", "lo compro", "quiero pagar", "lo pago")):
        env.reply_text = (
            "Pedido piloto anotado: corte $25.000. "
            "En esta versión AXEL no cobra. El dueño confirma el pago real después."
        )
        env.result = "ok"
        env.intent = "pedido"
        if memory is not None and env.customer_id:
            memory.add_note(env.customer_id, "Pedido piloto corte $25.000 (sin cobro)")
        return env
    if "domingo" in bajo:
        _, msg = estado_cali()
        env.reply_text = "Los domingos no atendemos. " + msg
        env.result = "ok"
        return env
    faq = kb.answer(text)
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
        if env.name:
            env.reply_text = f"Hola {env.name}, soy AXEL. ¿En qué te ayudo?"
        else:
            env.reply_text = kb.greeting()
        env.result = "ok"
        return env
    env.reply_text = (
        "No tengo esa información en la base del negocio. "
        "Puedo ayudarte con horarios, precios, ubicación o una cita. "
        "Si es otra cosa, el dueño lo revisa."
    )
    env.result = "ok"
    return env