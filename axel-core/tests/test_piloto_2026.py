#!/usr/bin/env python3
"""Pack de aceptación piloto 2026, con tokens WA vacíos y KB temporal:
precios desde servicios, sin agenda no ofrece cita, pedido en fila,
pedidos solo para el dueño, reembolso queda N3. No toca el kb.json real."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Sin tokens: nada sale a WhatsApp. Dueño y cliente son números de prueba.
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WA_OWNER_PHONE"] = "573000000001"
DUENO, CLIENTE, AJENO = "573000000001", "573000000002", "573000000003"

from axel import knowledge_base as kb
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process

KB_PILOTO = {
    "negocio": "Cafe Piloto",
    "rubro": "cafeteria",
    "agenda": False,
    "horario": "7:00 a 19:00",
    "servicios": [{"nombre": "cafe", "precio": 4000}, {"nombre": "empanada", "precio": 3000}],
    "politicas": {},
    "faqs": [],
}


def main() -> int:
    real = ROOT / "kb.json"
    antes = real.read_bytes() if real.exists() else None

    tmp = Path(tempfile.gettempdir())
    kb_tmp = tmp / "axel_kb_piloto_2026.json"
    kb_tmp.write_text(json.dumps(KB_PILOTO, ensure_ascii=False), encoding="utf-8")
    db = tmp / "axel_piloto_2026.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    def dice(texto: str, quien: str = CLIENTE):
        out = process(Envelope(text=texto, channel="whatsapp", channel_user_id=quien), memory)
        print(quien[-1], repr(texto), "->", out.reply_text)
        return out

    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        # Precios salen de servicios[].
        precios = dice("precios").reply_text or ""
        assert "Lista: cafe $4.000, empanada $3.000" in precios, precios

        # Sin agenda no ofrece cita.
        for texto in ("hola", "cuanto vale el cafe", "quiero una cita"):
            r = (dice(texto).reply_text or "").lower()
            assert "reserv" not in r and "agendar" not in r and "cupo" not in r, r
        assert kb.agenda() is False

        # "me lo llevo" guarda fila de pedido.
        assert (dice("me lo llevo el cafe").reply_text or "").startswith("Pedido anotado: cafe $4.000")
        filas = [(p["servicio"], p["precio"]) for p in memory.list_pedidos()]
        assert filas == [("cafe", 4000)], filas

        # El dueño ve pedidos; un ajeno no.
        dueno = dice("pedidos", DUENO).reply_text or ""
        assert dueno.startswith("Pedidos:") and "cafe $4.000" in dueno, dueno
        ajeno = dice("pedidos", AJENO).reply_text or ""
        assert "Pedidos:" not in ajeno and "$4.000" not in ajeno, ajeno

        # Reembolso queda en nivel 3, pendiente del dueño, sin ejecutar.
        reembolso = dice("quiero un reembolso de mi compra")
        assert reembolso.supervision_level == 3
        assert reembolso.result == "pending" and reembolso.approval_status == "pending_owner"
        assert reembolso.payload.get("executed") is None
        assert any(p["event_id"] == reembolso.event_id for p in memory.list_pending())

        # KB del piloto (copia del kb.json real, con agenda): "mesa" abre la reserva y pide día y hora.
        kb_tmp.write_bytes(real.read_bytes())
        assert kb.agenda() is True and "mesa" in kb.agenda_palabras()
        for quien, texto in (("573000000004", "reservar mesa"), ("573000000005", "quiero mesa")):
            r = dice(texto, quien).reply_text or ""
            assert "Dime día y hora" in r, r
    finally:
        kb._kb_path = original
        kb_tmp.unlink(missing_ok=True)

    assert (real.read_bytes() if real.exists() else None) == antes, "se tocó el kb.json real"
    print("OK — pack piloto 2026: precios, sin cita, pedido en fila, pedidos solo dueño, reembolso N3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
