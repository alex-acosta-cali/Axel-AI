from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from axel.envelope import Envelope

_CALI = timezone(timedelta(hours=-5))
FRANJAS = "9:00, 11:00, 15:00 o 17:00"


def _ahora_cali() -> datetime:
    return datetime.now(_CALI)


def _cerrado_ahora() -> bool:
    now = _ahora_cali()
    return now.weekday() == 6 or now.hour < 8 or now.hour >= 19


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
    if "domingo" in bajo and env.intent in {"reserva", "reprogramar"}:
        env.reply_text = "Los domingos no abrimos. Elige lunes a sábado."
        env.result = "denied"
        env.approval_status = "na"
        env.intent = "reserva_denegada"
        return env

    if "hoy" in bajo and _cerrado_ahora() and env.intent in {"reserva", "reprogramar"}:
        env.reply_text = (
            "Hoy en Cali ya no hay cupo (cerramos a las 19:00). "
            f"¿Mañana a las {FRANJAS}?"
        )
        env.result = "denied"
        env.approval_status = "na"
        env.intent = "reserva_denegada"
        return env

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

    vigente = None
    if memory is not None:
        vigente = memory.last_reserva(env.customer_id or "")

    if env.intent == "reprogramar":
        if memory is None:
            env.reply_text = "No pude tocar la agenda."
            env.result = "error"
            return env
        if not vigente:
            env.reply_text = "No tienes cita para reprogramar. ¿Agendamos una nueva?"
            env.result = "pending"
            env.approval_status = "pending_customer"
            env.intent = "reserva"
            return env
        if not _tiene_cuando(env.text or ""):
            env.reply_text = (
                f"Tienes «{vigente.get('summary')}». "
                f"¿La pasamos a {FRANJAS}?"
            )
            env.result = "pending"
            env.approval_status = "pending_customer"
            return env
        memory.cancel_last_reserva(env.customer_id or "")
        env.reply_text = f"Pasé la cita a «{env.text}»."
        env.result = "ok"
        env.approval_status = "confirmed_customer"
        return env

    if vigente and env.intent == "reserva":
        env.reply_text = (
            f"Ya tienes una cita: «{vigente.get('summary')}». "
            "No te agendo otra. Escribe cancelar la cita o reprogramar la cita."
        )
        env.result = "denied"
        env.approval_status = "na"
        env.intent = "reserva_denegada"
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
        f"Puedo reservarte. Franjas piloto: {FRANJAS}, lunes a sábado. "
        "Dime día y hora."
    )
    env.result = "pending"
    env.approval_status = "pending_customer"
    return env