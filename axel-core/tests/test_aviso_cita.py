#!/usr/bin/env python3
"""Aviso al cliente 24 h y 2 h antes de la cita, hora Cali. Base temporal; no envía nada."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from axel import knowledge_base as kb
from axel.agents import reservas
from axel.agents.reservas import _CALI, _NOMBRE_DIA, _ahora_cali, _cuando, avisos_cita, cerrar_recordatorio, cupos_de, proxima_viva, recordatorio_dia
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process


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
        # Con hora exacta (sábado 03/10 11:00) gana cita_at, aunque el texto diga otra cosa.
        conn.execute(
            "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
            " VALUES ('cus_exacta','evt_exacta','whatsapp','reserva','hoy a las 9:30','ok','2026-10-01 13:00:00','2026-10-03 11:00')"
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
    assert avisos(2, 11) == [("evt_exacta", "Recordatorio: tu cita es el sábado 03/10 a las 11:00.")]
    assert avisos(3, 9, 30) == [("evt_exacta", "Recordatorio: tu cita es hoy a las 11:00.")]
    # El saludo («Tu turno es…») también lee cita_at.
    assert proxima_viva(memory, "cus_exacta", datetime(2026, 10, 1, 8, 0, tzinfo=_CALI)) == "sábado 11:00"
    # «citas» del dueño: cita_at si existe; si no, el texto de siempre.
    citas = process(Envelope(text="citas", channel="panel", channel_user_id="alex_pc"), memory).reply_text or ""
    assert "- sábado 03/10 11:00 · " in citas and "- viernes 02/10 9:00 · " in citas, citas

    # "mañana" con ñ o sin tilde es el día siguiente.
    base = datetime(2026, 10, 1, 8, 0, tzinfo=_CALI)
    for texto in ("mañana 11", "MAÑANA a las 11", "manana 11"):
        assert _cuando(texto, base) == (date(2026, 10, 2), 11, 0), texto

    # De punta a punta: "mañana 11" reserva el día siguiente si la franja existe y está libre.
    kb_tmp = Path(tempfile.gettempdir()) / "axel_kb_aviso_cita.json"
    kb_tmp.write_text(json.dumps({"agenda": True, "horario": "8:00 a 19:00", "franjas": [9, 11, 15]}), encoding="utf-8")
    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        # Cupos: la cita con cita_at ocupa el sábado 03/10 a las 11, no el jueves a las 9:30.
        assert list(cupos_de(memory, date(2026, 10, 3))) == [(11, 0)]
        assert cupos_de(memory, date(2026, 10, 1)) == {}

        # Recordatorio del día al dueño: hora Cali, desde que abre (8:00), solo citas de hoy, una vez por día.
        # El día se cierra después de intentar el envío (como en demo.py), no antes.
        def recordatorio(dia: int, hora: int) -> str:
            ahora = datetime(2026, 10, dia, hora, 0, tzinfo=_CALI)
            texto = recordatorio_dia(memory, ahora)
            if texto:
                cerrar_recordatorio(memory, ahora)
            return texto

        assert recordatorio(1, 7) == "", "antes de abrir no sale"
        assert recordatorio_dia(memory, datetime(2026, 10, 1, 8, 0, tzinfo=_CALI)), "sin enviar no cierra el día"
        hoy1 = recordatorio(1, 8)
        assert hoy1 == "Recordatorio AXEL (hoy):\n- 7:30 · sin nombre · sin teléfono\n- 9:30 · sin nombre · sin teléfono", hoy1
        assert recordatorio(1, 12) == "", "una vez por día, aunque AXEL se reinicie"
        assert recordatorio(3, 9) == "Recordatorio AXEL (hoy):\n- 11:00 · sin nombre · sin teléfono", "cita_at, no el texto"
        assert recordatorio(5, 9) == "", "sin citas hoy no sale"
        # Día vacío no se cierra: si a las 10 agendan una de hoy, a las 10 sale el recordatorio.
        with memory._conn() as conn:
            conn.execute(
                "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
                " VALUES ('cus_tarde','evt_tarde','whatsapp','reserva','hoy 15:00','ok','2026-10-05 15:00:00','2026-10-05 15:00')"
            )
        assert recordatorio(5, 10) == "Recordatorio AXEL (hoy):\n- 15:00 · sin nombre · sin teléfono"
        assert recordatorio(5, 11) == "", "ya salió ese día"

        def dice(texto: str, quien: str) -> str:
            out = process(Envelope(text=texto, channel="test", channel_user_id=quien), memory)
            print(quien, repr(texto), "->", out.reply_text)
            return out.reply_text or ""

        # Reloj fijo: lunes 05/10 8:00 Cali. «mañana» = martes 06/10, sin cupo guardado por esta prueba
        # (las fijas son 02/10 9:00, 03/10 11:00 y 05/10 15:00). Con el reloj real chocaba el viernes 02/10.
        reservas._ahora_cali = lambda: datetime(2026, 10, 5, 8, 0, tzinfo=_CALI)
        manana = date(2026, 10, 6)
        dice("quiero una cita", "ana")
        r = dice("mañana 11", "ana")
        assert r.startswith(f"Quedó tu cita: {_NOMBRE_DIA[manana.weekday()]} 11:00"), r
        ana = memory.find_by_identity("test", "ana")["customer_id"]
        assert memory.last_reserva(ana)["cita_at"] == f"{manana.isoformat()} 11:00", memory.last_reserva(ana)
        assert dice("mis citas", "ana") == f"Tus reservas:\n- {_NOMBRE_DIA[manana.weekday()]} {manana.strftime('%d/%m')} 11:00"
        dice("quiero una cita", "beto")
        r = dice("mañana 11", "beto")
        assert r.startswith("Ese cupo ya está tomado."), "franja tomada"
        dice("quiero una cita", "caro")
        assert not dice("mañana 10", "caro").startswith("Quedó tu cita"), "10 no es franja"
    finally:
        reservas._ahora_cali = _ahora_cali
        kb._kb_path = original
        kb_tmp.unlink(missing_ok=True)

    print("OK — aviso 24 h y 2 h, uno por cita y plazo, hora Cali; ni canceladas ni pasadas; mañana con ñ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
