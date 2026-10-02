#!/usr/bin/env python3
"""Muro 67: regex que no se cuelga. Textos de 200 letras raras responden en menos de 1 segundo,
en el alta del dueño, en sus comandos y del cliente. Más de 500: "Mensaje muy largo.".
KB y base temporales. Tokens vacíos: nada sale a WhatsApp. No toca el kb.json real."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WA_OWNER_PHONE"] = "573000000001"
DUENO, ANA = "573000000001", "573000000002"

from axel import knowledge_base as kb  # noqa: E402
from axel.envelope import Envelope  # noqa: E402
from axel.memory import Memory  # noqa: E402
from axel.orchestrator import MENSAJE_LARGO, ONB_PREGUNTA, process  # noqa: E402

KB_TIENDA = {
    "negocio": "Tienda regex",
    "rubro": "tienda",
    "agenda": False,
    "horario": "8:00 a 18:00",
    "franjas": [],
    "servicios": [],
    "politicas": {},
    "faqs": [],
}

# 200 letras raras: espacios largos, signos y cifras sueltas donde la regex vieja se repartía de mil formas.
RARAS = [
    t[:199] + "!"
    for t in (
        "a" + " " * 300,
        "hola" + " " * 300,
        "a " + "1 " * 150,
        "a" + " $" * 150,
        "1." * 150,
        "9 p.m. " * 40,
    )
]
COMANDOS = [
    "agrega servicio a" + " " * 180 + "x",
    "cambia el precio de a" + " " * 178 + "x",
    "stock a" + " " * 190 + "x",
    "producto a" + " " * 188 + "| b",
    "producto a |" + " " * 180 + "b | c | x",
    "producto " + "a | " * 48,
    "franjas " + "9 , " * 48 + "x",
    "agrega pregunta a" + " respuesta" * 10 + " " * 80 + "x",
]


def main() -> int:
    real = ROOT / "kb.json"
    antes = real.read_bytes() if real.exists() else None

    tmp = Path(tempfile.gettempdir())
    kb_tmp = tmp / "axel_kb_regex.json"
    kb_tmp.write_text(json.dumps(KB_TIENDA, ensure_ascii=False), encoding="utf-8")
    ultima = kb_tmp.with_name(kb_tmp.stem + ".ultima.json")
    if ultima.exists():
        ultima.unlink()
    db = tmp / "axel_regex.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        def dice(texto: str, quien: str = DUENO, canal: str = "whatsapp") -> str:
            t = time.perf_counter()
            out = process(Envelope(text=texto, channel=canal, channel_user_id=quien), memory)
            dura = time.perf_counter() - t
            print(quien[-1], repr(texto[:30]), len(texto), "letras", f"{dura:.3f}s", "->", (out.reply_text or "")[:60])
            assert dura < 1, f"{dura:.2f}s con {texto[:30]!r}"
            return out.reply_text or ""

        # Alta del dueño hasta servicios: ahí corría la regex cúbica.
        assert ONB_PREGUNTA["onb_nombre"] in dice("configurar", "panel_regex", "panel")
        dice("Tienda regex", "panel_regex", "panel")
        dice("tienda", "panel_regex", "panel")
        assert ONB_PREGUNTA["onb_horario"] in dice("no", "panel_regex", "panel")
        assert ONB_PREGUNTA["onb_ubicacion"] in dice("de 8am a 6pm", "panel_regex", "panel")
        paso = dice("Cra 1 #2-3 Cali", "panel_regex", "panel")
        assert ONB_PREGUNTA["onb_servicios"] in paso, paso
        for texto in RARAS:
            assert len(texto) == 200, len(texto)
            dice(texto, "panel_regex", "panel")
        # La línea buena sigue entrando igual que antes.
        assert "Guardé: cafe $4.000, corte $15.000" in dice("cafe 4000\ncorte $ 15.000 pesos.", "panel_regex", "panel")
        dice("listo", "panel_regex", "panel")

        # Comandos del dueño y textos del cliente.
        for texto in COMANDOS + RARAS:
            dice(texto, DUENO)
        for texto in RARAS + COMANDOS:
            dice(texto, ANA)
        assert dice("producto A1 | tela | 10000 | 4", DUENO) == "Listo, producto A1 tela $10.000 · stock 4."

        # Más de 500 letras: no entra a la regex.
        for quien in (DUENO, ANA):
            assert dice("a" + " " * 3000 + "!", quien) == MENSAJE_LARGO
    finally:
        kb._kb_path = original

    despues = real.read_bytes() if real.exists() else None
    assert antes == despues, "el kb.json real cambió"
    print("OK — regex: 200 letras raras en menos de 1 s (alta, dueño y cliente); más de 500, Mensaje muy largo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
