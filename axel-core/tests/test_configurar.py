#!/usr/bin/env python3
"""Asistente configurar con una KB temporal: con agenda, sin agenda, cancelado a mitad,
reemplazar o sumar servicios. No toca el kb.json real del piloto."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from axel import knowledge_base as kb
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import ONB_PREGUNTA, process

KB_VIEJA = {
    "negocio": "Viejo",
    "rubro": "barberia",
    "agenda": True,
    "horario": "9:00 a 17:00",
    "franjas": [9],
    "servicios": [{"nombre": "corte", "precio": 25000}],
    "politicas": {},
    "faqs": [],
}


def main() -> int:
    real = ROOT / "kb.json"
    antes = real.read_bytes() if real.exists() else None

    tmp = Path(tempfile.gettempdir())
    kb_tmp = tmp / "axel_kb_configurar.json"
    db = tmp / "axel_kb_configurar.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    def dice(texto: str, canal: str = "panel") -> str:
        out = process(Envelope(text=texto, channel=canal, channel_user_id=f"{canal}_conf"), memory)
        print(repr(texto), "->", out.reply_text)
        return out.reply_text or ""

    def reset() -> None:
        kb_tmp.write_text(json.dumps(KB_VIEJA, ensure_ascii=False), encoding="utf-8")

    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        # Con agenda, reemplazando servicios.
        reset()
        assert ONB_PREGUNTA["onb_nombre"] in dice("configurar")
        assert ONB_PREGUNTA["onb_rubro"] in dice("Cafe Luna")
        assert ONB_PREGUNTA["onb_agenda"] in dice("cafeteria")
        assert dice("tal vez").startswith("No entendí"), "respuesta mala no avanza"
        assert ONB_PREGUNTA["onb_horario"] in dice("si")
        assert dice("todo el dia").startswith("No entendí")
        assert ONB_PREGUNTA["onb_franjas"] in dice("de 8am a 7pm")
        assert ONB_PREGUNTA["onb_ubicacion"] in dice("9 11 15")
        assert ONB_PREGUNTA["onb_reemplazo"] in dice("Cra 1 #2-3 Cali")
        assert dice("xx").startswith("No entendí")
        assert dice("reemplazar").startswith("Borré los servicios viejos")
        assert kb.servicios() == []
        assert "Guardé: cafe $4.000, empanada $3.000" in dice("cafe 4000\nempanada $3.000")
        fin = dice("listo")
        assert fin.startswith("Configuración terminada") and "corte" not in fin, fin
        datos = kb.load_kb()
        assert datos["negocio"] == "Cafe Luna" and datos["rubro"] == "cafeteria" and datos["agenda"] is True
        assert datos["horario"] == "8:00 a 19:00" and datos["franjas"] == [9, 11, 15]
        assert datos["ubicacion"] == "Cra 1 #2-3 Cali"
        assert [s["nombre"] for s in kb.servicios()] == ["cafe", "empanada"]

        # Sin agenda, sumando servicios: no pregunta franjas.
        reset()
        dice("configurar")
        dice("Ferre Uno")
        dice("ferreteria")
        dice("no")
        assert ONB_PREGUNTA["onb_ubicacion"] in dice("de 8 a 18")
        assert ONB_PREGUNTA["onb_reemplazo"] in dice("Calle 5")
        assert dice("sumar").startswith("Dejo los servicios que hay")
        dice("clavo 500")
        dice("listo")
        assert kb.agenda() is False
        assert [s["nombre"] for s in kb.servicios()] == ["corte", "clavo"]

        # Sin servicios guardados no pregunta reemplazar o sumar.
        kb_tmp.write_text(json.dumps({**KB_VIEJA, "servicios": []}), encoding="utf-8")
        dice("configurar")
        dice("Nuevo")
        dice("tienda")
        dice("no")
        dice("de 8 a 18")
        assert ONB_PREGUNTA["onb_servicios"] in dice("Calle 6")
        dice("listo")

        # Cancelado a mitad: lo respondido queda guardado.
        reset()
        dice("configurar")
        dice("Mitad")
        assert dice("cancelar configurar").startswith("Salí de la configuración")
        assert kb.load_kb()["negocio"] == "Mitad" and kb.load_kb()["rubro"] == "barberia"
        assert dice("hola").startswith("Hola"), "después de cancelar ya no está en el asistente"

        # Un cliente no arranca el asistente.
        assert ONB_PREGUNTA["onb_nombre"] not in dice("configurar", canal="whatsapp")

        # Cliente: sinónimos, precios gana, ubicación y políticas vacías.
        kb_tmp.write_text(json.dumps({**KB_VIEJA, "ubicacion": "Cra 9 Cali"}), encoding="utf-8")
        # AXEL acaba de preguntar el nombre: una pregunta no se guarda como nombre.
        assert dice("donde quedan", canal="whatsapp") == "Cra 9 Cali"
        ficha = dice("mi ficha", canal="whatsapp")
        assert "sin nombre" in ficha and "pedido" not in ficha, "sin pedidos no inventa línea"
        assert dice("quiero cortarme el pelo", canal="whatsapp").startswith("Corte: $25.000")
        assert dice("precios y quiero cortarme el pelo", canal="whatsapp").startswith("Lista: corte $25.000")
        assert "Cra" not in dice("donde pago", canal="whatsapp")
        assert dice("que garantia tienen", canal="whatsapp") == kb.NO_HAY

        # Pedidos: fila en la tabla, no nota. Nota vieja se pasa una vez.
        assert dice("me lo llevo el corte", canal="whatsapp").startswith("Pedido anotado: corte $25.000")
        cid = memory.list_pedidos()[0]["customer_id"]
        memory.add_note(cid, "Pedido piloto barba $10.000 (sin cobro)")
        memory = Memory(str(db))
        memory = Memory(str(db))
        filas = [(p["servicio"], p["precio"]) for p in memory.list_pedidos()]
        assert sorted(filas) == [("barba", 10000), ("corte", 25000)], filas
        lista = dice("pedidos")
        assert "corte $25.000" in lista and "barba $10.000" in lista, lista
        assert re.search(r"Último pedido: barba \$10\.000, \d\d/\d\d \d\d:\d\d\.$", dice("mi ficha", canal="whatsapp"))

        kb_tmp.write_text(json.dumps({**KB_VIEJA, "servicios": []}), encoding="utf-8")
        assert "$" not in dice("cuanto vale cortarme el pelo", canal="whatsapp"), "sin corte no inventa precio"
    finally:
        kb._kb_path = original
        kb_tmp.unlink(missing_ok=True)

    assert (real.read_bytes() if real.exists() else None) == antes, "se tocó el kb.json real"
    print("OK — configurar con y sin agenda, cancelar, reemplazar o sumar; kb.json real intacto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
