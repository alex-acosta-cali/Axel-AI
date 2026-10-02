#!/usr/bin/env python3
"""Prueba del nucleo: envia un mensaje y verifica orquestador + auditoria.
Muro 68: no llama al 8090 (con el túnel abierto, el 8090 es el VPS). Levanta el demo en un puerto libre
con base y KB temporales. Si no hay puerto, se salta. No escribe en el VPS. Tokens vacíos."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import HTTPServer
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.gettempdir()) / "axel_message"
TMP.mkdir(exist_ok=True)
# demo.py abre la base al importar: AXEL_DB la manda a una temporal para no tocar la real.
os.environ["AXEL_DB"] = str(TMP / "import.db")
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""

from axel import demo  # noqa: E402
from axel import knowledge_base as kb  # noqa: E402
from axel.memory import Memory  # noqa: E402

KB_CITAS = {
    "negocio": "Barberia prueba",
    "rubro": "barberia",
    "agenda": True,
    "horario": "9:00 a 17:00",
    "franjas": [9, 11, 15],
    "servicios": [{"nombre": "corte", "precio": 25000}],
    "politicas": {},
    "faqs": [],
}


def main() -> int:
    db = TMP / "message.db"
    if db.exists():
        db.unlink()
    demo.memory = Memory(str(db))
    kb_tmp = TMP / "kb_message.json"
    kb_tmp.write_text(json.dumps(KB_CITAS, ensure_ascii=False), encoding="utf-8")
    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp

    try:
        server = HTTPServer(("127.0.0.1", 0), demo.Handler)
    except OSError as exc:
        kb._kb_path = original
        print("SALTADA — sin puerto libre:", exc)
        return 0
    base = f"http://127.0.0.1:{server.server_address[1]}"
    assert not base.endswith(":8090")
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        health = httpx.get(f"{base}/health", timeout=5)
        health.raise_for_status()
        print("HEALTH", health.json())

        payload = {
            "text": "Hola, quiero una cita mañana",
            "channel": "test",
            "channel_user_id": "ana",
        }
        res = httpx.post(f"{base}/webhooks/test", json=payload, timeout=10)
        res.raise_for_status()
        body = res.json()
        print("PROCESS")
        print(json.dumps(body, ensure_ascii=False, indent=2))

        assert body["intent"] == "reserva", body
        assert body["agent"] == "reservas", body
        assert body["supervision_level"] == 2, body
        assert body["model"], body
        assert body["result"] in {"ok", "pending"}, body
        assert body["event_id"]

        audit = httpx.get(f"{base}/audit/{body['event_id']}", timeout=5)
        audit.raise_for_status()
        row = audit.json()
        print("AUDIT")
        print(json.dumps(row, ensure_ascii=False, indent=2))
        assert row.get("event_id") == body["event_id"]
        assert row.get("agent") == "reservas"
    finally:
        server.shutdown()
        server.server_close()
        kb._kb_path = original
    print("OK — orquestador procesó y registró la acción, sin el 8090")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
