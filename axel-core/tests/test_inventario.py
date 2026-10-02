#!/usr/bin/env python3
"""Muros 34 a 42: business_id, inventario, referencia, estados, KB segura, aprobar N, pedir por código, foto.
Tokens vacíos: nada sale a WhatsApp. No toca el kb.json real del piloto."""

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

from axel import knowledge_base as kb
from axel.connectors.whatsapp import parse_incoming
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import FOTO_COMPROBANTE, FOTO_PRODUCTO, PEDIDO_FALTA_PAGO, REF_APROBAR_AYUDA, process

KB_TIENDA = {
    "negocio": "Tienda de prueba",
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
    kb_tmp = tmp / "axel_kb_inventario.json"
    kb_tmp.write_text(json.dumps(KB_TIENDA, ensure_ascii=False), encoding="utf-8")
    ultima = kb_tmp.with_name(kb_tmp.stem + ".ultima.json")
    if ultima.exists():
        ultima.unlink()
    db = tmp / "axel_inventario.db"
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

        # Muro 36: el dueño carga inventario corto. Muro 39: se guarda con copia.
        r = dice("producto CAF01 | cafe molido | 12000 | 2", DUENO)
        assert "CAF01 cafe molido $12.000" in r and "stock 2" in r, r
        r = dice("producto CAF02 | cafe grano | 15000 | 0", DUENO)
        assert "stock 0" in r, r
        assert ultima.exists(), "falta la copia kb.ultima.json"

        # Muro 34-35: otro business_id no ve la KB ni el inventario del piloto.
        assert kb.load_kb("biz_otro").get("productos") is None
        assert kb.buscar_producto("CAF01")

        # Muro 37: referencia con inventario da precio y stock; sin inventario no hay precio.
        r = dice("ref CAF01", ANA, "Ana")
        assert r.startswith("CAF01 cafe molido: $12.000. Stock 2."), r

        # Muro 41: CAF01 se anota con precio de venta. Con business_id.
        r = dice("me lo llevo CAF01", ANA, "Ana")
        assert r.startswith("Pedido anotado: CAF01 cafe molido $12.000"), r
        pedidos = memory.list_pedidos()
        assert len(pedidos) == 1 and pedidos[0]["estado"] == "anotado", pedidos
        # Muro 45: me lo llevo no descuenta.
        assert kb.buscar_producto("CAF01")["stock"] == 2
        with memory._conn() as conn:
            fila = conn.execute("SELECT business_id FROM pedidos").fetchone()
        assert fila[0] == "biz_default", fila

        # Muro 41: sin stock no se anota.
        r = dice("me lo llevo CAF02", LUIS, "Luis")
        assert r.startswith("No hay CAF02 ahora."), r
        assert len(memory.list_pedidos()) == 1

        # Muro 46: contacto del proveedor. Se guarda, no se le escribe. El cliente no lo cambia.
        r = dice("contacto proveedor 300 123 4567", LUIS, "Luis")
        assert r.startswith("Eso solo lo cambia el dueño."), r
        envios_antes = len(memory.list_envios(100))
        r = dice("contacto proveedor 300 123 4567", DUENO)
        assert r == "Listo, contacto proveedor: 3001234567. AXEL no le escribe.", r
        assert kb.proveedor_contacto() == "3001234567"
        assert len(memory.list_envios(100)) == envios_antes

        # Muro 37/41: código raro no se anota. Nota al dueño con el proveedor, sin precio ni costo inventado.
        r = dice("lo compro XYZ9", LUIS, "Luis")
        assert "XYZ9" in r and "$" not in r, r
        assert len(memory.list_pedidos()) == 1
        refs = [p for p in memory.list_pending() if p["intent"] == "referencia"]
        assert len(refs) == 1 and "Falta tu sí" in refs[0]["requested_action"], refs
        assert "Proveedor: 3001234567." in refs[0]["requested_action"], refs
        assert "3001234567" not in r
        assert not [e for e in memory.list_envios(100) if "3001234567" in str(e["destino"])]

        # Muro 40: sin número se listan los pendientes. No se toma el primero.
        r = dice("aprobar", DUENO)
        assert r.startswith("Pendientes:") and f"#{refs[0]['n']}" in r, r
        assert len(memory.list_pending()) == 1
        r = dice("aprobar 99", DUENO)
        assert r.startswith("No hay pendiente #99."), r

        # Muro 41: aprobar N con precio y plazo. Sin ellos no se resuelve.
        n = refs[0]["n"]
        r = dice(f"aprobar {n}", DUENO)
        assert r == REF_APROBAR_AYUDA, r
        assert len(memory.list_pending()) == 1
        r = dice(f"aprobar {n} 45000 mañana", DUENO)
        assert "XYZ9: $45.000. Entrega: mañana." in r and "AXEL no cobra" in r, r
        assert not memory.list_pending()
        # Muro 41: no hay costo de proveedor en la KB.
        assert "costo" not in kb_tmp.read_text(encoding="utf-8")

        # Muro 42: foto sin descarga. El parser no guarda el id de media.
        cuerpo = {"entry": [{"changes": [{"field": "messages", "value": {"messages": [
            {"from": ANA, "id": "wamid.FOTO1", "type": "image", "image": {"id": "MEDIA123", "mime_type": "image/jpeg"}}
        ]}}]}]}
        msgs = parse_incoming(cuerpo)
        assert len(msgs) == 1 and msgs[0]["foto"] is True and msgs[0]["text"] == "", msgs
        assert "MEDIA123" not in json.dumps(msgs), msgs
        # Con pedido anotado: comprobante. Sin pedido: producto. Al dueño: "Llegó una foto."
        # Muro 55: el pedido anotado pasa a por verificar y el dueño sabe cuál.
        assert dice("", ANA, foto=True) == FOTO_COMPROBANTE
        assert memory.list_pedidos()[0]["estado"] == "por verificar"
        assert dice("", LUIS, foto=True).startswith(FOTO_PRODUCTO)
        fotos = [e["texto"] for e in memory.list_envios(50) if e["tipo"] == "foto"]
        pid = memory.list_pedidos()[0]["pedido_id"]
        assert sorted(fotos) == ["Llegó una foto.", f"Llegó una foto. Pedido {pid} quedó por verificar."], fotos

        # Muro 38: listo sin pagar no entrega. Pagado N usa el # de pedidos. Reporte con estados.
        pid = memory.list_pedidos()[0]["pedido_id"]
        r = dice("pedido listo ana", DUENO)
        assert r == PEDIDO_FALTA_PAGO, r
        r = dice(f"pedido pagado {pid}", DUENO)
        assert r.startswith(f"Pedido #{pid} pagado."), r
        r = dice("pedido listo ana", DUENO)
        assert r.startswith("Entregado: CAF01 cafe molido $12.000") and r.endswith("Stock CAF01: 1."), r
        assert memory.list_pedidos()[0]["estado"] == "entregado"
        r = dice("reporte", DUENO)
        assert "- anotados: 0" in r and "- pagados: 0" in r and "- entregados: 1" in r, r

        # Muro 45: entregado y pagado baja 1. Si queda 0, el siguiente "no hay".
        assert kb.buscar_producto("CAF01")["stock"] == 1
        dice("me lo llevo CAF01", LUIS, "Luis")
        assert kb.buscar_producto("CAF01")["stock"] == 1
        pid = memory.list_pedidos()[0]["pedido_id"]
        dice(f"pedido pagado {pid}", DUENO)
        r = dice("pedido listo luis", DUENO)
        assert r.startswith("Entregado: CAF01") and r.endswith("Stock CAF01: 0."), r
        assert kb.buscar_producto("CAF01")["stock"] == 0
        r = dice("me lo llevo CAF01", ANA, "Ana")
        assert r.startswith("No hay CAF01 ahora."), r

        # Muro 50: cancelar pedido N es del dueño. Anotado pasa a rechazado y suelta la unidad.
        dice("producto CAF03 | cafe tostado | 9000 | 1", DUENO)
        dice("me lo llevo CAF03", ANA, "Ana")
        assert dice("me lo llevo CAF03", LUIS, "Luis").startswith("No hay CAF03 ahora.")
        pid = memory.list_pedidos()[0]["pedido_id"]
        # Muro 56: Luis no cancela el pedido de Ana.
        assert dice(f"cancelar pedido {pid}", LUIS).startswith(f"No tienes pedido #{pid}.")
        assert dice("cancelar pedido", LUIS).startswith("No tienes pedidos para cancelar.")
        assert memory.list_pedidos()[0]["estado"] == "anotado"
        # Muro 58: Ana recibe el aviso de cancelación. Su celular, como lo deja el webhook.
        memory.set_customer_phone(memory.list_pedidos()[0]["customer_id"], ANA)
        assert dice(f"cancelar pedido {pid}", DUENO).startswith(f"Pedido #{pid} cancelado.")
        assert memory.list_pedidos()[0]["estado"] == "rechazado"
        aviso = memory.list_envios(1)[0]
        assert aviso["tipo"] == "pedido_cancelado" and aviso["destino"] and ANA.endswith(aviso["destino"]), aviso
        assert aviso["texto"] == "El dueño canceló tu pedido de CAF03.", aviso
        assert dice("me lo llevo CAF03", LUIS, "Luis").startswith("Pedido anotado: CAF03")
        pid = memory.list_pedidos()[0]["pedido_id"]
        dice(f"pedido pagado {pid}", DUENO)
        assert dice(f"cancelar pedido {pid}", DUENO) == "Ese pedido ya va. No lo cancelo."

        # Muro 52: pagado y con contacto proveedor pasa a en camino. No se le escribe al proveedor.
        # Muro 59: al cliente sí: un solo envío, a Luis.
        memory.set_customer_phone(memory.list_pedidos()[0]["customer_id"], LUIS)
        envios_antes = len(memory.list_envios(100))
        assert dice(f"pedido en camino {pid}", DUENO) == f"Pedido #{pid} en camino. AXEL no le escribe al proveedor."
        assert memory.list_pedidos()[0]["estado"] == "en camino"
        assert len(memory.list_envios(100)) == envios_antes + 1
        aviso = memory.list_envios(1)[0]
        assert aviso["tipo"] == "pedido_en_camino" and aviso["destino"] and LUIS.endswith(aviso["destino"]), aviso
        assert aviso["texto"] == "Tu pedido de CAF03 va en camino.", aviso
        assert dice(f"pedido en camino {pid}", DUENO) == f"No hay pedido #{pid} pagado."
        assert dice(f"pedido en camino {pid}", LUIS, "Luis") != f"Pedido #{pid} en camino. AXEL no le escribe al proveedor."

        # Muro 53: mi pedido. El cliente ve solo los suyos: código, precio, estado.
        r = dice("mi pedido", LUIS, "Luis")
        assert r.startswith("Tus pedidos:\n- CAF03 $9.000 · en camino · "), r
        assert "CAF01 $12.000 · entregado" in r and "cafe" not in r, r
        r = dice("mis pedidos", ANA, "Ana")
        assert "· en camino ·" not in r and "CAF03 $9.000 · rechazado" in r, r
        r = dice("mi pedido", "573000000009", "Nadie")
        assert r.startswith("No tienes pedidos."), r

        # Muro 51: inventario es del dueño. Código, nombre, stock y disponible.
        r = dice("inventario", DUENO)
        assert r.startswith("Inventario:\n"), r
        assert "- CAF01 · cafe molido · stock 0 · disponible 0" in r, r
        assert "- CAF03 · cafe tostado · stock 1 · disponible 0" in r, r
        r = dice("inventario", LUIS, "Luis")
        assert "Inventario:" not in r and "CAF03" not in r and "stock" not in r, r

        # Muro 39: kb.json roto no tumba AXEL. Usa la última copia.
        kb_tmp.write_text("{roto", encoding="utf-8")
        assert kb.buscar_producto("CAF01"), "no usó la última copia"
        r = dice("ref CAF01", LUIS, "Luis")
        assert r.startswith("CAF01 cafe molido: $12.000."), r
    finally:
        kb._kb_path = original

    despues = real.read_bytes() if real.exists() else None
    assert antes == despues, "el kb.json real cambió"
    print("OK — inventario: CAF01 se anota, sin stock no, código raro no, aprobar N con precio y plazo, foto sin descarga")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
