#!/usr/bin/env python3
"""Un cliente escribe por WhatsApp y luego por Instagram. AXEL lo reconoce."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process


def main() -> int:
    db = Path(tempfile.gettempdir()) / "axel_m3.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    first = process(
        Envelope(
            text="Hola, quiero una cita mañana",
            channel="whatsapp",
            channel_user_id="wa_ana",
            phone="+573001112233",
            name="Ana",
        ),
        memory,
    )
    second = process(
        Envelope(
            text="Seguimos con lo de ayer?",
            channel="instagram",
            channel_user_id="ig_ana",
            phone="+573001112233",
            name="Ana",
        ),
        memory,
    )

    print("MSG1", first.customer_id, first.channel, first.intent, first.reply_text)
    print("MSG2", second.customer_id, second.channel, second.intent, second.reply_text)
    print("IDENTITIES", second.payload.get("identities"))
    print("HISTORY", second.payload.get("history"))

    assert first.customer_id == second.customer_id, "debía ser el mismo cliente"
    assert second.known_context, "debía traer historial"
    assert "whatsapp" in second.known_context[0], second.known_context
    assert "Te reconozco" in (second.reply_text or "")
    channels = {i["channel"] for i in second.payload["identities"]}
    assert channels == {"whatsapp", "instagram"}, channels
    print("OK — mismo customer_id y contexto entre canales")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
