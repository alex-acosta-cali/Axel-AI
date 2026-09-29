#!/usr/bin/env python3
"""Aviso al cliente 24 h y 2 h antes de la cita, hora Cali. Base temporal; no envía nada."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from axel.agents.reservas import _CALI, avisos_cita
from axel.memory import Memory


def main() -> int:
    db = Path(tempfile.gettempdir()) / "axel_aviso_cita.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    # Confirmadas el jueves 01/10/2026 a las 8:00 Cali (13:00 UTC).
    with memory._conn() as conn:
        for event_id, texto in (
            ("evt_25h", "viernes a las 9:00"),
            ("evt_90m", "hoy a las 9:30"),
            ("evt_cancelada", "hoy a las 9:15"),
            ("evt_pasada", "hoy a las 7:30 am"),
        ):
            conn.execute(
                "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at)"
                " VALUES (?,?,'whatsapp','reserva',?,'ok','2026-10-01 13:00:00')",
                (f"cus_{event_id}", event_id, texto),
            )
    # El cliente cancela: la cita queda 'cancelled' y no se avisa.
    assert memory.cancel_last_reserva("cus_evt_cancelada")

    def avisos(dia: int, hora: int, minuto: int = 0) -> list[tuple[str, str]]:
        salida = avisos_cita(memory, datetime(2026, 10, dia, hora, minuto, tzinfo=_CALI))
        out = [(str(f["event_id"]), t) for f, t in salida]
        print(f"{dia:02d}/10 {hora}:{minuto:02d} ->", out)
        return out

    # 8:00: la de 25 h todavía no; la de 90 min dispara el de 2 h y no el de 24 h.
    # La cancelada (9:15) y la que ya pasó (7:30) no avisan.
    assert avisos(1, 8) == [("evt_90m", "Recordatorio: tu cita es hoy a las 9:30.")]
    assert avisos(1, 8, 30) == [], "ya avisada no se repite"
    # 9:00: la de 25 h entra en 24 h; dispara solo el de 24 h.
    assert avisos(1, 9) == [("evt_25h", "Recordatorio: tu cita es el viernes 02/10 a las 9:00.")]
    assert avisos(1, 12) == []
    # Viernes 7:00: 2 h antes.
    assert avisos(2, 7) == [("evt_25h", "Recordatorio: tu cita es hoy a las 9:00.")]
    assert avisos(2, 7, 30) == [] and avisos(2, 10) == [], "sin repetir y nada después de la cita"

    print("OK — aviso 24 h y 2 h, uno por cita y plazo, hora Cali; ni canceladas ni pasadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
