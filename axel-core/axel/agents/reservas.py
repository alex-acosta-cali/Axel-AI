from __future__ import annotations

from axel.envelope import Envelope


def handle(env: Envelope) -> Envelope:
    env.reply_text = (
        "Puedo reservarte un horario. Para confirmar necesito que me digas "
        "el día y la hora. ¿Confirmamos la reserva cuando elijas el cupo?"
    )
    env.result = "pending"
    env.approval_status = "pending_customer"
    return env
