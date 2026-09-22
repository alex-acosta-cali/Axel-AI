from __future__ import annotations

from axel.envelope import Envelope
from axel import knowledge_base as kb


def handle(env: Envelope) -> Envelope:
    text = (env.text or "").strip()
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
