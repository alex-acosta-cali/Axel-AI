#!/usr/bin/env python3
"""KB temporal de cafetería (sin agenda). AXEL lista café y empanada, no inventa corte ni ofrece cita.
No toca el kb.json real del piloto."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from axel import knowledge_base as kb
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process

KB_CAFETERIA = {
    "negocio": "Cafetería de prueba",
    "rubro": "cafeteria",
    "agenda": False,
    "agenda_palabras": ["cita", "reservar", "reserva", "turno", "mesa"],
    "horario": "7:00 a 19:00",
    "franjas": [],
    "servicios": [
        {"nombre": "cafe", "precio": 4000},
        {"nombre": "empanada", "precio": 3000},
    ],
    "politicas": {},
    "faqs": [],
}
OFRECE_CITA = ("cita", "cupo", "reserv", "agend")


def main() -> int:
    real = ROOT / "kb.json"
    antes = real.read_bytes() if real.exists() else None

    tmp = Path(tempfile.gettempdir())
    kb_tmp = tmp / "axel_kb_cafeteria.json"
    kb_tmp.write_text(json.dumps(KB_CAFETERIA, ensure_ascii=False), encoding="utf-8")
    db = tmp / "axel_kb_cafeteria.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        def pregunta(texto: str) -> str:
            out = process(
                Envelope(text=texto, channel="whatsapp", channel_user_id="wa_cafe", name="Ana"),
                memory,
            )
            print(repr(texto), "->", out.reply_text)
            return out.reply_text or ""

        precios = pregunta("precios")
        assert "cafe" in precios and "$4.000" in precios, precios
        assert "empanada" in precios and "$3.000" in precios, precios
        assert "corte" not in precios.lower(), precios
        assert not any(k in precios.lower() for k in OFRECE_CITA), precios

        corte = pregunta("cuánto vale el corte")
        assert corte.startswith("No tengo esa información"), corte
        assert not any(k in corte.lower() for k in OFRECE_CITA), corte

        empanada = pregunta("cuánto vale la empanada")
        assert "$3.000" in empanada, empanada
        assert not any(k in empanada.lower() for k in OFRECE_CITA), empanada

        # "mesa" es palabra de agenda, pero sin agenda no se agenda.
        mesa = pregunta("quiero mesa")
        assert mesa == "Este negocio no agenda citas por este canal.", mesa
    finally:
        kb._kb_path = original
        kb_tmp.unlink(missing_ok=True)

    assert (real.read_bytes() if real.exists() else None) == antes, "se tocó el kb.json real"
    print("OK — cafetería sin corte y sin cita; kb.json real intacto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
