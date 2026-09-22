from __future__ import annotations

import os
from typing import Any, Optional

import httpx


GRAPH = "https://graph.facebook.com/v21.0"


def parse_incoming(body: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            if change.get("field") != "messages":
                continue
            contacts = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
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
