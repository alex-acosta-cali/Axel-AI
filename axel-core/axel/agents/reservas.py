from __future__ import annotations

import re

from axel.envelope import Envelope


def _tiene_cuando(text: str) -> bool:
    t = (text or "").lower()
    if re.search(r"\b\d{1,2}([:.]\d{2})?\s*(am|pm)?\b", t):
        return True
    if re.search(
        r"\b(manana|mañana|hoy|tarde|noche|lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\b",
        t,
    ):
        return True
    return False


def handle(env: Envelope, memory=None) -> Envelope:
    if env.intent == "mi_cita" and memory is not None:
        fila = memory.last_reserva(env.customer_id or "")
        if fila:
            env.reply_text = f"Tu cita confirmada es: «{fila.get('summary')}»."
        else:
            env.reply_text = "No tienes una cita confirmada ahora."
        env.result = "ok"
        env.approval_status = "na"
        return env
    bajo = (env.text or "").lower()
    if "reprogram" in bajo or "cambiar la cita" in bajo or "cambiar cita" in bajo:
        env.intent = "reprogramar"
    if env.intent == "cancelar" and memory is not None:
        baja = memory.cancel_last_reserva(env.customer_id or "")
        if baja:
            env.reply_text = f"Cancelé la cita «{baja.get('summary')}»."
            env.result = "ok"
            env.approval_status = "cancelled_customer"
            return env
        env.reply_text = "No tienes una cita confirmada para cancelar."
        env.result = "ok"
        env.approval_status = "na"
        return env

    if env.intent == "reprogramar":
        if memory is None:
            env.reply_text = "No pude tocar la agenda."
            env.result = "error"
            return env
        if not _tiene_cuando(env.text or ""):
            env.reply_text = "¿Para qué día y hora la pasamos?"
            env.result = "pending"
            env.approval_status = "pending_customer"
            return env
        memory.cancel_last_reserva(env.customer_id or "")
        env.reply_text = f"Pasé la cita a «{env.text}»."
        env.result = "ok"
        env.approval_status = "confirmed_customer"
        return env

    if _tiene_cuando(env.text or "") and "cita" not in bajo and "reserva" not in bajo:
        env.reply_text = (
            f"Quedó anotada la reserva para «{env.text}». "
            "En el piloto no hay agenda real todavía; el cupo queda como confirmado de prueba."
        )
        env.result = "ok"
        env.approval_status = "confirmed_customer"
        return env

    env.reply_text = (
        "Puedo reservarte un horario. Para confirmar necesito que me digas "
        "el día y la hora. ¿Confirmamos la reserva cuando elijas el cupo?"
    )
    env.result = "pending"
    env.approval_status = "pending_customer"
    return env