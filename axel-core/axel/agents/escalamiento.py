from __future__ import annotations

from axel.envelope import Envelope


def handle(env: Envelope) -> Envelope:
    if env.intent == "queja":
        env.reply_text = (
            "Lamento lo que pasó. Dejé la queja con el dueño. "
            "No la cierro yo: él decide y te respondemos."
        )
    elif env.intent == "borrar_datos":
        # N3: AXEL no borra. El dueño aprueba o rechaza y decide qué hacer.
        env.reply_text = (
            "Dejé tu pedido de borrar datos con el dueño. "
            "No se borra nada solo: él lo revisa y te respondemos."
        )
    else:
        env.reply_text = (
            "Este tema necesita al dueño. Ya dejé el caso registrado y lo aviso. "
            "Te respondemos enseguida."
        )
    env.result = "pending"
    env.approval_status = "pending_owner"
    return env
