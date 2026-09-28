#!/usr/bin/env python3
"""KB temporal de ferretería (sin agenda). AXEL lista clavo y pintura, no inventa corte ni da cita.
No toca el kb.json real del piloto."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from axel import knowledge_base as kb
from axel.agents.reservas import SIN_AGENDA
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process

KB_FERRETERIA = {
    "negocio": "Ferretería de prueba",
    "rubro": "ferreteria",
    "agenda": False,
    "horario": "8:00 a 18:00",
    "franjas": [],
    "servicios": [
        {"nombre": "clavo", "precio": 500},
        {"nombre": "pintura", "precio": 18000},
    ],
    "politicas": {},
    "faqs": [],
}
OFRECE_CITA = ("cupo", "reserv", "agend")


def main() -> int:
    real = ROOT / "kb.json"
    antes = real.read_bytes() if real.exists() else None

    tmp = Path(tempfile.gettempdir())
    kb_tmp = tmp / "axel_kb_ferreteria.json"
    kb_tmp.write_text(json.dumps(KB_FERRETERIA, ensure_ascii=False), encoding="utf-8")
    db = tmp / "axel_kb_ferreteria.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        def pregunta(texto: str) -> str:
            out = process(
                Envelope(text=texto, channel="whatsapp", channel_user_id="wa_ferre", name="Ana"),
                memory,
            )
            print(repr(texto), "->", out.reply_text)
            return out.reply_text or ""

        precios = pregunta("precios")
        assert "clavo" in precios and "$500" in precios, precios
        assert "pintura" in precios and "$18.000" in precios, precios
        assert "corte" not in precios.lower(), precios
        assert not any(k in precios.lower() for k in OFRECE_CITA + ("cita",)), precios

        clavo = pregunta("cuanto vale el clavo")
        assert "$500" in clavo, clavo
        assert not any(k in clavo.lower() for k in OFRECE_CITA + ("cita",)), clavo

        cita = pregunta("quiero cita")
        assert cita.startswith(SIN_AGENDA), cita
        assert not any(k in cita.lower() for k in ("cupo", "reserv")), cita
    finally:
        kb._kb_path = original
        kb_tmp.unlink(missing_ok=True)

    assert (real.read_bytes() if real.exists() else None) == antes, "se tocó el kb.json real"
    print("OK — ferretería sin corte y sin cita; kb.json real intacto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
