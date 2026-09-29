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
        r = dice("pedido listo 2233", DUENO).reply_text or ""
        assert r.startswith("Entregado: corte $") and r.endswith(" · Gil. AXEL no cobra."), r
        fer_id = memory.find_by_identity("whatsapp", fer)["customer_id"]
        assert dict((p["customer_id"], p["estado"]) for p in memory.list_pedidos(50) if p["servicio"] == "corte") == {
            fer_id: "entregado", memory.find_by_identity("whatsapp", gil)["customer_id"]: "anotado"
        }
        r = dice("pedido listo", DUENO).reply_text or ""
        assert r.startswith("Entregado: corte $") and r.endswith(" · Gil. AXEL no cobra."), r
        assert dice("pedido listo", DUENO).reply_text == "No hay pedidos anotados."

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
