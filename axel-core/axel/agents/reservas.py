from __future__ import annotations

from axel.envelope import Envelope


def handle(env: Envelope) -> Envelope:
    text = (env.text or "").lower()
    tiene_cuando = any(
        p in text
        for p in ("mañana", "manana", "hoy", "tarde", "lunes", "martes", "am", "pm")
    ) or any(c.isdigit() for c in text)
    if tiene_cuando and "cita" not in text and "reserva" not in text:
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
