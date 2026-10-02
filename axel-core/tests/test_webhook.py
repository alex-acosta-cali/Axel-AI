#!/usr/bin/env python3
"""Webhook sin Meta real: firma, wamid repetido, verify token obligatorio y panel cerrado a Host público.
Levanta el demo en un puerto libre con base temporal. No envía nada a WhatsApp."""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import sys
import tempfile
import threading
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.gettempdir()) / "axel_webhook"
TMP.mkdir(exist_ok=True)
os.environ["AXEL_DB"] = str(TMP / "import.db")
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WA_OWNER_PHONE"] = "573000000001"
SECRETO = "secreto-de-prueba"

from axel import demo  # noqa: E402
from axel.memory import Memory  # noqa: E402


def main() -> int:
    db = TMP / "webhook.db"
    if db.exists():
        db.unlink()
    demo.memory = Memory(str(db))
    server = HTTPServer(("127.0.0.1", 0), demo.Handler)
    puerto = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def pide(metodo: str, ruta: str, host: str = "127.0.0.1", body: bytes = b"", extra: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
        conn.putrequest(metodo, ruta, skip_host=True)
        conn.putheader("Host", host)
        for k, v in (extra or {}).items():
            conn.putheader(k, v)
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        res = conn.getresponse()
        cuerpo = res.read().decode("utf-8", "replace")
        conn.close()
        print(metodo, ruta, host, extra or "", "->", res.status, cuerpo[:80].replace("\n", " "))
        return res.status, cuerpo

    try:
        # Panel: local sí; Host público o cabeceras de proxy, 403.
        assert pide("GET", "/")[0] == 200
        assert pide("GET", "/", "localhost:8090")[0] == 200
        for host, extra in (
            ("axel.ejemplo.com", None),
            ("127.0.0.1", {"X-Forwarded-For": "1.2.3.4"}),
            ("127.0.0.1", {"X-Real-IP": "1.2.3.4"}),
            ("127.0.0.1", {"Forwarded": "for=1.2.3.4"}),
            ("algo.ngrok-free.app", None),
        ):
            for metodo, ruta in (("GET", "/"), ("GET", "/audit"), ("POST", "/decidir"), ("POST", "/panel")):
                estado, cuerpo = pide(metodo, ruta, host, extra=extra)
                assert estado == 403 and "solo_local" in cuerpo, (host, extra, ruta, estado)
        assert pide("GET", "/health", "axel.ejemplo.com")[0] == 200, "health sí es público"

        # Verify: sin WA_VERIFY_TOKEN no pasa; con él, solo el token correcto.
        os.environ.pop("WA_VERIFY_TOKEN", None)
        q = "/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token={}&hub.challenge=123"
        assert pide("GET", q.format(""), "axel.ejemplo.com")[0] == 403
        assert pide("GET", q.format("axel-verify"), "axel.ejemplo.com")[0] == 403, "sin valor por defecto"
        os.environ["WA_VERIFY_TOKEN"] = "token-verify-prueba"
        assert pide("GET", q.format("otro"), "axel.ejemplo.com")[0] == 403
        assert pide("GET", q.format("token-verify-prueba"), "axel.ejemplo.com") == (200, "123")

        # Firma: sin secreto, sin firma o con firma mala, 403. Con firma buena, 200.
        body = json.dumps({"entry": [{"changes": [{"field": "messages", "value": {
            "contacts": [{"wa_id": "573000000777", "profile": {"name": "Prueba"}}],
            "messages": [{"from": "573000000777", "id": "wamid.TEST1", "type": "text", "text": {"body": "hola"}}],
        }}]}]}).encode()
        firma = "sha256=" + hmac.new(SECRETO.encode(), body, hashlib.sha256).hexdigest()
        os.environ.pop("WA_APP_SECRET", None)
        assert pide("POST", "/webhooks/whatsapp", "axel.ejemplo.com", body, {"X-Hub-Signature-256": firma})[0] == 403
        os.environ["WA_APP_SECRET"] = SECRETO
        assert pide("POST", "/webhooks/whatsapp", "axel.ejemplo.com", body)[0] == 403
        assert pide("POST", "/webhooks/whatsapp", "axel.ejemplo.com", body, {"X-Hub-Signature-256": "sha256=00"})[0] == 403
        estado, cuerpo = pide("POST", "/webhooks/whatsapp", "axel.ejemplo.com", body, {"X-Hub-Signature-256": firma})
        assert estado == 200 and json.loads(cuerpo)["nuevos"] == 1, cuerpo
        # Meta reintenta el mismo wamid: 200 pero no se procesa otra vez.
        estado, cuerpo = pide("POST", "/webhooks/whatsapp", "axel.ejemplo.com", body, {"X-Hub-Signature-256": firma})
        assert estado == 200 and json.loads(cuerpo)["nuevos"] == 0, cuerpo
        cli = demo.memory.find_by_identity("whatsapp", "573000000777")
        entrantes = [s for s in demo.memory.last_summaries(cli["customer_id"], 10)]
        assert len(entrantes) == 1, entrantes

        # Más de 500 letras no entra a la regex: responde rápido y el servidor sigue vivo.
        largo = "hola" + " " * 3000 + "x"
        for quien in ("tester", "573000000001"):
            cuerpo = json.dumps({"channel_user_id": quien, "phone": quien, "text": largo}).encode()
            estado, resp = pide("POST", "/webhooks/test", body=cuerpo, extra={"Content-Type": "application/json"})
            assert estado == 200 and json.loads(resp)["reply_text"] == "Mensaje muy largo.", resp
        normal = json.dumps({"text": "a" * 500}).encode()
        estado, resp = pide("POST", "/webhooks/test", body=normal, extra={"Content-Type": "application/json"})
        assert estado == 200 and json.loads(resp)["reply_text"] != "Mensaje muy largo.", resp
        assert pide("GET", "/health")[0] == 200
    finally:
        server.shutdown()
        server.server_close()

    print("OK — webhook: panel cerrado a Host público, verify obligatorio, firma, wamid y mensaje largo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
