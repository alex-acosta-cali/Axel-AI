#!/usr/bin/env python3
"""Pide un reembolso. AXEL no lo ejecuta, notifica al dueno y deja audit."""

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
    db = Path(tempfile.gettempdir()) / "axel_m4.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    out = process(
        Envelope(
            text="Quiero un reembolso de mi compra de ayer",
            channel="whatsapp",
            channel_user_id="wa_ana",
            phone="+573001112233",
            name="Ana",
        ),
        memory,
    )
    audit = memory.get_audit(out.event_id)
    pending = memory.list_pending()

    print("RESULT", out.result, out.approval_status, out.supervision_level)
    print("WHY", out.why)
    print("NOTIFIED", out.owner_notified)
    print("REPLY", out.reply_text)
    print("AUDIT", audit)
    print("PENDING", pending)

    assert out.supervision_level == 3
    assert out.result == "pending"
    assert out.approval_status == "pending_owner"
    assert out.owner_notified is True
    assert "reembolso" not in (out.reply_text or "").lower() or "dueño" in (out.reply_text or "").lower() or "dueno" in (out.reply_text or "").lower() or "dueño" in (out.reply_text or "")
    # No ejecuto el reembolso: no hay marca executed
    assert out.payload.get("executed") is None
    assert audit and audit["why"]
    assert audit["model"]
    assert pending and pending[0]["event_id"] == out.event_id
    print("OK — AXEL se detuvo y notifico al dueno")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
