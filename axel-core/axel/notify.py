from __future__ import annotations

import os

from axel.connectors.whatsapp import send_text
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


def aviso_pedido(quien: str, pedido: str) -> str:
    """Aviso corto al dueño por el canal de alertas N3. Solo informa: AXEL no cobra."""
    text = f"Pedido nuevo: {quien} · {pedido}. AXEL no cobra."
    print("\n===== AVISO AL DUENO =====\n" + text + "\n==========================\n")
    destino = (os.getenv("WA_OWNER_PHONE") or "").strip()
    if destino:
        print("WA DUENO:", send_text(destino, text))
    return text


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
    destino = (os.getenv("WA_OWNER_PHONE") or "").strip()
    if destino:
        res = send_text(destino, text)
        print("WA DUENO:", res)
    return text