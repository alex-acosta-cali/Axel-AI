from __future__ import annotations

from axel.envelope import Envelope


def handle(env: Envelope) -> Envelope:
    env.reply_text = (
        "Este tema necesita al dueño. Ya dejé el caso registrado y lo aviso. "
        "Te respondemos enseguida."
    )
    env.result = "pending"
    env.approval_status = "pending_owner"
    return env
