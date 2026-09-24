from __future__ import annotations

import re

from axel.agents import atencion, escalamiento, reservas
from axel.envelope import Envelope, now_iso
from axel.memory import Memory
from axel.notify import notify_owner
from axel.permissions import classify_level, needs_customer_confirm, needs_owner_approval, reason_for
from axel.router_model import route


INTENTS = [
    ("queja", re.compile(r"queja|reclamo|molesto|pésimo|pesimo|nunca más|abogado", re.I)),
    ("reembolso", re.compile(r"reembols|rembols|devolver plata|devoluci", re.I)),
    ("cancelar", re.compile(r"cancelar (la )?cita|anular reserva", re.I)),
    ("reprogramar", re.compile(r"cambiar (la )?cita|reprogram", re.I)),
    ("reserva", re.compile(r"reserva|agendar|cita|turno|disponib", re.I)),
    ("venta", re.compile(r"precio|cuánto|cuanto cuesta|quiero comprar|cotiz", re.I)),
    ("saludo", re.compile(r"^(hola|buenas|buen día|buenos días|hey)\b", re.I)),
]


def _norm(text: str) -> str:
    raw = (text or "").lower().strip()
    table = str.maketrans("áéíóúü", "aeiouu")
    return raw.translate(table)


def classify_intent(text: str) -> str:
    raw = _norm(text)
    if not raw:
        return "pregunta"
    for name, pattern in INTENTS:
        if pattern.search(raw):
            return name
    return "pregunta"


def pick_agent(intent: str) -> str:
    if intent in {"reserva", "reprogramar", "cancelar"}:
        return "reservas"
    if intent in {"queja", "reembolso", "descuento_grande", "admin"}:
        return "escalamiento"
    if intent == "venta":
        return "atencion"  # ventas reales vienen en un modulo posterior
    return "atencion"


def process(env: Envelope, memory: Memory) -> Envelope:
    ident = memory.identify_customer(
        business_id=env.business_id,
        channel=env.channel,
        channel_user_id=env.channel_user_id,
        phone=env.phone,
        email=env.email,
        name=env.name,
    )
    env.customer_id = ident["customer"]["customer_id"]
    history = memory.last_summaries(env.customer_id)
    env.known_context = [
        f"{h.get('channel')}:{h.get('intent')}:{h.get('summary')}" for h in history
    ]
    env.context_refs = [f"crm:{env.customer_id}"] + [f"hist:{h['event_id']}" for h in history]
    env.payload["identities"] = ident["identities"]
    env.payload["history"] = history

    env.intent = classify_intent(env.text)
    llamado = re.search(r"(?:me llamo|mi nombre es)\s+([a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{2,30})", env.text or "", re.I)
    if llamado:
        nombre = llamado.group(1).strip().title()
        memory.set_customer_name(env.customer_id, nombre)
        env.name = nombre
        env.intent = "datos"
    open_task = memory.get_open_task(env.customer_id)
    if open_task == "reserva" and env.intent in {"pregunta", "saludo"}:
        env.intent = "reserva"
    env.agent = pick_agent(env.intent)
    env.supervision_level = classify_level(env.intent)
    env.why = reason_for(env.intent or "", env.supervision_level)

    decision = route(env.intent)
    env.model = decision.model
    env.model_reason = decision.reason

    if needs_owner_approval(env.supervision_level):
        env = escalamiento.handle(env)
        notify_owner(env, memory)
    elif env.agent == "reservas" or needs_customer_confirm(env.supervision_level):
        env = reservas.handle(env)
    else:
        env = atencion.handle(env)

    if env.result is None:
        env.result = "ok"

    if env.intent == "reserva" and env.result == "pending":
        memory.set_open_task(env.customer_id, "reserva")
    elif env.intent == "reserva" and env.result == "ok":
        memory.set_open_task(env.customer_id, "")
    elif env.intent == "reembolso":
        memory.set_open_task(env.customer_id, "")

    memory.save_turn(
        customer_id=env.customer_id,
        event_id=env.event_id,
        channel=env.channel,
        intent=env.intent or "",
        text=env.text or "",
        reply=env.reply_text or "",
        result=env.result or "",
    )
    memory.write_audit(
        {
            "event_id": env.event_id,
            "received_at": env.received_at,
            "finished_at": now_iso(),
            "channel": env.channel,
            "customer_id": env.customer_id,
            "agent": env.agent,
            "model": env.model,
            "supervision_level": env.supervision_level,
            "approval_status": env.approval_status,
            "input_summary": (env.text or "")[:240],
            "output_summary": (env.reply_text or "")[:240],
            "result": env.result,
            "error": env.error,
            "why": env.why,
            "data_used": ",".join(env.context_refs),
        }
    )
    return env
