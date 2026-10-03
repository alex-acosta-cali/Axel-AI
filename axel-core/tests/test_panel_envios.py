#!/usr/bin/env python3
"""Panel local: tabla de envíos (8 filas, sin texto ni celular entero) y citas con cita_at. Base temporal."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WA_OWNER_PHONE"] = "573000000001"

# demo.py abre la base al importar: AXEL_DB la manda a una temporal para no tocar la real.
TMP = Path(tempfile.gettempdir()) / "axel_panel_envios"
TMP.mkdir(exist_ok=True)
os.environ["AXEL_DB"] = str(TMP / "import.db")

from axel import demo  # noqa: E402
from axel.memory import Memory  # noqa: E402


def main() -> int:
    db = TMP / "panel.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))
    demo.memory = memory

    gil = memory.identify_customer(
        business_id="biz_default", channel="whatsapp", channel_user_id="573001112233", phone="3001112233", name="Gil"
    )["customer"]["customer_id"]
    # 9 envíos: el panel muestra solo los 8 más nuevos.
    memory.add_envio("573009990000", "aviso_2h", "viejo", "enviado")
    memory.add_envio("573001112233", "pedido_listo", "Tu pedido 3001112233 listo", "enviado")
    memory.add_envio("573000000001", "pedido_nuevo", "Pedido nuevo: Gil", "fallo")
    memory.add_envio("573009998877", "aviso_24h", "Recordatorio 3009998877", "fuera_24h")
    memory.add_envio("", "pedido_listo", "sin cel", "sin_celular")
    for _ in range(4):
        memory.add_envio("573000000001", "n3_dueno", "DECISION PENDIENTE", "enviado")

    tabla = demo._tabla_envios()
    print(tabla)
    assert tabla.count("<tr>") == 9, "cabecera + 8 filas"
    assert "aviso_2h" not in tabla, "la más vieja no sale"
    for fragmento in ("<td>Gil</td>", "<td>dueño</td>", "<td>…8877</td>", "<td>—</td>", "<td>fuera_24h</td>"):
        assert fragmento in tabla, fragmento
    for prohibido in ("3001112233", "3009998877", "Tu pedido", "Recordatorio", "DECISION"):
        assert prohibido not in tabla, prohibido

    # Cita con hora exacta: el texto dice otra cosa, el panel usa cita_at.
    with memory._conn() as conn:
        conn.execute(
            "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
            " VALUES (?, 'evt_panel', 'whatsapp', 'reserva', 'hoy a las 9:30', 'ok', '2026-10-01 13:00:00', '2026-10-03 11:00')",
            (gil,),
        )
    panel = demo.Handler.__new__(demo.Handler)._panel()
    assert panel.index("<h2>Reporte de hoy</h2>") < panel.index("<h2>Clientes WhatsApp</h2>")
    # Los 7 bloques del dueño siguen en el panel.
    for titulo in ("Reporte de hoy", "Cupos de la semana", "Citas", "Clientes WhatsApp", "Catálogo", "Pedidos", "Envíos"):
        assert f"<h2>{titulo}</h2>" in panel, titulo
    assert "sábado 03/10 11:00" in panel, "Clientes WhatsApp lee cita_at"
    assert "3001112233" in panel.split("<h2>Clientes WhatsApp</h2>")[1], "el celular sigue en la tabla de clientes"
    assert "3001112233" not in panel.split("<h2>Envíos</h2>")[1].split("<h2>")[0]

    # Muro 65: inventario en el panel. 16 productos, salen 15. Disponible descuenta el pedido abierto.
    productos = [{"codigo": f"P{i:02d}", "nombre": f"cosa {i}", "precio": 1000, "stock": 3} for i in range(16)]
    original = demo.kb.productos
    demo.kb.productos = lambda: productos
    try:
        memory.add_pedido(gil, "P00 cosa 0", 1000)
        tabla = demo._tabla_inventario()
    finally:
        demo.kb.productos = original
    print(tabla)
    assert tabla.count("<tr>") == 16, "cabecera + 15 filas"
    assert "<td>P00</td><td>cosa 0</td><td>3</td><td>2</td>" in tabla, tabla
    assert "P15" not in tabla, "máximo 15"
    assert "<h2>Inventario</h2>" in panel

    # Muro 72: ΛXEL arriba; Día, Conversaciones, Aprobaciones; inventario abajo.
    orden = ["<h1>ΛXEL</h1>", 'id="dia"', 'id="conversaciones"', 'id="aprobaciones"', 'id="inventario"']
    pos = [panel.index(x) for x in orden]
    assert pos == sorted(pos), pos
    dia = panel.split('id="dia"')[1].split('id="conversaciones"')[0]
    for titulo in ("Reporte de hoy", "Citas", "Pedidos"):
        assert f"<h2>{titulo}</h2>" in dia, titulo
    assert "<h2>Últimos</h2>" in panel.split('id="conversaciones"')[1].split('id="aprobaciones"')[0]
    assert "<h2>Pendientes</h2>" in panel.split('id="aprobaciones"')[1].split('id="inventario"')[0]

    # Ladrillo 2: Catálogo vive en Mi negocio; Envíos en Registro (operador). Ni uno ni otro en Día ni Conversaciones.
    orden = ['id="inventario"', 'id="mi-negocio"', 'id="registro"']
    pos = [panel.index(x) for x in orden]
    assert pos == sorted(pos), pos
    conversaciones = panel.split('id="conversaciones"')[1].split('id="aprobaciones"')[0]
    assert "<h2>Catálogo</h2>" not in dia and "<h2>Envíos</h2>" not in conversaciones
    assert "<h2>Catálogo</h2>" in panel.split('id="mi-negocio"')[1].split('id="registro"')[0]
    assert "<h2>Envíos</h2>" in panel.split('id="registro"')[1]

    print("OK — panel: 8 envíos sin texto ni celular entero; citas con cita_at; inventario 15")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
