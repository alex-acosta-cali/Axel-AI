#!/usr/bin/env python3
"""Muro G: alerta de cierre al dueño. Una vez al día, a la hora de cierre, si hay pendientes o pedidos anotados.
Base y KB temporales; tokens vacíos: no envía nada de verdad."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WA_OWNER_PHONE"] = "573000000001"

from axel import knowledge_base as kb  # noqa: E402
from axel import notify  # noqa: E402
from axel.agents.reservas import _ahora_cali  # noqa: E402
from axel.memory import Memory  # noqa: E402
from axel.orchestrator import ALERTA_CIERRE, alerta_cierre, enviar_alerta_cierre  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.gettempdir())
    db = tmp / "axel_alerta_cierre.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))
    kb_tmp = tmp / "axel_kb_alerta_cierre.json"
    kb_tmp.write_text(json.dumps({"negocio": "Prueba", "horario": "8:00 a 19:00"}), encoding="utf-8")
    original, envio_real = kb._kb_path, notify.send_text
    kb._kb_path = lambda: kb_tmp
    salidas = []
    notify.send_text = lambda destino, texto: salidas.append(destino) or {"skipped": True}
    try:
        assert kb.get_hours()[1] == (19, 0), kb.get_hours()
        cierre = _ahora_cali().replace(hour=19, minute=0, second=0, microsecond=0)
        alertas = lambda: [e for e in memory.list_envios(50) if e["tipo"] == ALERTA_CIERRE]

        # Antes del cierre: nada. A la hora de cierre sin pendientes ni anotados: no escribe.
        assert alerta_cierre(memory, cierre - timedelta(minutes=1)) == ""
        assert enviar_alerta_cierre(memory, cierre) == "" and not alertas(), "si no hay, no escribe"

        # Un pendiente y dos pedidos: uno anotado, uno entregado (no cuenta).
        cli = memory.identify_customer(business_id="biz_default", channel="whatsapp", channel_user_id="573001112233",
                                       phone="3001112233", name="Gil")["customer"]["customer_id"]
        memory.save_pending_approval({"event_id": "evt_1", "customer_id": cli, "intent": "reembolso", "why": "x",
                                      "requested_action": "Quiero un reembolso", "notify_text": "x"})
        memory.add_pedido(cli, "corte", 25000)
        memory.add_pedido(cli, "barba", 10000)
        with memory._conn() as conn:
            conn.execute("UPDATE pedidos SET estado = 'entregado' WHERE servicio = 'barba'")
        texto = alerta_cierre(memory, cierre)
        assert texto.startswith("Cierre del día: 1 por aprobar y 1 pedido anotado por $25.000."), texto
        assert "AXEL no cobra." in texto
        # Muro H: plural correcto.
        memory.add_pedido(cli, "cera", 8000)
        assert "y 2 pedidos anotados por $33.000." in alerta_cierre(memory, cierre)
        with memory._conn() as conn:
            conn.execute("DELETE FROM pedidos WHERE servicio = 'cera'")

        # Día 1: el dueño nunca escribió por WhatsApp: fila fuera_24h, sin envío real.
        assert enviar_alerta_cierre(memory, cierre) == "fuera_24h"
        assert len(alertas()) == 1 and alertas()[0]["estado"] == "fuera_24h" and not salidas
        # Mismo día: no se repite, aunque siga habiendo pendientes.
        assert enviar_alerta_cierre(memory, cierre + timedelta(hours=2)) == "" and len(alertas()) == 1

        # Día 2: el dueño escribió hace 30 h: fuera de 24 h, sin envío.
        dueno = memory.identify_customer(business_id="biz_default", channel="whatsapp",
                                         channel_user_id="573000000001", phone="3000000001")["customer"]["customer_id"]
        memory.save_turn(customer_id=dueno, event_id="evt_d", channel="whatsapp", intent="admin",
                         text="reporte", reply="", result="ok")
        with memory._conn() as conn:
            conn.execute("UPDATE messages SET created_at = datetime('now', '-30 hours') WHERE customer_id = ?", (dueno,))
        with memory._conn() as conn:  # pasa un día: la alerta de ayer queda ayer
            conn.execute("UPDATE envios SET created_at = datetime(created_at, '-1 day') WHERE tipo = ?", (ALERTA_CIERRE,))
        assert enviar_alerta_cierre(memory, cierre) == "fuera_24h" and not salidas
        assert enviar_alerta_cierre(memory, cierre) == "" and len(alertas()) == 2

        # Día 3: el dueño escribió hace poco: se intenta. Sin token no sale y queda fallo.
        with memory._conn() as conn:
            conn.execute("UPDATE envios SET created_at = datetime(created_at, '-1 day') WHERE tipo = ?", (ALERTA_CIERRE,))
        memory.save_turn(customer_id=dueno, event_id="evt_d2", channel="whatsapp", intent="admin",
                         text="hola", reply="", result="ok")
        assert enviar_alerta_cierre(memory, cierre) == "fallo"
        assert salidas == ["573000000001"], salidas
        assert [e["estado"] for e in alertas()] == ["fallo", "fuera_24h", "fuera_24h"]
    finally:
        kb._kb_path, notify.send_text = original, envio_real

    print("OK — alerta de cierre: una vez al día, solo si hay algo, fuera_24h sin ventana del dueño")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
