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
    ("cierre", re.compile(r"^(gracias|graciass|listo|ok gracias|chao|adios|adiós|hasta luego|perfecto)\b", re.I)),
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
    if not env.name:
        env.name = ident["customer"].get("name")
    if not env.phone:
        env.phone = ident["customer"].get("phone")
    if not env.email:
        env.email = ident["customer"].get("email")
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
    tel = re.search(
        r"(?:mi celular|mi telefono|mi teléfono|celular|whatsapp|el numero|el número)?\D*((?:3\d{9})|(?:\d{10}))",
        env.text or "",
        re.I,
    )
    if tel and env.intent in {"pregunta", "saludo", "datos"}:
        numero = tel.group(1)
        memory.set_customer_phone(env.customer_id, numero)
        env.phone = numero[-10:]
        env.intent = "datos"
    mail = re.search(
        r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
        env.text or "",
        re.I,
    )
    if mail and env.intent in {"pregunta", "saludo", "datos"}:
        correo = mail.group(1).lower()
        memory.set_customer_email(env.customer_id, correo)
        env.email = correo
        env.intent = "datos"
    open_task = memory.get_open_task(env.customer_id)
    if open_task == "reserva" and env.intent in {"pregunta", "saludo"}:
        env.intent = "reserva"
    if open_task == "reprogramar" and env.intent in {"pregunta", "saludo", "reserva"}:
        env.intent = "reprogramar"
    if open_task == "oferta_cita" and env.intent in {"pregunta", "saludo", "venta"}:
        if re.search(r"^(si|sí|dale|ok|okay|va|claro|reserv)", _norm(env.text or "")):
            env.intent = "reserva"
        elif re.search(r"^(no|despues|después|ahora no)", _norm(env.text or "")):
            memory.set_open_task(env.customer_id, "")
            env.intent = "pregunta"
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
        env = reservas.handle(env, memory)
    else:
        env = atencion.handle(env)
        low = (env.reply_text or "").lower()
        if "reserve un cupo" in low or "te reserve" in low:
            memory.set_open_task(env.customer_id, "oferta_cita")

    if env.result is None:
        env.result = "ok"

    if env.intent == "reserva" and env.result == "pending":
        memory.set_open_task(env.customer_id, "reserva")
    elif env.intent == "reprogramar" and env.result == "pending":
        memory.set_open_task(env.customer_id, "reprogramar")
    elif env.intent in {"reserva", "reprogramar"} and env.result == "ok":
        memory.set_open_task(env.customer_id, "")
    elif env.intent in {"reembolso", "cancelar"}:
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
