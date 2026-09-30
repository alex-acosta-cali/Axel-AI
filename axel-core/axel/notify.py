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


def _digitos(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def enviar(memory: Memory | None, tipo: str, destino: str, text: str, cliente: str | None = None) -> str:
    """Envía por WhatsApp y deja una fila en envios. Un solo intento: si Meta falla, queda 'fallo'.
    Con 'cliente' (su customer_id): si su último mensaje entrante tiene más de 24 h, no se manda texto
    libre y queda 'fuera_24h'. Sin 'cliente' (avisos al dueño) no se mira: su ventana es la suya."""
    destino = _digitos(destino)
    if not destino:
        estado = "sin_celular"
    elif cliente is not None and memory is not None and not memory.escribio_24h(cliente):
        estado = "fuera_24h"
        print(f"WA {tipo}: fuera de 24 h, no se envía texto libre")
    else:
        try:
            res = send_text(destino, text)
            print(f"WA {tipo}:", res)
            ok = not res.get("skipped") and 200 <= int(res.get("status", 200)) < 300
        except Exception as exc:
            print(f"WA {tipo} error:", exc)
            ok = False
        estado = "enviado" if ok else "fallo"
    if memory is not None:
        memory.add_envio(destino, tipo, text, estado)
    return estado


def aviso_pedido(quien: str, pedido: str, memory: Memory | None = None) -> str:
    """Aviso corto al dueño por el canal de alertas N3. Solo informa: AXEL no cobra."""
    text = f"Pedido nuevo: {quien} · {pedido}. AXEL no cobra."
    print("\n===== AVISO AL DUENO =====\n" + text + "\n==========================\n")
    enviar(memory, "pedido_nuevo", os.getenv("WA_OWNER_PHONE") or "", text)
    return text


def aviso_cliente(memory: Memory | None, tipo: str, phone: str, text: str, customer_id: str = "") -> str:
    """Aviso a un cliente. Si su celular es el del dueño, no se envía: fila 'omitido_dueno'.
    Fuera de su ventana de 24 h tampoco: fila 'fuera_24h'."""
    destino = _digitos(phone)
    if destino and destino == _digitos(os.getenv("WA_OWNER_PHONE") or ""):
        if memory is not None:
            memory.add_envio(destino, tipo, text, "omitido_dueno")
        return "omitido_dueno"
    return enviar(memory, tipo, destino, text, customer_id or "")


def aviso_cliente_listo(phone: str, servicio: str, memory: Memory | None = None, customer_id: str = "") -> str:
    """Avisa a ESE cliente que su pedido quedó entregado. Sin celular no se envía: solo queda en el log."""
    text = f"Tu pedido de {servicio} quedó listo. El dueño confirma el pago. AXEL no cobra."
    if aviso_cliente(memory, "pedido_listo", phone, text, customer_id) != "enviado":
        print(f"AVISO PEDIDO LISTO sin envío: {text}")
        return ""
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
    enviar(memory, "n3_dueno", os.getenv("WA_OWNER_PHONE") or "", text)
    return text