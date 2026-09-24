from __future__ import annotations

from axel.envelope import Envelope
from axel.memory import Memory


def owner_alert(env: Envelope) -> str:
    return (
        "DECISION PENDIENTE NIVEL 3\n"
        f"Evento: {env.event_id}\n"
        f"Cliente: {env.customer_id}\n"
        f"Canal: {env.channel}\n"
        f"Intent: {env.intent}\n"
        f"Por que: {env.why}\n"
        f"Pedido: {env.text}\n"
        "AXEL NO ejecuto la accion. Responde APROBAR o RECHAZAR."
    )


def notify_owner(env: Envelope, memory: Memory) -> str:
    if memory.has_pending(env.customer_id or "", env.intent or ""):
        env.owner_notified = True
        env.reply_text = (
            "Ese pedido ya está con el dueño. No lo duplico. "
            "Cuando decida, te avisamos."
        )
        env.result = "pending"
        env.approval_status = "pending_owner"
        return "duplicate"
    text = owner_alert(env)
    memory.save_pending_approval(
        {
            "event_id": env.event_id,
            "customer_id": env.customer_id,
            "intent": env.intent,
            "why": env.why,
            "requested_action": env.text,
            "notify_text": text,
            "status": "pending",
        }
    )
    env.owner_notified = True
    env.payload["owner_alert"] = text
    print("\n===== ALERTA AL DUENO =====\n" + text + "\n===========================\n")
    return text
