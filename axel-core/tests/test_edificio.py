#!/usr/bin/env python3
"""Edificio 55 a 65: foto a por verificar, cliente cancela y suelta, tienen NOMBRE, producto no se duplica,
borrar con abierto no, tres líneas. Tokens vacíos: nada sale a WhatsApp. No toca el kb.json real."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WA_OWNER_PHONE"] = "573000000001"
DUENO, ANA, LUIS = "573000000001", "573000000002", "573000000003"

from axel import knowledge_base as kb  # noqa: E402
from axel.envelope import Envelope  # noqa: E402
from axel.memory import Memory  # noqa: E402
from axel.orchestrator import FOTO_COMPROBANTE, PEDIDO_YA_VA_CLIENTE, process  # noqa: E402

KB_TIENDA = {
    "negocio": "Tienda edificio",
    "rubro": "tienda",
    "agenda": False,
    "horario": "8:00 a 18:00",
    "franjas": [],
    "servicios": [],
    "politicas": {},
    "faqs": [],
}


def main() -> int:
    real = ROOT / "kb.json"
    antes = real.read_bytes() if real.exists() else None

    tmp = Path(tempfile.gettempdir())
    kb_tmp = tmp / "axel_kb_edificio.json"
    kb_tmp.write_text(json.dumps(KB_TIENDA, ensure_ascii=False), encoding="utf-8")
    ultima = kb_tmp.with_name(kb_tmp.stem + ".ultima.json")
    if ultima.exists():
        ultima.unlink()
    db = tmp / "axel_edificio.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        def dice(texto: str, quien: str = ANA, nombre: str | None = None, foto: bool = False) -> str:
            out = process(
                Envelope(text=texto, channel="whatsapp", channel_user_id=quien, name=nombre, payload={"foto": foto}),
                memory,
            )
            print(quien[-1], repr(texto) + (" [foto]" if foto else ""), "->", out.reply_text)
            return out.reply_text or ""

        def estado(n: int) -> str:
            return next(str(p.get("estado") or "anotado") for p in memory.list_pedidos(500) if int(p["pedido_id"]) == n)

        def ultimo() -> int:
            return max(int(p["pedido_id"]) for p in memory.list_pedidos(500))

        # 63: tres líneas, una mala no tumba las otras.
        r = dice(
            "producto A1 | tela | 10000 | 4\nproducto A2 | hilo | x | 9\nproducto A3 | botón | 500 | 20",
            DUENO,
        )
        assert r.split("\n") == [
            "Listo, producto A1 tela $10.000 · stock 4.",
            "No entendí el precio.",
            "Listo, producto A3 botón $500 · stock 20.",
        ], r
        assert [p["codigo"] for p in kb.productos()] == ["A1", "A3"], kb.productos()

        # 61: el mismo código actualiza nombre, precio y stock. No crea otra fila.
        r = dice("producto A1 | tela azul | 12000 | 5", DUENO)
        assert "actualizado" in r, r
        a1 = [p for p in kb.productos() if p["codigo"] == "A1"]
        assert len(a1) == 1 and a1[0]["nombre"] == "tela azul" and a1[0]["precio"] == 12000 and a1[0]["stock"] == 5, a1

        # 60: tienen NOMBRE. Uno: precio y disponible. Varios: lista sin anotar. Ninguno: no anota.
        dice("producto A4 | tela roja | 9000 | 2", DUENO)
        # El primer mensaje del cliente lleva la nota de datos al final.
        assert dice("tienen botón", ANA, "Ana").startswith("A3 botón: $500. Disponible 20.")
        pedidos_antes = len(memory.list_pedidos(500))
        r = dice("tienen tela", ANA, "Ana")
        assert r.startswith("Tengo:") and "A1" in r and "A4" in r, r
        r = dice("tienen martillo", ANA, "Ana")
        assert r.startswith("No tengo martillo"), r
        assert len(memory.list_pedidos(500)) == pedidos_antes, "tienen no anota"

        # 55: foto con pedido anotado sin pagar pasa a por verificar.
        assert dice("me lo llevo A3", ANA, "Ana").startswith("Pedido anotado: A3")
        n_ana = ultimo()
        assert dice("", ANA, "Ana", foto=True) == FOTO_COMPROBANTE
        assert estado(n_ana) == "por verificar", estado(n_ana)

        # 62: borrar con pedido abierto no. Sin abiertos, sí.
        assert dice("producto borrar A3", DUENO) == "Tiene pedidos abiertos."
        assert kb.buscar_producto("A3")
        assert dice("producto borrar A4", DUENO) == "Listo, borré el producto A4."
        assert not kb.buscar_producto("A4")

        # 56: el cliente cancela lo suyo y suelta la unidad. No el de otro. Pagado ya va.
        assert dice("me lo llevo A1", LUIS, "Luis").startswith("Pedido anotado: A1")
        n_luis = ultimo()
        assert dice(f"cancelar pedido {n_luis}", ANA, "Ana") == f"No tienes pedido #{n_luis}."
        assert estado(n_luis) == "anotado"
        assert memory.pedidos_abiertos("A3") == 1
        assert dice("cancelar pedido", ANA, "Ana") == "Cancelé tu pedido de A3."
        assert estado(n_ana) == "rechazado" and memory.pedidos_abiertos("A3") == 0
        dice(f"pedido pagado {n_luis}", DUENO)
        assert estado(n_luis) == "pagado", estado(n_luis)
        assert dice("cancelar pedido", LUIS, "Luis") == PEDIDO_YA_VA_CLIENTE
        assert estado(n_luis) == "pagado"
    finally:
        kb._kb_path = original

    despues = real.read_bytes() if real.exists() else None
    assert antes == despues, "el kb.json real cambió"
    print("OK — edificio: foto a por verificar, cliente cancela y suelta, tienen nombre, no duplica, borrar con abierto no, tres líneas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
