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
    assert panel.index("<h2>Reporte de hoy</h2>") < panel.index("<h2>Clientes</h2>")
    # Los bloques del dueño siguen en el panel. Ladrillo 4: una sola lista "Clientes" (antes dos tablas).
    for titulo in ("Reporte de hoy", "Cupos de la semana", "Citas", "Clientes", "Catálogo", "Pedidos", "Envíos"):
        assert f"<h2>{titulo}</h2>" in panel, titulo
    assert "<h2>Clientes WhatsApp</h2>" not in panel and panel.count("<h2>Clientes</h2>") == 1
    clientes = panel.split("<h2>Clientes</h2>")[1].split("</table>")[0]
    assert "sábado 03/10 11:00" in clientes, "Clientes lee cita_at"
    assert "3001112233" in clientes, "el celular sigue en la lista de clientes"
    assert "<td>WhatsApp</td>" in clientes and "<th>ID</th>" not in clientes and gil not in clientes, "canal sí, ID no"
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
    # Ladrillo 4: la fila técnica (intent, nivel, hora UTC) sale de Conversaciones y queda en Registro.
    assert "<h2>Últimos</h2>" not in panel.split('id="conversaciones"')[1].split('id="aprobaciones"')[0]
    assert "<h2>Últimos</h2>" in panel.split('id="registro"')[1]
    # Una sola barra "Escribe a AXEL", fuera de las ventanas. Λ dorada en la marca y en las puertas.
    assert panel.count('placeholder="Escribe a AXEL"') == 1
    assert panel.index("</main>") < panel.index('placeholder="Escribe a AXEL"')
    assert '<span class="lambda" aria-hidden="true">Λ</span>' in panel.split('class="puertas"')[1].split("</nav>")[0]
    assert "<h2>Pendientes</h2>" in panel.split('id="aprobaciones"')[1].split('id="inventario"')[0]

    # Ladrillo 2: Catálogo vive en Mi negocio; Envíos en Registro (operador). Ni uno ni otro en Día ni Conversaciones.
    orden = ['id="inventario"', 'id="mi-negocio"', 'id="registro"']
    pos = [panel.index(x) for x in orden]
    assert pos == sorted(pos), pos
    conversaciones = panel.split('id="conversaciones"')[1].split('id="aprobaciones"')[0]
    assert "<h2>Catálogo</h2>" not in dia and "<h2>Envíos</h2>" not in conversaciones
    assert "<h2>Catálogo</h2>" in panel.split('id="mi-negocio"')[1].split('id="registro"')[0]
    assert "<h2>Envíos</h2>" in panel.split('id="registro"')[1]

    # Ladrillo 3: hilo de solo lectura. Sin mensajes, "Al día. Nadie espera." Sin caja de enviar.
    assert "Al día. Nadie espera." in demo._chats()[0]
    memory.save_turn(customer_id=gil, event_id="evt_hilo", channel="whatsapp", intent="consulta",
                     text="¿Tienen cupo mañana?", reply="Sí, a las 10:00.", result="ok")
    panel = demo.Handler.__new__(demo.Handler)._panel()
    conversaciones = panel.split('id="conversaciones"')[1].split('id="aprobaciones"')[0]
    assert "<h2>Chats</h2>" in conversaciones and "Gil" in conversaciones and "WhatsApp" in conversaciones
    assert "Sí, a las 10:00." in conversaciones, "la lista muestra el último texto"
    hilo = panel.split("id='hilo-0'")[1].split("</dialog>")[0]
    assert hilo.index("¿Tienen cupo mañana?") < hilo.index("Sí, a las 10:00."), "del más viejo al más nuevo"
    assert "<form method='post'" not in hilo and "Enviar" not in hilo, "el hilo no envía"
    assert "Instagram" not in panel and "Web" not in panel

    # Hilo sin internos ni borrados. Chat vivo: texto completo, aunque traiga el celular.
    largo = "Mi celular es 3001112233 y quiero saber " + "x" * 120
    memory.save_turn(customer_id=gil, event_id="evt_largo", channel="whatsapp", intent="consulta", text=largo, reply="", result="ok")
    alex = memory.identify_customer(business_id="biz_default", channel="panel", channel_user_id="alex_pc")["customer"]["customer_id"]
    memory.save_turn(customer_id=alex, event_id="evt_int", channel="panel", intent="consulta", text="reporte interno", reply="ok", result="ok")
    ana = memory.identify_customer(
        business_id="biz_default", channel="whatsapp", channel_user_id="573004445566", phone="3004445566", name="Ana"
    )["customer"]["customer_id"]
    memory.save_turn(customer_id=ana, event_id="evt_ana", channel="whatsapp", intent="consulta", text="secreto de Ana", reply="", result="ok")
    with memory._conn() as conn:
        conn.execute("UPDATE customers SET name = NULL, datos_borrados = 1 WHERE customer_id = ?", (ana,))
    chats, hilos = demo._chats()
    assert "reporte interno" not in chats + hilos and "interno" not in chats, "sin internos"
    assert "secreto de Ana" not in chats + hilos and chats.count("Datos borrados") == 1 and "Datos borrados" in hilos
    assert largo in chats and largo in hilos, "texto completo"
    assert memory.list_mensajes(ana), "la base no se borra"

    # Ladrillo 5: la ficha del panel no sale en la lista de clientes, pero sigue en la base. Aviso bajo la barra.
    panel = demo.Handler.__new__(demo.Handler)._panel()
    clientes = panel.split("<h2>Clientes</h2>")[1].split("</table>")[0]
    assert clientes.count("<tr>") == 3, "cabecera + Gil + Ana, sin alex_pc"
    assert memory.find_by_identity("panel", "alex_pc").get("customer_id") == alex, "la ficha no se borra"
    barra = panel.split('class="barra"')[1].split("</div>")[0]
    assert "Un comando de dueño puede avisar al cliente. No le escribe texto libre." in barra

    print("OK — panel: 8 envíos sin texto ni celular entero; citas con cita_at; inventario 15; hilo solo lectura")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
