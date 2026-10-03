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
    # Muro H: fecha relativa (dentro de 10 días), para que la prueba no dependa del día en que corre.
    from datetime import timedelta as _td
    cita_dia = demo._ahora_cali().date() + _td(days=10)
    cita_txt = f"{demo._NOMBRE_DIA[cita_dia.weekday()]} {cita_dia:%d/%m} 11:00"
    with memory._conn() as conn:
        conn.execute(
            "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
            " VALUES (?, 'evt_panel', 'whatsapp', 'reserva', 'hoy a las 9:30', 'ok', datetime('now', '-1 day'), ?)",
            (gil, f"{cita_dia.isoformat()} 11:00"),
        )
    panel = demo.Handler.__new__(demo.Handler)._panel()
    # Muro I: sin "Reporte de hoy"; el Día sigue antes que Clientes.
    assert panel.index('id="dia"') < panel.index("<h2>Clientes</h2>")
    # Los bloques del dueño siguen en el panel. Ladrillo 4: una sola lista "Clientes" (antes dos tablas).
    # Ladrillo 6: "Citas" lleva la A dorada (demo._a); los demás títulos siguen en texto plano.
    # Ladrillo 8: todo título fijo con "a" la lleva dorada (demo._a). Los que no tienen "a" quedan igual.
    for titulo in (demo._a("Cupos de la semana"), demo._a("Citas"), "Clientes", demo._a("Datos del negocio"), "Pedidos", demo._a("Avisos"), "Eventos"):
        assert f"<h2>{titulo}</h2>" in panel, titulo
    assert "<h2>Clientes WhatsApp</h2>" not in panel and panel.count("<h2>Clientes</h2>") == 1
    clientes = panel.split("<h2>Clientes</h2>")[1].split("</table>")[0]
    # Muro K: Clientes en recuadro con scroll: nombre, canal, celular, correo, última vez, dirección, redes.
    # Ya no lleva la última cita (antes probaba que leía cita_at).
    assert "".join(f"<th>{demo._a(c)}</th>" for c in
                   ("Nombre", "Canal", "Celular", "Correo", "Última vez", "Dirección", "Redes")) in clientes, clientes
    assert cita_txt not in clientes and "<td>—</td><td>aún no</td>" in clientes
    assert '<div class="tabla recuadro">' in panel.split("<h2>Clientes</h2>")[1][:40]
    assert "3001112233" in clientes, "el celular sigue en la lista de clientes"
    assert "<td>WhatsApp</td>" in clientes and "<th>ID</th>" not in clientes and gil not in clientes, "canal sí, ID no"
    # Muro F: "Envíos" pasa a llamarse "Avisos"; sigue sin texto ni celular entero.
    avisos_h2 = f"<h2>{demo._a('Avisos')}</h2>"
    assert "<h2>Envíos</h2>" not in panel
    assert "3001112233" not in panel.split(avisos_h2)[1].split("<h2>")[0]

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
    for titulo in (demo._a("Citas"), "Pedidos"):
        assert f"<h2>{titulo}</h2>" in dia, titulo
    # Muro I: el Día ya no lleva el reporte de cuatro tarjetas (lo reemplazan las casillas del home).
    assert "Reporte de hoy" not in dia and "class=\"tarjeta\"" not in panel
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
    # Muro B: el título "Catálogo" pasa a "Datos del negocio"; los servicios se fueron a Inventario.
    catalogo = f"<h2>{demo._a('Datos del negocio')}</h2>"
    assert catalogo not in dia and avisos_h2 not in conversaciones
    mi_negocio = panel.split('id="mi-negocio"')[1].split('id="registro"')[0]
    assert catalogo in mi_negocio
    assert "<h2>" + demo._a("Servicios") + "</h2>" not in mi_negocio and "<th>" + demo._a("Servicio") + "</th>" not in mi_negocio
    for campo in ("Negocio", "Rubro", "Agenda", "Horario", "Franjas", "Ubicación", "Tono", "Política de cancelación", "Política de garantía"):
        assert f"<th>{demo._a(campo)}</th>" in mi_negocio, campo
    for linea in ("Redes: aún no", "Publicar: aún no", "Otro WhatsApp: aún no"):
        assert f"<p class=\"ficha\">{demo._a(linea)}</p>" in mi_negocio, linea
    # Muro C: el formulario de franjas va antes; las tres líneas finales siguen sin enlace ni botón.
    final = mi_negocio.split(f"<p class=\"ficha\">{demo._a('Redes: aún no')}</p>")[1]
    assert "<a " not in final and "<button" not in final, "las tres líneas van sin enlace ni botón"
    inventario = panel.split('id="inventario"')[1].split('id="mi-negocio"')[0]
    assert "<h2>" + demo._a("Servicios") + "</h2>" in inventario

    # Muro B: servicios con stock o "sin tope", e imagen o "sin imagen". No se suben fotos.
    original = demo.kb.servicios
    demo.kb.servicios = lambda: [{"nombre": "corte", "precio": 25000, "stock": 5},
                                 {"nombre": "barba", "precio": 10000, "imagen": "x.jpg"}]
    try:
        serv = demo._tabla_servicios()
    finally:
        demo.kb.servicios = original
    # Muro J: nombre y precio editables; sin stock en el panel; imagen solo dice si hay. Botón para agregar.
    assert "name='nuevo' value='corte'" in serv and "name='precio' inputmode='numeric' value='25000'" in serv, serv
    assert "name='stock'" not in serv and "sin tope" not in serv, "el servicio no lleva stock en el panel"
    assert "<td>sin imagen</td>" in serv and "<td>con imagen</td>" in serv and "<img" not in serv, serv
    assert "action='/servicio_nuevo'" in serv and "type='file'" not in serv
    assert avisos_h2 in panel.split('id="registro"')[1]

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
    # Muro E: la última columna es Cierre: quedó, apertura, decisión y cómo salió el aviso al cliente.
    assert "Gil" in decididas and "evt_reem" in decididas and "evt_reem" not in aprob.split(h2_dec)[0]
    aviso = "fallo" if ultimo["estado"] == "fallo" else "fuera de 24 h"
    assert re.search(rf"<td class='cierre'>aprobada · abierto \d\d/\d\d \d\d:\d\d · decidido \d\d/\d\d \d\d:\d\d · {aviso}</td>",
                     decididas), decididas
    assert demo._a("AXEL no mueve dinero.") in aprob

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
    # Muro E: Resumen en vez del texto crudo. Sin daño, pérdida ni mal servicio escritos: no se mencionan.
    assert "<td class='resumen'>Pide reembolso. Pedido anotado: P00 cosa 0 $1.000.</td>" in fila_gil, fila_gil
    assert "<td class='resumen'>Pide reembolso. No hay pedido anotado.</td>" in fila_ana, fila_ana
    assert "nivel 3" not in pend and "Menciona" not in pend, "sin motivo inventado"
    for fila in (fila_gil, fila_ana):
        hid = re.search(r"class='ir-chat' data-abre='(hilo-[\w]+)'", fila).group(1)
        assert f"id='{hid}'" in panel, hid
        hilo = panel.split(f"id='{hid}'")[1].split("</dialog>")[0]
        assert "<form method='post'" not in hilo, "el hilo no envía"
    assert f">{demo._a('Aprobar')}</button>" in fila_gil and f">{demo._a('Rechazar')}</button>" in fila_gil
    assert "<td class='nombre'>Gil</td>" in pend, "el nombre no lleva A dorada ni decide"
    assert f"<button class=\"otro\" data-abre=\"registro\">{demo._a('Registro · operador')}</button>" in panel

    # Muro E: resumen con lo que el cliente escribió; pedido solo si está anotado; atrasado a las 4 h.
    r = demo._resumen
    assert r("reembolso", "Llegó dañado y fue un mal servicio", None) == \
        "Pide reembolso. No hay pedido anotado. Menciona daño, mal servicio."
    assert r("reembolso", "se perdió el paquete", None).endswith("Menciona pérdida.")
    assert r("descuento", "quiero precio especial", None) == "Pide descuento. No hay pedido anotado."
    pedidos_x = [{"customer_id": "c1", "servicio": "corte", "precio": 25000, "estado": "entregado"},
                 {"customer_id": "c1", "servicio": "barba", "precio": 10000, "estado": "anotado"}]
    assert demo._pedido_anotado("c1", pedidos_x)["servicio"] == "barba"
    assert demo._pedido_anotado("c1", pedidos_x[:1]) is None, "entregado no cuenta: sin pedido"
    base = demo.datetime(2026, 10, 3, 12, 0)
    assert demo._atrasado("2026-10-03 07:59:00", base) and not demo._atrasado("2026-10-03 08:30:00", base)
    with memory._conn() as conn:
        conn.execute("UPDATE pending_approvals SET created_at = datetime('now', '-5 hours') WHERE event_id = 'evt_p8'")
    pend = h._panel().split('id="aprobaciones"')[1].split(f"<h2>{demo._a('Decididas')}</h2>")[0]
    assert "<span class='atrasado'>atrasado</span>" in pend.split("<td>evt_p8</td>")[1].split("</tr>")[0]
    assert "atrasado" not in pend.split("<td>evt_p8b</td>")[1].split("</tr>")[0]

    # Muro C: el dueño edita precio, stock y franjas en el panel. kb temporal: el real no se toca.
    import json
    from datetime import timedelta
    kb_tmp = TMP / "kb_muro_c.json"
    kb_tmp.write_text(json.dumps({"negocio": "Prueba", "servicios": [{"nombre": "corte", "precio": 25000},
                                                                     {"nombre": "barba", "precio": 10000}],
                                  "franjas": [9, 10, 11]}), encoding="utf-8")
    kb_original = demo.kb._kb_path
    demo.kb._kb_path = lambda: kb_tmp
    try:
        # Muro J (antes Muro C): el servicio edita nombre y precio. Sin stock en el panel.
        g = demo.guardar_servicio
        servicio = demo.kb.buscar_servicio
        assert g("corte", "", "30.000") == "servicio_ok" and servicio("corte")["precio"] == 30000
        assert g("corte", "corte", "") == "precio_vacio" and servicio("corte")["precio"] == 30000, "precio vacío no se guarda"
        assert g("corte", "", "abc") == "precio_mal" and g("corte", "", "0") == "precio_mal"
        assert g("nada", "", "1000") == "servicio_no"
        assert g("corte", "barba", "99999") == "nombre_mal" and servicio("corte")["precio"] == 30000, "repetido: nada"
        assert g("corte", "x", "") == "nombre_mal"
        assert g("corte", "corte de pelo", "25000") == "servicio_ok"
        assert servicio("corte") is None and servicio("corte de pelo")["precio"] == 25000
        assert g("corte de pelo", "corte", "") == "servicio_ok" and servicio("corte")["precio"] == 25000
        # Agregar servicio: mismo campo que "agrega servicio X a N" por WhatsApp.
        assert demo.agregar_servicio("tinte", "40.000") == "servicio_nuevo_ok" and servicio("tinte")["precio"] == 40000
        assert demo.agregar_servicio("tinte", "1000") == "servicio_nuevo_mal" and demo.agregar_servicio("cera", "") == "servicio_nuevo_mal"
        demo.kb.remove_servicio("tinte")
        # El stock del servicio sigue en WhatsApp: stock 0 no se vende.
        h._run({"text": "stock corte 0", "channel": "panel", "channel_user_id": "alex_pc"})
        venta = h._run({"text": "me lo llevo el corte", "channel": "whatsapp", "channel_user_id": "573001112233",
                        "phone": "3001112233"})
        assert venta["reply_text"].startswith("No hay corte ahora."), venta["reply_text"]
        h._run({"text": "stock corte 4", "channel": "panel", "channel_user_id": "alex_pc"})
        assert servicio("corte")["stock"] == 4 and "name='stock'" not in demo._tabla_servicios()

        # Muro J: producto con precio editable y a la venta sí/no, aunque el stock sea 0. El stock no se toca aquí.
        demo.kb.set_producto("CAF01", "cafe molido", 12000, 0)
        gp = demo.guardar_producto
        assert gp("CAF01", "13.000", "si") == "producto_ok"
        caf = demo.kb.buscar_producto("CAF01")
        assert caf["precio"] == 13000 and caf["stock"] == 0 and demo.kb.a_la_venta(caf)
        assert gp("ZZZ", "1000", "si") == "producto_no" and gp("CAF01", "abc", "si") == "producto_mal"
        h._run({"text": "producto CAF01 | cafe molido | 13000 | 5", "channel": "panel", "channel_user_id": "alex_pc"})
        assert gp("CAF01", "", "no") == "producto_ok" and demo.kb.buscar_producto("CAF01")["precio"] == 13000
        h._run({"text": "producto CAF01 | cafe molido | 13000 | 6", "channel": "panel", "channel_user_id": "alex_pc"})
        assert demo.kb.buscar_producto("CAF01")["disponible"] is False, "WhatsApp no borra el no del panel"
        cliente = {"channel": "whatsapp", "channel_user_id": "573001112233", "phone": "3001112233"}
        assert h._run({**cliente, "text": "me lo llevo CAF01"})["reply_text"].startswith("No hay CAF01 ahora."), "no: no se vende"
        assert "Disponible 0." in h._run({**cliente, "text": "tienen cafe molido"})["reply_text"]
        inv = demo._tabla_inventario()
        assert "<td>CAF01</td><td>cafe molido</td><td>6</td><td>6</td>" in inv and "value='13000'" in inv, inv
        assert "<option value='no' selected>no</option>" in inv and "action='/producto'" in inv
        assert gp("CAF01", "", "si") == "producto_ok"
        assert h._run({**cliente, "text": "me lo llevo CAF01"})["reply_text"].startswith("Pedido anotado: CAF01")
        with memory._conn() as conn:
            conn.execute("DELETE FROM pedidos WHERE servicio LIKE 'CAF01%'")
        assert demo._a("Tercero de compra: aún no") in h._panel().split('id="mi-negocio"')[1]

        # Franjas: repetidas se ignoran; una inválida no guarda nada; la cita confirmada no se borra.
        dia = demo._ahora_cali().date() + timedelta(days=1)
        if dia.weekday() == 6:
            dia += timedelta(days=1)
        with memory._conn() as conn:
            conn.execute(
                "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
                " VALUES (?, 'evt_franja', 'whatsapp', 'reserva', 'mañana 10', 'ok', datetime('now'), ?)",
                (gil, f"{dia.isoformat()} 10:00"),
            )
        gf = demo.guardar_franjas
        assert gf("8, 25") == "franjas_mal" and demo.kb.load_kb()["franjas"] == [9, 10, 11], "inválida: no se guarda"
        assert gf("8, x") == "franjas_mal" and gf("") == "franjas_mal" and gf("8:75") == "franjas_mal"
        assert gf("14, 8, 14, 16") == "franjas_ok"
        assert demo.kb.load_kb()["franjas"] == [8, 14, 16], "repetida ignorada, en orden"
        assert any(c["event_id"] == "evt_franja" for c in memory.list_confirmed_reservas(50)), "la cita no se borra"
        assert any("Fuera de franja" in l and "10" in l for l in demo._fuera_de_franja()), "queda fuera de franja"
        assert gf("6, 8:30") == "franjas_fuera" and demo.kb.load_kb()["franjas"] == [6, "8:30"]

        # Muro J: cupos de color por semana. Clic en verde = anotar (queda sin confirmar y ocupa el cupo).
        assert gf("9, 10, 11") == "franjas_ok"
        with memory._conn() as conn:
            conn.execute(
                "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
                " VALUES (?, 'evt_cancelada', 'whatsapp', 'reserva', 'cancelada', 'cancelled', datetime('now'), ?)",
                (gil, f"{dia.isoformat()} 09:00"),
            )
        ac = demo.anotar_cupo
        assert ac(dia.isoformat(), "11:00", gil, "corte") == "cupo_ok"
        assert ac(dia.isoformat(), "11:00", gil, "") == "cupo_tomado", "el mismo cupo no se anota dos veces"
        assert ac(dia.isoformat(), "10:00", gil, "") == "cupo_tomado", "la cita confirmada ocupa"
        ayer = demo._ahora_cali().date() - timedelta(days=1)
        domingo = demo._ahora_cali().date() + timedelta(days=6 - demo._ahora_cali().date().weekday() + 7)
        assert ac(ayer.isoformat(), "11:00", gil, "") == "cupo_mal" and ac(domingo.isoformat(), "11:00", gil, "") == "cupo_mal"
        assert ac(dia.isoformat(), "12:00", gil, "") == "cupo_mal" and ac("x", "11:00", gil, "") == "cupo_mal"
        assert ac(dia.isoformat(), "9:00", "", "") == "cliente_mal" and ac(dia.isoformat(), "9:00", alex, "") == "cliente_mal"
        anotada = demo.memory.list_reservas_por_resultado("por_confirmar")
        assert len(anotada) == 1 and anotada[0]["summary"] == "Anotada por el dueño: corte" and anotada[0]["channel"] == "panel"
        # WhatsApp usa las mismas franjas y ve el cupo ocupado.
        assert (11, 0) in demo.cupos_de(memory, dia) and (9, 0) not in demo.cupos_de(memory, dia), "cancelada libera"
        # Sin confirmar no cuenta como cita confirmada.
        assert all(c["event_id"] != anotada[0]["event_id"] for c in memory.list_confirmed_reservas(50))
        dia_html = h._panel("cupo_ok").split('id="dia"')[1].split('id="conversaciones"')[0]
        assert demo.AVISOS["cupo_ok"] in dia_html
        assert dia_html.count("class='semana'") == demo.SEMANAS_CUPOS and dia_html.count(" hidden>") == demo.SEMANAS_CUPOS - 1
        assert "data-semana-paso='-1'" in dia_html and "data-semana-paso='1'" in dia_html
        assert "class='cupo sin-confirmar'>sin confirmar · Gil</td>" in dia_html
        assert "class='cupo confirmada'>confirmada · Gil</td>" in dia_html
        assert "class='cupo cancelada'>cancelada · Gil</td>" in dia_html
        assert f"data-fecha='{dia.isoformat()}' data-hora='9:00'" not in dia_html, "cancelada se ve roja, no verde"
        assert "class='cupo libre'><button type='button' class='anotar'" in dia_html and "id='anotar-cupo'" in dia_html
        anotar = dia_html.split("id='anotar-cupo'")[1].split("</dialog>")[0]
        assert f"value='{gil}'" in anotar and f"value='{alex}'" not in anotar, "el dueño no es cliente"
        assert ".cupos{overflow:auto;height:300px" in h._panel(), "alto fijo y scroll"

        # El panel muestra el aviso fijo y el formulario de franjas con lo guardado.
        panel = h._panel("franjas_mal")
        mi_negocio = panel.split('id="mi-negocio"')[1].split('id="registro"')[0]
        assert demo.AVISOS["franjas_mal"] in mi_negocio and 'action="/franjas"' in mi_negocio
        assert 'value="9:00, 10:00, 11:00"' in mi_negocio, "el campo trae las franjas guardadas"
        assert demo.AVISOS["franjas_mal"] not in h._panel("<script>"), "solo códigos conocidos"
        assert "<script>alert" not in h._panel("<script>alert(1)</script>")

        # Muro D: cuatro casillas en el home, sin "sin cobro". Cada una abre sus clientes con canal.
        with memory._conn() as conn:
            conn.execute("DELETE FROM pedidos")
            conn.execute("UPDATE pending_approvals SET status = 'approved' WHERE status = 'pending'")
        hoy_cita = f"{demo._ahora_cali().date().isoformat()} 15:00"
        with memory._conn() as conn:
            conn.execute(
                "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
                " VALUES (?, 'evt_hoy', 'whatsapp', 'reserva', 'hoy 3', 'ok', datetime('now'), ?)", (gil, hoy_cita))
        memory.add_pedido(gil, "corte", 25000)            # anotado hoy
        memory.add_pedido(gil, "barba", 10000)            # entregado hoy
        memory.add_pedido(alex, "tinte", 40000)           # rechazado: no cuenta
        with memory._conn() as conn:
            conn.execute("UPDATE pedidos SET estado = 'pagado' WHERE servicio = 'barba'")
            conn.execute("UPDATE pedidos SET estado = 'rechazado' WHERE servicio = 'tinte'")
            conn.execute("INSERT INTO pedidos(customer_id, servicio, precio, created_at, estado)"
                         " VALUES (?, 'cera', 8000, '2020-01-01 12:00:00', 'pagado')", (gil,))  # abierto, de otro día
            # Entregado viejo, sin delivered_at: no cuenta en Cerrado y su hora queda "—".
            conn.execute("INSERT INTO pedidos(customer_id, servicio, precio, created_at, estado)"
                         " VALUES (?, 'uñas', 5000, '2020-01-01 12:00:00', 'entregado')", (gil,))
        # Muro H: entregar guarda delivered_at; Cerrado usa esa hora.
        barba = next(p for p in memory.list_pedidos(50) if p["servicio"] == "barba")
        assert memory.entregar_pedido(barba["pedido_id"])
        barba = next(p for p in memory.list_pedidos(50) if p["servicio"] == "barba")
        assert barba["estado"] == "entregado" and barba["delivered_at"], barba
        memory.save_pending_approval({"event_id": "evt_d", "customer_id": gil, "intent": "reembolso", "why": "x",
                                      "requested_action": "Quiero un reembolso", "notify_text": "x"})
        panel = h._panel()
        home = panel.split("<main>")[1].split("<nav")[0]
        assert "sin cobro" not in home and home.count("class='casilla'") == 4, home
        cifra = lambda vid: re.search(rf"data-abre='{vid}'>.*?<b>(.*?)</b>", home).group(1)
        # Se cuentan las citas de hoy, no un número fijo.
        hoy = demo._ahora_cali().date()
        n_citas = sum(1 for c in memory.list_confirmed_reservas(500) if (w := demo.cuando_fila(c)) and w[0] == hoy)
        assert n_citas >= 1 and cifra("casilla-reserva") == f"{n_citas}/2", "citas de hoy / 2 pedidos sin rechazados"
        assert cifra("casilla-gestionado") == "2 · $35.000"
        assert cifra("casilla-proceso") == "3 · $33.000", "1 pendiente + 2 abiertos (corte y cera)"
        assert cifra("casilla-cerrado") == "1 · $10.000"
        cerrado = panel.split("id='casilla-cerrado'")[1].split("</dialog>")[0]
        assert demo._a("No es un pago verificado.") in cerrado
        # Muro I: misma tabla de gestión: cliente, canal, tipo, cantidad, código, nombre, precio, estado.
        assert re.search(r"<td>Gil</td><td>WhatsApp</td><td>servicio</td><td>1</td><td>—</td><td>barba</td>"
                         r"<td>\$10\.000</td><td>entregado \d\d/\d\d \d\d:\d\d</td>", cerrado), cerrado
        assert "uñas" not in cerrado, "sin delivered_at no cuenta como cerrado hoy"
        proceso = panel.split("id='casilla-proceso'")[1].split("</dialog>")[0]
        assert "<td>reembolso</td><td>—</td><td>—</td><td>Pide reembolso</td><td>—</td><td>espera tu sí</td>" in proceso
        assert "<td>cera</td><td>$8.000</td><td>pagado</td>" in proceso and "tinte" not in proceso
        for vid in ("casilla-gestionado", "casilla-proceso", "casilla-cerrado"):
            tabla = panel.split(f"id='{vid}'")[1].split("</dialog>")[0]
            assert "".join(f"<th>{demo._a(c)}</th>" for c in demo._COLUMNAS_GESTION) in tabla, vid

        # Muro I: cita de hoy con servicio conocido suma en Gestionado una vez, con su precio. Sin servicio, no.
        hoy_ana = f"{demo._ahora_cali().date().isoformat()} 16:00"
        with memory._conn() as conn:
            conn.execute(
                "INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at)"
                " VALUES (?, 'evt_ana_corte', 'whatsapp', 'reserva', 'hoy a las 4 para corte', 'ok', datetime('now'), ?)",
                (ana, hoy_ana))
        panel = h._panel()
        home = panel.split("<main>")[1].split("<nav")[0]
        precio_corte = demo.kb.buscar_servicio("corte")["precio"]
        assert cifra("casilla-gestionado") == f"3 · {demo.kb.precio_txt(35000 + precio_corte)}", cifra("casilla-gestionado")
        gest = panel.split("id='casilla-gestionado'")[1].split("</dialog>")[0]
        assert gest.count("cita confirmada 16:00") == 1 and "cita confirmada 15:00" not in gest, "cita sin servicio no suma"
        # Reembolso aprobado hoy: fila visible; sin monto guardado no resta valor.
        assert "reembolso aprobado · sin monto" in gest and "<td>reembolso</td><td>—</td><td>—</td><td>reembolso</td><td>—</td>" in gest
        # Rechazado no suma.
        assert "tinte" not in gest

        # Muro I: Reserva/Pedido abre por canal (canal, cantidad, valor); cada canal abre sus filas.
        reserva = panel.split("id='casilla-reserva'")[1].split("</dialog>")[0]
        assert "".join(f"<th>{demo._a(c)}</th>" for c in ("Canal", "Cantidad", "Valor")) in reserva
        fila_wa = re.search(r"data-abre='(casilla-reserva-\d+)'>WhatsApp</button></td><td>(\d+)</td><td>(.*?)</td>", reserva)
        assert fila_wa and fila_wa.group(2) == "4", reserva  # 2 citas de hoy + 2 pedidos de hoy (corte, barba)
        assert fila_wa.group(3) == demo.kb.precio_txt(35000 + precio_corte), fila_wa.group(3)
        sub = panel.split(f"id='{fila_wa.group(1)}'")[1].split("</dialog>")[0]
        assert "cita confirmada 15:00" in sub and "cita confirmada 16:00" in sub and "<td>Ana</td>" not in sub
        assert "<td>sin nombre</td>" in sub, "Ana borró sus datos: sin nombre"

        # Muro I: producto del inventario lleva código y nombre; servicio, código "—".
        prods = demo.kb.productos
        demo.kb.productos = lambda: [{"codigo": "CAF01", "nombre": "cafe molido", "precio": 12000, "stock": 3}]
        try:
            f = demo._fila_pedido({"customer_id": "x", "servicio": "CAF01 cafe", "precio": 12000, "estado": "anotado"})
            assert (f["tipo"], f["codigo"], f["nombre"], f["cantidad"]) == ("producto", "CAF01", "cafe molido", "1"), f
        finally:
            demo.kb.productos = prods
        assert "Instagram" not in panel and "<td>Web</td>" not in panel, "sin canal inventado"
        assert demo._a("Envíos de producto, repartidor y contra entrega: aún no") in home
        # Agenda no: sin cupos; los pedidos siguen.
        assert demo._a("Cupos de la semana") in panel
        demo.kb.set_agenda(False)
        dia = h._panel().split('id="dia"')[1].split('id="conversaciones"')[0]
        assert demo._a("Cupos de la semana") not in dia and "<h2>Pedidos</h2>" in dia
    finally:
        demo.kb._kb_path = kb_original

    # Muro F: Registro con Eventos (Inicio, Gestión, Fin) arriba de Avisos. Sin repetir el hilo, sin internos.
    registro = h._panel().split('id="registro"')[1]
    assert registro.index("<h2>Eventos</h2>") < registro.index(f"<h2>{demo._a('Avisos')}</h2>")
    eventos = registro.split("<h2>Eventos</h2>")[1].split("</table>")[0]
    assert "<td>Inicio</td><td>Gil</td><td>¿Tienen cupo mañana?</td>" in eventos, eventos
    assert "Mi celular es" not in eventos and "Sí, a las 10:00." not in eventos, "solo el primer mensaje, no el hilo"
    assert "<td>Inicio</td><td>…5566</td><td>Datos borrados</td>" in eventos, "datos borrados no se leen"
    assert "<td>Gestión</td><td>Gil</td><td>Pide reembolso. Espera tu sí.</td>" in eventos
    assert "<td>Fin</td><td>Gil</td><td>Pidió reembolso: aprobado.</td>" in eventos
    assert "<td>Fin</td><td>Gil</td><td>Pedido entregado: barba $10.000.</td>" in eventos
    # Muro H: Fin de un pedido usa delivered_at; sin ella, "—".
    assert re.search(r"<td>\d\d/\d\d \d\d:\d\d</td><td>Fin</td><td>Gil</td><td>Pedido entregado: barba", eventos), eventos
    assert "<td>—</td><td>Fin</td><td>Gil</td><td>Pedido entregado: uñas $5.000.</td>" in eventos, eventos

    # Muro H: el aviso de una decisión guarda el event_id. Sin vínculo: "sin vínculo"; nunca el aviso de otro caso.
    for eid in ("evt_h1", "evt_h2"):
        memory.save_pending_approval({"event_id": eid, "customer_id": gil, "intent": "descuento", "why": "x",
                                      "requested_action": "Quiero descuento", "notify_text": "x"})
    h._decidir("evt_h1", "approved")
    memory.resolve_pending("evt_h2", "rejected")  # decidido sin aviso (como el panel viejo)
    vinculo = memory.aviso_del_caso("evt_h1")
    assert vinculo and vinculo["tipo"] == "n3_cliente" and vinculo["estado"] in {"fallo", "fuera_24h"}, vinculo
    assert memory.aviso_del_caso("evt_h2") is None
    decididas = h._panel().split(f"<h2>{demo._a('Decididas')}</h2>")[1]
    fila_h1 = decididas.split("<td>evt_h1</td>")[1].split("</tr>")[0]
    fila_h2 = decididas.split("<td>evt_h2</td>")[1].split("</tr>")[0]
    assert re.search(r"· (fallo|fuera de 24 h)</td>$", fila_h1), fila_h1
    assert "· sin vínculo</td>" in fila_h2 and "fallo" not in fila_h2 and "fuera de 24 h" not in fila_h2, fila_h2
    assert "reporte interno" not in eventos and "despacho" not in registro.lower()
    assert demo._corto("x" * 80).endswith("…") and len(demo._corto("x" * 80)) == 60

    # Muro K: puerta Quiénes somos (texto fijo, sello Λ) y clip de primera visita (solo enlace, no archivo).
    panel = h._panel()
    quienes = panel.split("id='quienes-somos'")[1].split("</dialog>")[0]
    for frase in ("no cobra", "Ley 1581", "no se venden", "borrar mis datos", "Guarda solo lo que el cliente dio"):
        assert frase in quienes, frase
    assert "<div class='sello' aria-hidden='true'>Λ</div>" in quienes and "data-abre=\"quienes-somos\"" in panel
    intro = panel.split("id='intro'")[1].split("</div>")[0]
    assert " hidden>" in panel.split("id='intro'")[1][:10] and "data-src='https://www.youtube-nocookie.com/embed/s7zg6v035PQ" in intro
    assert " src='" not in intro, "el video solo se pide al mostrarse"
    assert "localStorage" in panel and "intro.hidden) location.reload()" in panel
    assert not list(Path(ROOT).rglob("*.mp4")), "el clip no se guarda en el repo"
    # Las tres puertas: letra de la marca, palabras enteras.
    css = panel.split("<style>")[1].split("</style>")[0]
    assert "text-transform:uppercase;white-space:nowrap" in css.split(".puertas button{")[1].split("}")[0]

    # Muro K: sin nombre, AXEL pregunta hasta tres veces; a la tercera, "omitido".
    from axel.orchestrator import PREGUNTA_NOMBRE, nombre_omitido
    nuevo = {"channel": "whatsapp", "channel_user_id": "573005550000", "phone": "3005550000"}
    preguntas = [PREGUNTA_NOMBRE in (h._run({**nuevo, "text": t})["reply_text"] or "") for t in ("hola", "hola", "hola", "hola")]
    assert preguntas == [True, True, True, False], preguntas
    sin_nombre = memory.find_by_identity("whatsapp", "573005550000")["customer_id"]
    assert nombre_omitido(memory, sin_nombre)
    clientes = h._panel().split("<h2>Clientes</h2>")[1].split("</table>")[0]
    assert "<td>omitido</td>" in clientes and memory.get_customer(sin_nombre)["name"] is None, "omitido solo se muestra"

    print("OK — panel: 8 envíos sin texto ni celular entero; citas con cita_at; inventario 15; hilo solo lectura")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
