"""NO ARRANCAR. Servidor FastAPI viejo, solo de referencia.

No tiene firma de Meta, ni control de wamid repetido, ni panel cerrado a Host público.
El servicio de AXEL es: python -m axel.demo
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from axel.connectors.whatsapp import parse_incoming, send_text
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process

load_dotenv()

DB_PATH = os.getenv("AXEL_DB_PATH", str(Path(__file__).resolve().parents[1] / "axel.db"))
memory = Memory(DB_PATH)
app = FastAPI(title="AXEL Core", version="0.1.0")


class TestMessage(BaseModel):
    text: str
    channel: str = "test"
    channel_user_id: str = "tester"
    phone: str | None = None
    email: str | None = None
    name: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "axel-core"}


@app.get("/webhooks/whatsapp")
def wa_verify(request: Request) -> Response:
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    expected = os.getenv("WA_VERIFY_TOKEN", "axel-verify")
    if mode == "subscribe" and token == expected:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhooks/whatsapp")
async def wa_incoming(request: Request) -> dict:
    body = await request.json()
    accepted = []
    for item in parse_incoming(body):
        env = Envelope(
            channel="whatsapp",
            channel_user_id=item["channel_user_id"],
            phone=item.get("phone"),
            name=item.get("name"),
            text=item.get("text") or "",
            business_id=os.getenv("BUSINESS_ID", "biz_default"),
        )
        out = process(env, memory)
        if out.reply_text:
            send_text(item["channel_user_id"], out.reply_text)
        accepted.append(out.event_id)
    return {"ok": True, "events": accepted}


@app.post("/webhooks/test")
def webhook_test(msg: TestMessage) -> dict:
    env = Envelope(
        channel=msg.channel,
        channel_user_id=msg.channel_user_id,
        business_id=os.getenv("BUSINESS_ID", "biz_default"),
        text=msg.text,
        phone=msg.phone,
        email=msg.email,
        name=msg.name,
    )
    out = process(env, memory)
    return out.model_dump()


@app.get("/audit")
def audit(limit: int = 20) -> dict:
    return {"events": memory.list_audit(limit=limit)}


@app.get("/audit/{event_id}")
def audit_one(event_id: str) -> dict:
    row = memory.get_audit(event_id)
    if not row:
        return {"error": "not_found"}
    return row
