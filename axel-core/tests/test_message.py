#!/usr/bin/env python3
"""Prueba del nucleo: envia un mensaje y verifica orquestador + auditoria."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8090"


def main() -> int:
    health = httpx.get(f"{BASE}/health", timeout=5)
    health.raise_for_status()
    print("HEALTH", health.json())

    payload = {
        "text": "Hola, quiero una cita mañana",
        "channel": "test",
        "channel_user_id": "ana",
    }
    res = httpx.post(f"{BASE}/webhooks/test", json=payload, timeout=10)
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

    audit = httpx.get(f"{BASE}/audit/{body['event_id']}", timeout=5)
    audit.raise_for_status()
    row = audit.json()
    print("AUDIT")
    print(json.dumps(row, ensure_ascii=False, indent=2))
    assert row.get("event_id") == body["event_id"]
    assert row.get("agent") == "reservas"
    print("OK — orquestador procesó y registró la acción")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
