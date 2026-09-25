from __future__ import annotations

from axel.envelope import Envelope


def handle(env: Envelope) -> Envelope:
    if env.intent == "queja":
        env.reply_text = (
            "Lamento lo que pasó. Dejé la queja con el dueño. "
            "No la cierro yo: él decide y te respondemos."
        )
    else:
        env.reply_text = (
            "Este tema necesita al dueño. Ya dejé el caso registrado y lo aviso. "
            "Te respondemos enseguida."
        )
    env.result = "pending"
    env.approval_status = "pending_owner"
    return env
