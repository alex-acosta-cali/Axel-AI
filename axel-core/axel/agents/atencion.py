from __future__ import annotations

from axel.envelope import Envelope
from axel import knowledge_base as kb


def handle(env: Envelope) -> Envelope:
    text = (env.text or "").strip()
    if env.intent == "datos":
        partes = []
        if env.name:
            partes.append(f"nombre: {env.name}")
        if env.phone:
            partes.append(f"celular: {env.phone}")
        if env.email:
            partes.append(f"correo: {env.email}")
        env.reply_text = ("Quedó tu " + " y ".join(partes) + ".") if partes else "Recibí tus datos."
        env.result = "ok"
        return env
    faq = kb.answer(text)
    if faq:
        env.reply_text = faq
    elif env.known_context:
        last = env.known_context[0]
        env.reply_text = (
            f"Te reconozco aunque escribas por {env.channel}. "
            f"La última vez: {last}. Ahora: «{text[:160]}»."
        )
    elif env.intent == "saludo":
        env.reply_text = kb.greeting()
    else:
        env.reply_text = (
            kb.greeting()
            + " Si buscas horarios, ubicación o precios, pregúntame. "
            + f"Recibí: «{text[:120]}»."
        )
    env.result = "ok"
    return env
