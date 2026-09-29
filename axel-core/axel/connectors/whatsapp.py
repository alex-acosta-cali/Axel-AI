from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

import httpx

GRAPH = "https://graph.facebook.com/v21.0"


def firma_valida(raw: bytes, firma: str) -> bool:
    """X-Hub-Signature-256 = 'sha256=' + HMAC-SHA256(body crudo, WA_APP_SECRET). Sin secreto o sin firma: False."""
    secreto = os.getenv("WA_APP_SECRET", "")
    firma = (firma or "").strip()
    if not secreto or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode("utf-8"), raw or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(firma[len("sha256="):].lower(), esperada)


def parse_incoming(body: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            if change.get("field") != "messages":
                continue
            contacts = {
                c.get("wa_id"): (c.get("profile") or {}).get("name")
                for c in value.get("contacts", [])
            }
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                wa_id = msg.get("from", "")
                out.append(
                    {
                        "channel": "whatsapp",
                        "channel_user_id": wa_id,
                        "phone": f"+{wa_id}" if wa_id and not str(wa_id).startswith("+") else wa_id,
                        "name": contacts.get(wa_id),
                        "text": (msg.get("text") or {}).get("body", ""),
                        "raw_ref": msg.get("id"),
                    }
                )
    return out


def mark_read(message_id: str) -> dict[str, Any]:
    token = os.getenv("WA_ACCESS_TOKEN", "")
    phone_id = os.getenv("WA_PHONE_NUMBER_ID", "")
    if not token or not phone_id or not message_id:
        return {"skipped": True}
    url = f"{GRAPH}/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as client:
        res = client.post(url, headers=headers, json=payload)
        return {"status": res.status_code}


def send_text(to_phone: str, text: str) -> dict[str, Any]:
    token = os.getenv("WA_ACCESS_TOKEN", "")
    phone_id = os.getenv("WA_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        return {"skipped": True, "reason": "missing WA_ACCESS_TOKEN or WA_PHONE_NUMBER_ID"}
    to = to_phone.lstrip("+")
    url = f"{GRAPH}/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=20) as client:
        res = client.post(url, headers=headers, json=payload)
        return {"status": res.status_code, "body": res.json() if res.content else {}}