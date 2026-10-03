#!/usr/bin/env python3
"""Panel local: tabla de envíos (8 filas, sin texto ni celular entero) y citas con cita_at. Base temporal."""

from __future__ import annotations

import os
import re
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
    # Ladrillo 6: "Citas" lleva la A dorada (demo._a); los demás títulos siguen en texto plano.
    # Ladrillo 8: todo título fijo con "a" la lleva dorada (demo._a). Los que no tienen "a" quedan igual.
    for titulo in ("Reporte de hoy", demo._a("Cupos de la semana"), demo._a("Citas"), "Clientes", demo._a("Catálogo"), "Pedidos", "Envíos"):
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
    assert f"<h2>{demo._a('Inventario')}</h2>" in panel

    # Muro 72: ΛXEL arriba; Día, Conversaciones, Aprobaciones; inventario abajo.
    orden = ["<h1>ΛXEL</h1>", 'id="dia"', 'id="conversaciones"', 'id="aprobaciones"', 'id="inventario"']
    pos = [panel.index(x) for x in orden]
    assert pos == sorted(pos), pos
    dia = panel.split('id="dia"')[1].split('id="conversaciones"')[0]
    for titulo in ("Reporte de hoy", demo._a("Citas"), "Pedidos"):
        assert f"<h2>{titulo}</h2>" in dia, titulo
    # Ladrillo 6: el reporte del panel son cuatro tarjetas, sin texto largo ni línea de pagados.
    reporte = dia.split("<h2>Reporte de hoy</h2>")[1].split("<h2>")[0]
    assert reporte.count("class=\"tarjeta\"") == 4 and "<pre>" not in reporte and "pagado" not in reporte, reporte
    for rotulo in ("citas hoy", "anotado, sin cobro", "entregados", "por aprobar"):
        assert demo._a(rotulo) in reporte, rotulo
    assert "<button" not in reporte, "sin botones nuevos"
    assert "setInterval" in panel and "20000" in panel and "location.reload()" in panel
    # Muro A: cada a/A de un rótulo fijo se ve como la Λ dorada; la palabra va entera (nowrap) y se lee la letra real.
    assert demo._a("Día") == "<span class='palabra'>Dí<span class='a' aria-hidden='true'>&Lambda;</span><span class='sr'>a</span></span>"
    assert demo._a("Pedidos") == "Pedidos" and demo._a("por aprobar").startswith("por <span class='palabra'>")
    assert demo._a("Aprobaciones").count("&Lambda;") == 2
    assert f"<button data-abre=\"aprobaciones\">{demo._a('Aprobaciones')}" in panel
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
    catalogo = f"<h2>{demo._a('Catálogo')}</h2>"
    assert catalogo not in dia and "<h2>Envíos</h2>" not in conversaciones
    assert catalogo in panel.split('id="mi-negocio"')[1].split('id="registro"')[0]
    assert "<h2>Envíos</h2>" in panel.split('id="registro"')[1]

    # Ladrillo 3: hilo de solo lectura. Sin mensajes, "Al día. Nadie espera." Sin caja de enviar.
    assert "Al día. Nadie espera." in demo._chats()[0]
    memory.save_turn(customer_id=gil, event_id="evt_hilo", channel="whatsapp", intent="consulta",
                     text="¿Tienen cupo mañana?", reply="Sí, a las 10:00.", result="ok")
    panel = demo.Handler.__new__(demo.Handler)._panel()
    conversaciones = panel.split('id="conversaciones"')[1].split('id="aprobaciones"')[0]
    assert f"<h2>{demo._a('Chats')}</h2>" in conversaciones and "Gil" in conversaciones and "WhatsApp" in conversaciones
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

    # Ladrillo 7: un clic en el nombre o la fila no decide; solo Aprobar. La fila decidida queda con su hora.
    memory.save_pending_approval({"event_id": "evt_reem", "customer_id": gil, "intent": "reembolso", "why": "prueba",
                                  "requested_action": "Quiero un reembolso", "notify_text": "prueba"})
    estado = lambda: next(p["status"] for p in [dict(r) for r in memory._conn().execute(
        "SELECT status FROM pending_approvals WHERE event_id = 'evt_reem'")])
    h = demo.Handler.__new__(demo.Handler)
    panel = h._panel()
    nombre = panel.split("id=\"aprobaciones\"")[1].split("<td class='nombre'>")[1].split("</td>")[0]
    assert nombre == "Gil" and "<form" not in nombre and "<button" not in nombre, "el nombre es texto"
    for sin_boton in ("", "otra", "pending"):
        h._decidir("evt_reem", sin_boton)  # clic de nombre o fila: no trae una decisión válida
        assert estado() == "pending", sin_boton
    h._decidir("evt_inexistente", "approved")
    assert estado() == "pending"
    antes = len(memory.list_envios(500))
    h._decidir("evt_reem", "approved")
    assert estado() == "approved", "Aprobar sí decide"
    ultimo = memory.list_envios(1)[0]
    assert len(memory.list_envios(500)) == antes + 1 and ultimo["tipo"] == "n3_cliente", ultimo
    assert ultimo["estado"] in {"fallo", "fuera_24h"}, "sin token el aviso no sale y queda escrito"
    panel = h._panel()
    aprob = panel.split('id="aprobaciones"')[1].split('id="inventario"')[0]
    h2_dec = f"<h2>{demo._a('Decididas')}</h2>"
    decididas = aprob.split(h2_dec)[1]
    assert "Gil" in decididas and "<td>aprobada</td>" in decididas and "evt_reem" not in aprob.split(h2_dec)[0]
    assert re.search(r"<td>\d\d/\d\d \d\d:\d\d</td>", decididas), "con la hora"

    # Ladrillo 8: Pedido real o "sin pedido"; el texto del cliente tal cual; Chat abre su hilo; A dorada en los botones.
    for eid, cid, txt in (("evt_p8", gil, "Quiero devolver la cosa"), ("evt_p8b", ana, "Quiero un reembolso")):
        memory.save_pending_approval({"event_id": eid, "customer_id": cid, "intent": "reembolso", "why": "nivel 3",
                                      "requested_action": txt, "notify_text": "x"})
    panel = h._panel()
    pend = panel.split('id="aprobaciones"')[1].split(f"<h2>{demo._a('Decididas')}</h2>")[0]
    fila_gil = pend.split("<td>evt_p8</td>")[1].split("</tr>")[0]
    fila_ana = pend.split("<td>evt_p8b</td>")[1].split("</tr>")[0]
    assert "<td class='pedido'>P00 cosa 0 $1.000</td>" in fila_gil, fila_gil
    assert "<td class='pedido'>sin pedido</td>" in fila_ana, fila_ana
    assert "<td class='dijo'>Quiero devolver la cosa</td>" in fila_gil and "nivel 3" not in pend, "sin motivo inventado"
    for fila in (fila_gil, fila_ana):
        hid = re.search(r"class='ir-chat' data-abre='(hilo-[\w]+)'", fila).group(1)
        assert f"id='{hid}'" in panel, hid
        hilo = panel.split(f"id='{hid}'")[1].split("</dialog>")[0]
        assert "<form method='post'" not in hilo, "el hilo no envía"
    assert f">{demo._a('Aprobar')}</button>" in fila_gil and f">{demo._a('Rechazar')}</button>" in fila_gil
    assert "<td class='nombre'>Gil</td>" in pend, "el nombre no lleva A dorada ni decide"
    assert f"<button class=\"otro\" data-abre=\"registro\">{demo._a('Registro · operador')}</button>" in panel

    print("OK — panel: 8 envíos sin texto ni celular entero; citas con cita_at; inventario 15; hilo solo lectura")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
