#!/usr/bin/env python3
"""Pack de aceptación piloto 2026, con tokens WA vacíos y KB temporal:
precios desde servicios, sin agenda no ofrece cita, pedido en fila,
pedidos solo para el dueño, reembolso queda N3. No toca el kb.json real."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Sin tokens: nada sale a WhatsApp. Dueño y cliente son números de prueba.
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WA_OWNER_PHONE"] = "573000000001"
DUENO, CLIENTE, AJENO = "573000000001", "573000000002", "573000000003"

from axel import knowledge_base as kb
from axel import notify
from axel.envelope import Envelope
from axel.memory import Memory
from axel.orchestrator import process

KB_PILOTO = {
    "negocio": "Cafe Piloto",
    "rubro": "cafeteria",
    "agenda": False,
    "horario": "7:00 a 19:00",
    "servicios": [{"nombre": "cafe", "precio": 4000}, {"nombre": "empanada", "precio": 3000}],
    "politicas": {},
    "faqs": [],
}


def main() -> int:
    real = ROOT / "kb.json"
    antes = real.read_bytes() if real.exists() else None

    tmp = Path(tempfile.gettempdir())
    kb_tmp = tmp / "axel_kb_piloto_2026.json"
    kb_tmp.write_text(json.dumps(KB_PILOTO, ensure_ascii=False), encoding="utf-8")
    db = tmp / "axel_piloto_2026.db"
    if db.exists():
        db.unlink()
    memory = Memory(str(db))

    def dice(texto: str, quien: str = CLIENTE):
        out = process(Envelope(text=texto, channel="whatsapp", channel_user_id=quien), memory)
        print(quien[-1], repr(texto), "->", out.reply_text)
        return out

    original = kb._kb_path
    kb._kb_path = lambda: kb_tmp
    try:
        # Precios salen de servicios[].
        precios = dice("precios").reply_text or ""
        assert "Lista: cafe $4.000, empanada $3.000" in precios, precios

        # Sin agenda no ofrece cita.
        for texto in ("hola", "cuanto vale el cafe", "quiero una cita"):
            r = (dice(texto).reply_text or "").lower()
            assert "reserv" not in r and "agendar" not in r and "cupo" not in r, r
        assert kb.agenda() is False

        # "me lo llevo" guarda fila de pedido.
        anotado = dice("me lo llevo el cafe")
        assert (anotado.reply_text or "").startswith("Pedido anotado: cafe $4.000")
        # Aviso al dueño: quién, qué, $. No cobra.
        assert anotado.payload.get("aviso_pedido") == "Pedido nuevo: sin nombre · cafe $4.000. AXEL no cobra.", anotado.payload
        filas = [(p["servicio"], p["precio"]) for p in memory.list_pedidos()]
        assert filas == [("cafe", 4000)], filas

        # El dueño ve pedidos; un ajeno no.
        dueno = dice("pedidos", DUENO).reply_text or ""
        assert dueno.startswith("Pedidos:") and "cafe $4.000" in dueno, dueno
        ajeno = dice("pedidos", AJENO).reply_text or ""
        assert "Pedidos:" not in ajeno and "$4.000" not in ajeno, ajeno

        # Estado del pedido: anotado -> entregado solo por el dueño. Entregado no es cobrado.
        assert dueno.endswith("cafe $4.000 · anotado"), dueno
        dice("pedido listo", CLIENTE)
        assert [p["estado"] for p in memory.list_pedidos()] == ["anotado"], "el cliente no cambia estado"
        assert dice("pedido listo", DUENO).reply_text == "Entregado: cafe $4.000 · sin nombre. AXEL no cobra."
        assert (dice("pedidos", DUENO).reply_text or "").endswith("cafe $4.000 · entregado")
        assert dice("pedido listo", DUENO).reply_text == "No hay pedidos anotados."

        # Reembolso queda en nivel 3, pendiente del dueño, sin ejecutar.
        reembolso = dice("quiero un reembolso de mi compra")
        assert reembolso.supervision_level == 3
        assert reembolso.result == "pending" and reembolso.approval_status == "pending_owner"
        assert reembolso.payload.get("executed") is None
        assert any(p["event_id"] == reembolso.event_id for p in memory.list_pending())

        # KB del piloto (copia del kb.json real, con agenda, sin "mesa"): "turno" abre la reserva y pide día y hora.
        kb_tmp.write_bytes(real.read_bytes())
        assert kb.agenda() is True and "turno" in kb.agenda_palabras() and "mesa" not in kb.agenda_palabras()
        for quien, texto in (("573000000004", "reservar turno"), ("573000000005", "quiero turno")):
            r = dice(texto, quien).reply_text or ""
            assert "Dime día y hora" in r, r
        corte = dice("cuanto vale el corte", "573000000006").reply_text or ""
        assert corte.startswith("Corte: $") and "¿Te anoto un turno?" in corte, corte

        # Cancelar / reprogramar con la palabra de agenda. "pedido" y "mesa" no están en la lista: no tocan la cita.
        eva = "573000000007"
        dice("quiero turno", eva)
        cita = dice("jueves a las 11", eva)
        assert (cita.reply_text or "").startswith("Quedó tu cita"), cita.reply_text
        cid = cita.customer_id
        for texto in ("cancelar el pedido", "cancelar la mesa"):
            r = dice(texto, eva).reply_text or ""
            assert "Cancelé" not in r and memory.last_reserva(cid), r
        r = dice("reprogramar turno", eva).reply_text or ""
        assert "No tienes cita" not in r and "Cancelé" not in r, r
        assert (dice("cancelar el turno", eva).reply_text or "").startswith("Cancelé la cita")
        assert memory.last_reserva(cid) is None
        dice("quiero una reserva", eva)
        dice("jueves a las 11", eva)
        assert (dice("cancelar la reserva", eva).reply_text or "").startswith("Cancelé la cita")

        # Cliente ve solo sus reservas vivas; el dueño ve todas con "citas".
        fer = "573000000008"
        assert dice("mi reserva", eva).reply_text == "No tienes reserva."
        dice("quiero turno", fer)
        dice("viernes a las 9", fer)
        dice("quiero turno", eva)
        dice("sabado a las 15", eva)
        suya = dice("mis citas", eva).reply_text or ""
        assert suya.startswith("Tus reservas:\n- sábado") and "viernes" not in suya, suya
        de_fer = dice("mi turno", fer).reply_text or ""
        assert de_fer.startswith("Tus reservas:\n- viernes") and "sábado" not in de_fer, de_fer
        todas = dice("citas", DUENO).reply_text or ""
        assert "viernes" in todas and "sábado" in todas, todas

        # Saludo con reserva viva: la recuerda con la palabra del piloto. Sin reserva, saludo de siempre. Dueño no.
        hola_fer = dice("hola", fer).reply_text or ""
        assert hola_fer.startswith("Hola, soy AXEL. Tu turno es viernes 9:00.\n"), hola_fer
        # Segunda línea: negocio + abierto o cerrado.
        linea2 = hola_fer.split("\n")[1]
        assert linea2.startswith(kb.load_kb()["negocio"]) and ("abiertos" in linea2 or "No abrimos" in linea2 or "cerrados" in linea2), linea2
        sin = dice("buenas", "573000000009").reply_text or ""
        assert "Tu turno" not in sin and "soy AXEL" in sin, sin
        assert "Tu turno" not in (dice("hola", DUENO).reply_text or "")

        # Sin cita viva pero con pedido anotado: el saludo lo recuerda. Con cita, gana la cita.
        gil = "573000000010"
        dice("me lo llevo el corte", gil)
        hola_gil = dice("hola", gil).reply_text or ""
        assert hola_gil.startswith("Hola, soy AXEL. Tienes un pedido anotado: corte $"), hola_gil
        assert hola_gil.split("\n")[1].startswith(kb.load_kb()["negocio"]), hola_gil
        dice("me lo llevo el corte", fer)
        hola_fer = dice("hola", fer).reply_text or ""
        assert "Tu turno es viernes" in hola_fer and "pedido" not in hola_fer, hola_fer
        assert "pedido anotado" not in (dice("hola", DUENO).reply_text or "")

        # "mi pedido" / "mis pedidos": el cliente ve solo los suyos. El dueño sigue viendo todos.
        de_gil = dice("mis pedidos", gil).reply_text or ""
        assert de_gil.startswith("Tus pedidos:\n- corte $") and "· anotado · " in de_gil, de_gil
        assert de_gil.count("\n- ") == 1, de_gil
        assert (dice("mi pedido", fer).reply_text or "").count("\n- ") == 1
        assert (dice("mi pedido", "573000000009").reply_text or "").startswith("No tienes pedidos.")
        todos = dice("pedidos", DUENO).reply_text or ""
        assert todos.startswith("Pedidos:") and todos.count("\n- ") >= 3, todos

        # "pedido listo": con varios anotados hoy lista y pide nombre o cel. Nunca marca el de otra persona.
        def estados():
            return sorted((p["customer_id"][-4:], p["estado"]) for p in memory.list_pedidos(50) if p["servicio"] == "corte")
        antes_listo = estados()
        assert [e for _, e in antes_listo] == ["anotado", "anotado"], antes_listo
        dice("pedido listo", gil)
        assert estados() == antes_listo, "el cliente no usa pedido listo"
        varios = dice("pedido listo", DUENO).reply_text or ""
        assert varios.startswith("Pedidos anotados:\n") and varios.count("\n- ") == 2 and "pedido listo NOMBRE" in varios, varios
        assert estados() == antes_listo, varios
        dice("me llamo Gil", gil)
        dice("me llamo Gil", fer)
        dice("mi celular 3001112233", fer)
        mismo = dice("pedido listo gil", DUENO).reply_text or ""
        assert mismo.startswith("Hay varios con ese nombre") and "cel …2233" in mismo, mismo
        assert estados() == antes_listo, mismo
        # Al entregar, aviso a ESE cliente por su celular. Sin celular no se envía (solo log).
        enviados = []
        envio_real = notify.send_text
        notify.send_text = lambda to, text: enviados.append((to, text)) or {"fake": True}
        r = dice("pedido listo 2233", DUENO).reply_text or ""
        assert r.startswith("Entregado: corte $") and r.endswith(" · Gil. AXEL no cobra."), r
        assert enviados == [("3001112233", "Tu pedido de corte quedó listo. El dueño confirma el pago. AXEL no cobra.")], enviados
        fer_id = memory.find_by_identity("whatsapp", fer)["customer_id"]
        assert dict((p["customer_id"], p["estado"]) for p in memory.list_pedidos(50) if p["servicio"] == "corte") == {
            fer_id: "entregado", memory.find_by_identity("whatsapp", gil)["customer_id"]: "anotado"
        }
        r = dice("pedido listo", DUENO).reply_text or ""
        assert r.startswith("Entregado: corte $") and r.endswith(" · Gil. AXEL no cobra."), r
        assert len(enviados) == 1, "gil sin celular: no se inventa envío"
        notify.send_text = envio_real
        assert dice("pedido listo", DUENO).reply_text == "No hay pedidos anotados."

        # Pack habitación: clientes nuevos, de punta a punta.
        negocio = kb.load_kb()["negocio"]
        hab = "573000000011"
        dice("quiero turno", hab)
        assert (dice("sabado a las 11", hab).reply_text or "").startswith("Quedó tu cita")
        con = dice("hola", hab).reply_text or ""
        assert "Tu turno es sábado 11:00." in con and negocio in con, con
        sin_res = dice("hola", "573000000012").reply_text or ""
        assert "turno" not in sin_res.lower() and "cita" not in sin_res.lower(), sin_res

        p1, p2 = "573000000013", "573000000014"
        dice("me lo llevo el corte", p1)
        dice("me lo llevo el corte", p2)
        ids = {memory.find_by_identity("whatsapp", q)["customer_id"] for q in (p1, p2)}

        def de_hab():
            return [p["estado"] for p in memory.list_pedidos(50) if p["customer_id"] in ids]

        assert de_hab() == ["anotado", "anotado"]
        assert (dice("pedido listo", DUENO).reply_text or "").startswith("Pedidos anotados:\n")
        assert de_hab() == ["anotado", "anotado"], "pedido listo solo no cierra los dos"

        dice("mi celular 3004445566", p1)
        enviados = []
        notify.send_text = lambda to, text: enviados.append((to, text)) or {"fake": True}
        try:
            assert (dice("pedido listo 5566", DUENO).reply_text or "").startswith("Entregado: corte $")
        finally:
            notify.send_text = envio_real
        assert sorted(de_hab()) == ["anotado", "entregado"], de_hab()
        assert enviados == [("3004445566", "Tu pedido de corte quedó listo. El dueño confirma el pago. AXEL no cobra.")], enviados

        # Tono de la KB: cercano (tú) en el piloto; formal (usted) cambia saludo y "no tengo esa información".
        assert kb.tono() == "cercano"
        assert "Puedo ayudarte con" in (dice("venden naves espaciales", "573000000015").reply_text or "")
        kb_tmp.write_text(json.dumps({**kb.load_kb(), "tono": "formal"}, ensure_ascii=False), encoding="utf-8")
        assert kb.tono() == "formal"
        no_hay = dice("venden naves espaciales", "573000000016").reply_text or ""
        assert "Puedo ayudarle con" in no_hay and "ayudarte" not in no_hay, no_hay
        assert no_hay.endswith("¿Cómo quiere que le llame?") and "te llame" not in no_hay, no_hay
        # La pregunta formal también toma el nombre.
        dice("venden naves espaciales", "573000000017")
        assert dice("Leo", "573000000017").reply_text == "Quedó su nombre: Leo."
        usted = dice("hola", "573000000016").reply_text or ""
        assert ("le puedo ayudar" in usted or "agendarle" in usted) and "te ayudo" not in usted and "agendarte" not in usted, usted
        assert "Su turno es sábado 11:00." in (dice("hola", hab).reply_text or "")
        kb_tmp.write_bytes(real.read_bytes())

        # Stock: 0 no se vende ni se ofrece cita; 2 o sin "stock" sí. No se resta al vender.
        con_stock = kb.load_kb()
        con_stock["servicios"] = [
            {"nombre": "corte", "precio": 25000, "stock": 2},
            {"nombre": "barba", "precio": 15000, "stock": 0},
            {"nombre": "corte + barba", "precio": 35000},
        ]
        kb_tmp.write_text(json.dumps(con_stock, ensure_ascii=False), encoding="utf-8")
        rita = "573000000018"
        dice("me llamo Rita", rita)
        assert dice("cuanto vale la barba", rita).reply_text == "No hay barba ahora."
        sin_barba = dice("me lo llevo la barba", rita)
        assert sin_barba.reply_text == "No hay barba ahora." and "aviso_pedido" not in sin_barba.payload
        assert (dice("me lo llevo el corte", rita).reply_text or "").startswith("Pedido anotado: corte $25.000")
        assert (dice("me lo llevo el corte + barba", rita).reply_text or "").startswith("Pedido anotado: corte + barba $35.000")
        rita_id = memory.find_by_identity("whatsapp", rita)["customer_id"]
        assert sorted(p["servicio"] for p in memory.list_pedidos(100) if p["customer_id"] == rita_id) == ["corte", "corte + barba"]
        lista = dice("precios", rita).reply_text or ""
        assert "barba agotado" in lista and "corte $25.000" in lista and "corte + barba $35.000" in lista, lista
        assert [s.get("stock") for s in kb.servicios()] == [2, 0, None], "no se resta stock al vender"
        kb_tmp.write_bytes(real.read_bytes())

        # El dueño edita stock; el cliente no. "catalogo" muestra stock solo si el campo existe.
        assert dice("stock corte 0", rita).reply_text == "Eso solo lo cambia el dueño."
        assert "stock" not in kb.buscar_servicio("corte")
        assert dice("stock corte 0", DUENO).reply_text == "Listo, corte: stock 0. Queda agotado: no se vende."
        assert dice("me lo llevo el corte", rita).reply_text == "No hay corte ahora."
        cat = dice("catalogo", DUENO).reply_text or ""
        assert "- corte $25.000 · stock 0 (agotado)" in cat and "- barba $15.000\n" in cat, cat
        assert dice("stock corte 5", DUENO).reply_text == "Listo, corte: stock 5."
        assert "- corte $25.000 · stock 5\n" in (dice("catalogo", DUENO).reply_text or "")
        assert (dice("me lo llevo el corte", rita).reply_text or "").startswith("Pedido anotado: corte $25.000")
        assert dice("stock pizza 3", DUENO).reply_text == "No tengo el servicio pizza."
        kb_tmp.write_bytes(real.read_bytes())

        # El dueño cambia el tono; el cliente no. "ayuda" y "catalogo" lo muestran.
        assert dice("tono formal", rita).reply_text == "Eso solo lo cambia el dueño."
        assert kb.tono() == "cercano"
        assert dice("tono formal", DUENO).reply_text == "Listo, tono: formal (usted)."
        assert kb.load_kb()["tono"] == "formal"
        assert "Tono: formal" in (dice("catalogo", DUENO).reply_text or "")
        assert "tono formal/cercano" in (dice("ayuda", DUENO).reply_text or "")
        assert dice("tono cercano", DUENO).reply_text == "Listo, tono: cercano (tú)."
        assert kb.load_kb()["tono"] == "cercano" and "Tono: cercano" in (dice("catalogo", DUENO).reply_text or "")
        kb_tmp.write_bytes(real.read_bytes())

        # wamid: Meta reintenta el mismo mensaje; solo cuenta la primera vez.
        assert memory.marcar_wamid("wamid.PILOTO1") is True
        assert memory.marcar_wamid("wamid.PILOTO1") is False
        assert memory.marcar_wamid("wamid.PILOTO2") is True

        # envios: cada aviso deja fila. Sin token = fallo; sin celular; al dueño como cliente se omite.
        tipos = {(e["tipo"], e["estado"]) for e in memory.list_envios(500)}
        for fila in (("pedido_nuevo", "fallo"), ("pedido_listo", "enviado"), ("pedido_listo", "sin_celular"), ("n3_dueno", "fallo")):
            assert fila in tipos, (fila, tipos)
        assert notify.aviso_cliente(memory, "pedido_listo", DUENO, "x") == "omitido_dueno"
        # Meta falla: un solo intento, fila fallo.
        intentos = []
        notify.send_text = lambda to, text: intentos.append(to) or {"status": 500, "body": {}}
        try:
            assert notify.enviar(memory, "aviso_24h", CLIENTE, "Recordatorio: tu cita es hoy a las 11:00.") == "fallo"
            dice("aprobar", DUENO)
        finally:
            notify.send_text = envio_real
        assert intentos == [CLIENTE], intentos
        ultimos = memory.list_envios(3)
        assert [e["tipo"] for e in ultimos][:2] == ["n3_cliente", "aviso_24h"], ultimos
        assert ultimos[1]["estado"] == "fallo"
        env_dueno = dice("envios", DUENO).reply_text or ""
        assert env_dueno.startswith("Envíos:\n- ") and env_dueno.count("\n- ") == 10, env_dueno
        assert " · dueño · " in env_dueno and " · aviso_24h · " in env_dueno and " · fallo" in env_dueno, env_dueno
        assert "Envíos:" not in (dice("envios", CLIENTE).reply_text or ""), "el cliente no ve envios"

        # Nombre: un comando o acción de agenda no se guarda como nombre; se responde la intención.
        for n, texto in enumerate(("cancelar la mesa", "precios", "horario", "ficha", "ayuda")):
            nuevo = f"57300000010{n}"
            assert "¿Cómo quieres que te llame?" in (dice("hola", nuevo).reply_text or "")
            r = dice(texto, nuevo)
            assert not r.name and "Quedó tu nombre" not in (r.reply_text or ""), r.reply_text
            assert not memory.find_by_identity("whatsapp", nuevo).get("name"), texto
        frases = ("mi ficha", "Mis citas", "mi cita", "mi reserva", "mi turno", "mi pedido")
        for n, texto in enumerate(frases):
            nuevo = f"57300000020{n}"
            dice("hola", nuevo)
            r = dice(texto, nuevo)
            assert not r.name and not memory.find_by_identity("whatsapp", nuevo).get("name"), (texto, r.reply_text)
        for n, texto in enumerate(("Mi Leidy", "Mi Leidy Perez")):
            nuevo = f"57300000030{n}"
            dice("hola", nuevo)
            assert dice(texto, nuevo).reply_text == f"Quedó tu nombre: {texto}."

        # limpiar: borra fantasmas de verdad, no clientes con pedido, cita viva o N3 pendiente.
        assert memory.find_by_identity("whatsapp", AJENO), "el ajeno existe antes de limpiar"
        assert (dice("limpiar", DUENO).reply_text or "").startswith("Eliminé")
        assert not memory.find_by_identity("whatsapp", AJENO), "fantasma sin nada se borra"
        assert memory.find_by_identity("whatsapp", CLIENTE), "con pedido y N3 no se borra"
        assert memory.find_by_identity("whatsapp", fer), "con cita viva no se borra"
        assert (dice("mi turno", fer).reply_text or "").startswith("Tus reservas:\n- viernes")
        assert all(memory.get_customer(p["customer_id"]) for p in memory.list_pedidos()), "ningún pedido queda sin cliente"
    finally:
        kb._kb_path = original
        kb_tmp.unlink(missing_ok=True)

    assert (real.read_bytes() if real.exists() else None) == antes, "se tocó el kb.json real"
    print("OK — pack piloto 2026: precios, sin cita, pedido en fila, pedidos solo dueño, reembolso N3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
