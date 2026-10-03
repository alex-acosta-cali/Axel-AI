from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL DEFAULT 'biz_default',
    name TEXT,
    phone TEXT,
    email TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS identities (
    identity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    channel_user_id TEXT NOT NULL,
    UNIQUE(channel, channel_user_id)
);
CREATE TABLE IF NOT EXISTS conversation_summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT,
    event_id TEXT,
    channel TEXT,
    intent TEXT,
    summary TEXT,
    result TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT,
    event_id TEXT,
    channel TEXT,
    direction TEXT,
    text TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS session_state (
    customer_id TEXT PRIMARY KEY,
    open_task TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    received_at TEXT,
    finished_at TEXT,
    channel TEXT,
    customer_id TEXT,
    agent TEXT,
    model TEXT,
    supervision_level INTEGER,
    approval_status TEXT,
    input_summary TEXT,
    output_summary TEXT,
    result TEXT,
    error TEXT,
    why TEXT,
    data_used TEXT
);
CREATE TABLE IF NOT EXISTS pending_approvals (
    event_id TEXT PRIMARY KEY,
    customer_id TEXT,
    intent TEXT,
    why TEXT,
    requested_action TEXT,
    notify_text TEXT,
    status TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS customer_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS pedidos (
    pedido_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    servicio TEXT NOT NULL,
    precio INTEGER NOT NULL,
    created_at TEXT,
    nota_id INTEGER UNIQUE
);
CREATE TABLE IF NOT EXISTS avisos_cita (
    event_id TEXT NOT NULL,
    plazo TEXT NOT NULL,
    created_at TEXT,
    PRIMARY KEY (event_id, plazo)
);
CREATE TABLE IF NOT EXISTS avisos_stock (
    codigo TEXT NOT NULL,
    business_id TEXT NOT NULL DEFAULT 'biz_default',
    created_at TEXT,
    PRIMARY KEY (codigo, business_id)
);
CREATE TABLE IF NOT EXISTS wamid_visto (
    wamid TEXT PRIMARY KEY,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS envios (
    envio_id INTEGER PRIMARY KEY AUTOINCREMENT,
    destino TEXT,
    tipo TEXT NOT NULL,
    texto TEXT,
    estado TEXT NOT NULL,
    created_at TEXT
);
"""
# Muro 38: estados del pedido, en orden. 'rechazado' va aparte. Sin banco.
ESTADOS_PEDIDO = ("anotado", "por verificar", "pagado", "en camino", "entregado")
# Nota vieja "Pedido piloto corte $25.000 (sin cobro)" -> fila en pedidos.
_NOTA_PEDIDO = re.compile(r"^Pedido piloto (.+) \$([\d.]+) \(sin cobro\)$")


def _new_customer_id() -> str:
    return f"cus_{uuid4().hex[:10]}"


class Memory:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            for tabla, col, typ in (
                ("audit_events", "why", "TEXT"),
                ("audit_events", "data_used", "TEXT"),
                ("pedidos", "estado", "TEXT NOT NULL DEFAULT 'anotado'"),
                # Cita confirmada: 'AAAA-MM-DD HH:MM' hora Cali. Las viejas quedan NULL y se leen del texto.
                ("conversation_summaries", "cita_at", "TEXT"),
                # 1 = el dueño aprobó "borrar mis datos". "mi ficha" dice "datos borrados".
                ("customers", "datos_borrados", "INTEGER NOT NULL DEFAULT 0"),
                # Muro 34: citas y pedidos llevan negocio. Las filas viejas se leen como biz_default.
                ("conversation_summaries", "business_id", "TEXT NOT NULL DEFAULT 'biz_default'"),
                ("pedidos", "business_id", "TEXT NOT NULL DEFAULT 'biz_default'"),
                # Hora en que el dueño decidió (UTC). Las viejas quedan NULL.
                ("pending_approvals", "decided_at", "TEXT"),
            ):
                try:
                    conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {typ}")
                except sqlite3.OperationalError:
                    pass
            # Pedidos viejos guardados como nota: se copian una vez; la nota no se toca.
            for n in conn.execute(
                "SELECT note_id, customer_id, note, created_at FROM customer_notes WHERE note LIKE 'Pedido piloto %'"
            ).fetchall():
                m = _NOTA_PEDIDO.match(n["note"])
                if m:
                    conn.execute(
                        "INSERT OR IGNORE INTO pedidos(customer_id, servicio, precio, created_at, nota_id) VALUES (?,?,?,?,?)",
                        (n["customer_id"], m.group(1), int(m.group(2).replace(".", "")), n["created_at"], n["note_id"]),
                    )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def identify_customer(
        self,
        *,
        business_id: str,
        channel: str,
        channel_user_id: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict[str, Any]:
        phone = (phone or "").strip() or None
        email = (email or "").strip().lower() or None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT customer_id FROM identities WHERE channel = ? AND channel_user_id = ?",
                (channel, channel_user_id),
            ).fetchone()
            if row:
                customer_id = row["customer_id"]
            else:
                customer_id = None
                if phone:
                    found = conn.execute(
                        "SELECT customer_id FROM customers WHERE business_id = ? AND phone = ?",
                        (business_id, phone),
                    ).fetchone()
                    if found:
                        customer_id = found["customer_id"]
                if not customer_id and email:
                    found = conn.execute(
                        "SELECT customer_id FROM customers WHERE business_id = ? AND email = ?",
                        (business_id, email),
                    ).fetchone()
                    if found:
                        customer_id = found["customer_id"]
                if not customer_id:
                    customer_id = _new_customer_id()
                    conn.execute(
                        """
                        INSERT INTO customers(customer_id, business_id, name, phone, email, created_at, updated_at)
                        VALUES (?,?,?,?,?,datetime('now'),datetime('now'))
                        """,
                        (customer_id, business_id, name, phone, email),
                    )
                conn.execute(
                    "INSERT OR IGNORE INTO identities(customer_id, channel, channel_user_id) VALUES (?,?,?)",
                    (customer_id, channel, channel_user_id),
                )
            if phone or email or name:
                conn.execute(
                    """
                    UPDATE customers
                    SET phone = COALESCE(?, phone),
                        email = COALESCE(?, email),
                        name = COALESCE(?, name),
                        updated_at = datetime('now')
                    WHERE customer_id = ?
                    """,
                    (phone, email, name, customer_id),
                )
            cust = conn.execute(
                "SELECT * FROM customers WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
            identities = conn.execute(
                "SELECT channel, channel_user_id FROM identities WHERE customer_id = ?",
                (customer_id,),
            ).fetchall()
        return {
            "customer": dict(cust) if cust else {"customer_id": customer_id},
            "identities": [dict(i) for i in identities],
        }

    def last_summaries(self, customer_id: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT event_id, channel, intent, summary, result, created_at
                FROM conversation_summaries
                WHERE customer_id = ?
                ORDER BY summary_id DESC
                LIMIT ?
                """,
                (customer_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_confirmed_reservas(self, limit: int = 10, business_id: str = "biz_default") -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT s.event_id, s.customer_id, s.channel, s.summary, s.created_at, s.cita_at, c.name
                FROM conversation_summaries s
                LEFT JOIN customers c ON c.customer_id = s.customer_id
                WHERE s.intent = 'reserva' AND s.result = 'ok'
                  AND COALESCE(s.business_id, 'biz_default') = ?
                ORDER BY summary_id DESC
                LIMIT ?
                """,
                (business_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def last_reserva(self, customer_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT summary, created_at, cita_at FROM conversation_summaries
                WHERE customer_id = ? AND intent = 'reserva' AND result = 'ok'
                ORDER BY summary_id DESC LIMIT 1
                """,
                (customer_id,),
            ).fetchone()
        return dict(row) if row else None

    def cancel_last_reserva(self, customer_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT summary_id, summary FROM conversation_summaries
                WHERE customer_id = ? AND intent = 'reserva' AND result = 'ok'
                ORDER BY summary_id DESC LIMIT 1
                """,
                (customer_id,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE conversation_summaries SET result = 'cancelled' WHERE summary_id = ?",
                (row["summary_id"],),
            )
            return {"summary": row["summary"]}

    def save_turn(
        self,
        *,
        customer_id: str,
        event_id: str,
        channel: str,
        intent: str,
        text: str,
        reply: str,
        result: str,
        cita_at: Optional[str] = None,
        business_id: str = "biz_default",
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at, cita_at, business_id)
                VALUES (?,?,?,?,?,?,datetime('now'),?,?)
                """,
                (customer_id, event_id, channel, intent, text[:240], result, cita_at, business_id),
            )
            conn.execute(
                """
                INSERT INTO messages(customer_id, event_id, channel, direction, text, created_at)
                VALUES (?,?,?,?,?,datetime('now'))
                """,
                (customer_id, event_id, channel, "in", text),
            )
            if reply:
                conn.execute(
                    """
                    INSERT INTO messages(customer_id, event_id, channel, direction, text, created_at)
                    VALUES (?,?,?,?,?,datetime('now'))
                    """,
                    (customer_id, event_id, channel, "out", reply),
                )

    def write_audit(self, data: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_events(
                    event_id, received_at, finished_at, channel, customer_id, agent, model,
                    supervision_level, approval_status, input_summary, output_summary, result, error,
                    why, data_used
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    data.get("event_id"),
                    data.get("received_at"),
                    data.get("finished_at"),
                    data.get("channel"),
                    data.get("customer_id"),
                    data.get("agent"),
                    data.get("model"),
                    data.get("supervision_level"),
                    data.get("approval_status"),
                    data.get("input_summary"),
                    data.get("output_summary"),
                    data.get("result"),
                    data.get("error"),
                    data.get("why"),
                    data.get("data_used"),
                ),
            )

    def list_audit(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_audit(self, event_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM audit_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return dict(row) if row else None

    def has_pending(self, customer_id: str, intent: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT event_id FROM pending_approvals
                WHERE customer_id = ? AND intent = ? AND status = 'pending'
                LIMIT 1
                """,
                (customer_id, intent),
            ).fetchone()
        return bool(row)

    def save_pending_approval(self, data: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_approvals(
                    event_id, customer_id, intent, why, requested_action, notify_text, status, created_at
                ) VALUES (?,?,?,?,?,?,?,datetime('now'))
                """,
                (
                    data.get("event_id"),
                    data.get("customer_id"),
                    data.get("intent"),
                    data.get("why"),
                    data.get("requested_action"),
                    data.get("notify_text"),
                    data.get("status", "pending"),
                ),
            )

    def list_pending(self) -> list[dict[str, Any]]:
        """Muro 40: 'n' es el número que el dueño escribe en aprobar N / rechazar N."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT rowid AS n, * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_decididas(self, limit: int = 10) -> list[dict[str, Any]]:
        """Últimas aprobaciones ya decididas, las más nuevas primero. Solo lectura, para el panel."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_approvals WHERE status IN ('approved', 'rejected')"
                " ORDER BY COALESCE(decided_at, created_at) DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_open_task(self, customer_id: str) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT open_task FROM session_state WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
        return str(row["open_task"]) if row and row["open_task"] else ""

    def last_reply(self, customer_id: str) -> str:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT text FROM messages
                WHERE customer_id = ? AND direction = 'out'
                ORDER BY message_id DESC LIMIT 1
                """,
                (customer_id,),
            ).fetchone()
        return str(row["text"] or "") if row else ""

    def replied_with(self, customer_id: str, fragment: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM messages
                WHERE customer_id = ? AND direction = 'out' AND instr(text, ?) > 0
                LIMIT 1
                """,
                (customer_id, fragment),
            ).fetchone()
        return bool(row)

    def add_note(self, customer_id: str, note: str) -> None:
        note = (note or "").strip()[:240]
        if not customer_id or not note:
            return
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO customer_notes(customer_id, note, created_at) VALUES (?,?,datetime('now'))",
                (customer_id, note),
            )

    def list_notes(self, customer_id: str, limit: int = 3) -> list[dict[str, Any]]:
        if not customer_id:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT note, created_at FROM customer_notes
                WHERE customer_id = ?
                ORDER BY note_id DESC
                LIMIT ?
                """,
                (customer_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_pedido(self, customer_id: str, servicio: str, precio: int, business_id: str = "biz_default") -> None:
        if not customer_id or not servicio:
            return
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO pedidos(customer_id, servicio, precio, created_at, business_id) VALUES (?,?,?,datetime('now'),?)",
                (customer_id, servicio, int(precio), business_id),
            )

    def marcar_aviso(self, event_id: str, plazo: str) -> bool:
        """True la primera vez para esa cita y ese plazo; False si ya estaba avisada."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO avisos_cita(event_id, plazo, created_at) VALUES (?,?,datetime('now'))",
                (event_id, plazo),
            )
            return cur.rowcount == 1

    def aviso_hecho(self, event_id: str, plazo: str) -> bool:
        """True si esa cita y ese plazo ya quedaron marcados. No marca."""
        with self._conn() as conn:
            fila = conn.execute("SELECT 1 FROM avisos_cita WHERE event_id = ? AND plazo = ?", (event_id, plazo)).fetchone()
            return fila is not None

    def marcar_sin_stock(self, codigo: str, business_id: str = "biz_default") -> bool:
        """Muro 64: True la primera vez que ese código queda sin disponible; False si ya se avisó."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO avisos_stock(codigo, business_id, created_at) VALUES (?,?,datetime('now'))",
                (codigo, business_id),
            )
            return cur.rowcount == 1

    def limpiar_sin_stock(self, codigo: str, business_id: str = "biz_default") -> None:
        """Muro 64: volvió a haber. El próximo 0 avisa otra vez."""
        with self._conn() as conn:
            conn.execute("DELETE FROM avisos_stock WHERE codigo = ? AND business_id = ?", (codigo, business_id))

    def marcar_wamid(self, wamid: str) -> bool:
        """True la primera vez que llega ese mensaje de WhatsApp; False si Meta lo reintenta."""
        if not wamid:
            return True
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO wamid_visto(wamid, created_at) VALUES (?, datetime('now'))",
                (wamid,),
            )
            return cur.rowcount == 1

    def add_envio(self, destino: str, tipo: str, texto: str, estado: str) -> None:
        """Una fila por aviso saliente: a quién, qué (corto), para qué y cómo terminó."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO envios(destino, tipo, texto, estado, created_at) VALUES (?,?,?,?,datetime('now'))",
                (destino or "", tipo, (texto or "")[:80], estado),
            )

    def escribio_24h(self, customer_id: str) -> bool:
        """True si el último mensaje entrante de WhatsApp de ese cliente tiene menos de 24 h."""
        if not customer_id:
            return False
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM messages
                WHERE customer_id = ? AND channel = 'whatsapp' AND direction = 'in'
                  AND created_at >= datetime('now', '-24 hours')
                LIMIT 1
                """,
                (customer_id,),
            ).fetchone()
        return bool(row)

    def list_envios(self, limit: int = 10) -> list[dict[str, Any]]:
        """Últimos envíos, los más nuevos primero. Solo para el dueño."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT destino, tipo, texto, estado, created_at FROM envios ORDER BY envio_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def last_pedido(self, customer_id: str) -> dict[str, Any] | None:
        if not customer_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT servicio, precio, created_at FROM pedidos WHERE customer_id = ? ORDER BY created_at DESC, pedido_id DESC LIMIT 1",
                (customer_id,),
            ).fetchone()
        return dict(row) if row else None

    def pedido_por_pagar(self, customer_id: str) -> bool:
        """Muro 42: True si ese cliente tiene un pedido 'anotado' o 'por verificar'."""
        if not customer_id:
            return False
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM pedidos WHERE customer_id = ? AND estado IN ('anotado', 'por verificar') LIMIT 1",
                (customer_id,),
            ).fetchone()
        return bool(row)

    def foto_por_verificar(self, customer_id: str, business_id: str = "biz_default") -> int | None:
        """Muro 55: el pedido más nuevo del cliente sin pagar pasa a 'por verificar'. Su número, o None si no hay."""
        if not customer_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT pedido_id FROM pedidos WHERE customer_id = ? AND estado IN ('anotado', 'por verificar')"
                " AND COALESCE(business_id, 'biz_default') = ? ORDER BY created_at DESC, pedido_id DESC LIMIT 1",
                (customer_id, business_id),
            ).fetchone()
            if not row:
                return None
            conn.execute("UPDATE pedidos SET estado = 'por verificar' WHERE pedido_id = ?", (row[0],))
        return int(row[0])

    def pedidos_abiertos(self, codigo: str, business_id: str = "biz_default") -> int:
        """Muro 47/49: pedidos de ese código que todavía no se entregan ni se rechazan.
        Cuenta por código ('CAF01 ...'), no por nombre: si el dueño cambia el nombre, la unidad sigue reservada."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM pedidos WHERE (servicio = ? OR substr(servicio, 1, length(?) + 1) = ? || ' ')"
                " AND estado IN ('anotado', 'por verificar', 'pagado', 'en camino')"
                " AND COALESCE(business_id, 'biz_default') = ?",
                (codigo, codigo, codigo, business_id),
            ).fetchone()
        return int(row[0]) if row else 0

    def list_pedidos(self, limit: int = 15, business_id: str = "biz_default") -> list[dict[str, Any]]:
        """Filas de pedidos de todos los clientes del negocio, las más nuevas primero. Solo para el dueño."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT p.pedido_id, p.servicio, p.precio, p.estado, p.created_at, p.customer_id, c.name, c.phone
                FROM pedidos p
                LEFT JOIN customers c ON c.customer_id = p.customer_id
                WHERE COALESCE(p.business_id, 'biz_default') = ?
                ORDER BY p.created_at DESC, p.pedido_id DESC
                LIMIT ?
                """,
                (business_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def entregar_pedido(self, pedido_id: int, business_id: str = "biz_default") -> bool:
        """Muro 38: solo un pedido 'pagado' o 'en camino' pasa a 'entregado'. AXEL no cobra."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE pedidos SET estado = 'entregado' WHERE pedido_id = ? AND estado IN ('pagado', 'en camino')"
                " AND COALESCE(business_id, 'biz_default') = ?",
                (pedido_id, business_id),
            )
            return cur.rowcount == 1

    def cancelar_pedido(self, pedido_id: int, business_id: str = "biz_default") -> str:
        """Muro 50: 'anotado' o 'por verificar' pasa a 'rechazado' y la unidad vuelve al disponible.
        Devuelve 'cancelado' si lo canceló; si no, el estado que tiene ('' si no existe)."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE pedidos SET estado = 'rechazado' WHERE pedido_id = ? AND estado IN ('anotado', 'por verificar')"
                " AND COALESCE(business_id, 'biz_default') = ?",
                (pedido_id, business_id),
            )
            if cur.rowcount == 1:
                return "cancelado"
            row = conn.execute(
                "SELECT estado FROM pedidos WHERE pedido_id = ? AND COALESCE(business_id, 'biz_default') = ?",
                (pedido_id, business_id),
            ).fetchone()
        return str(row[0]) if row else ""

    def en_camino_pedido(self, pedido_id: int, business_id: str = "biz_default") -> bool:
        """Muro 52: solo un pedido 'pagado' pasa a 'en camino'. AXEL no le escribe al proveedor."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE pedidos SET estado = 'en camino' WHERE pedido_id = ? AND estado = 'pagado'"
                " AND COALESCE(business_id, 'biz_default') = ?",
                (pedido_id, business_id),
            )
            return cur.rowcount == 1

    def pagar_pedido(self, pedido_id: int, business_id: str = "biz_default") -> bool:
        """Muro 38: solo el dueño marca pagado. AXEL no mira el banco ni acepta una foto como pago."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE pedidos SET estado = 'pagado' WHERE pedido_id = ? AND estado IN ('anotado', 'por verificar')"
                " AND COALESCE(business_id, 'biz_default') = ?",
                (pedido_id, business_id),
            )
            return cur.rowcount == 1

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        if not customer_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_customer_name(self, customer_id: str, name: str) -> None:
        name = (name or "").strip()[:80]
        if not name:
            return
        with self._conn() as conn:
            # Nombre nuevo después de "borrar mis datos": la ficha vuelve a mostrarlo.
            conn.execute(
                "UPDATE customers SET name = ?, datos_borrados = 0, updated_at = datetime('now') WHERE customer_id = ?",
                (name, customer_id),
            )

    def list_customers(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT customer_id, name, phone, email, updated_at
                FROM customers
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_whatsapp_customers(self, limit: int = 20) -> list[dict[str, Any]]:
        """Clientes con identidad whatsapp y la última vez que escribieron por ese canal."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT c.customer_id, c.name, c.phone, MAX(m.created_at) AS last_in
                FROM identities i
                JOIN customers c ON c.customer_id = i.customer_id
                LEFT JOIN messages m
                  ON m.customer_id = c.customer_id AND m.channel = 'whatsapp' AND m.direction = 'in'
                WHERE i.channel = 'whatsapp'
                GROUP BY c.customer_id
                ORDER BY last_in DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def clientes_de_canal(self, channel: str) -> set[str]:
        """customer_id con identidad en ese canal. Solo lectura."""
        with self._conn() as conn:
            rows = conn.execute("SELECT DISTINCT customer_id FROM identities WHERE channel = ?", (channel,)).fetchall()
        return {str(r["customer_id"]) for r in rows}

    def list_conversaciones(self, limit: int = 20) -> list[dict[str, Any]]:
        """Último mensaje vivo de cada cliente, los más nuevos primero. Sin internos (panel, prueba). Solo lectura."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT m.customer_id, m.channel, m.direction, m.text, m.created_at, c.name, c.phone, c.datos_borrados
                FROM messages m
                JOIN (SELECT customer_id, MAX(message_id) AS ultimo FROM messages
                      WHERE COALESCE(channel, '') IN ('whatsapp', '') GROUP BY customer_id) u
                  ON m.message_id = u.ultimo
                LEFT JOIN customers c ON c.customer_id = m.customer_id
                ORDER BY m.message_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_mensajes(self, customer_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Últimos mensajes vivos de un cliente, del más viejo al más nuevo. Sin internos. Solo lectura, para el hilo."""
        if not customer_id:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT direction, channel, text, created_at FROM messages"
                " WHERE customer_id = ? AND COALESCE(channel, '') IN ('whatsapp', '') ORDER BY message_id DESC LIMIT ?",
                (customer_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def purge_ghost_customers(self) -> int:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT customer_id FROM customers c
                WHERE (name IS NULL OR TRIM(name) = '')
                  AND (phone IS NULL OR TRIM(phone) = '')
                  AND (email IS NULL OR TRIM(email) = '')
                  -- Sin datos pero con pedido, cita viva o N3 pendiente no es fantasma.
                  AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE p.customer_id = c.customer_id)
                  AND NOT EXISTS (
                      SELECT 1 FROM conversation_summaries s
                      WHERE s.customer_id = c.customer_id AND s.intent = 'reserva' AND s.result = 'ok'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM pending_approvals a WHERE a.customer_id = c.customer_id AND a.status = 'pending'
                  )
                """
            ).fetchall()
            ids = [r["customer_id"] for r in rows]
            for cid in ids:
                conn.execute("DELETE FROM identities WHERE customer_id = ?", (cid,))
                conn.execute("DELETE FROM customers WHERE customer_id = ?", (cid,))
        return len(ids)

    def find_by_identity(self, channel: str, channel_user_id: str) -> dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT c.* FROM identities i
                JOIN customers c ON c.customer_id = i.customer_id
                WHERE i.channel = ? AND i.channel_user_id = ?
                """,
                (channel, channel_user_id),
            ).fetchone()
        return dict(row) if row else {}

    def set_customer_email(self, customer_id: str, email: str) -> None:
        email = (email or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            return
        with self._conn() as conn:
            conn.execute(
                "UPDATE customers SET email = ?, updated_at = datetime('now') WHERE customer_id = ?",
                (email[:120], customer_id),
            )

    def set_customer_phone(self, customer_id: str, phone: str) -> None:
        phone = "".join(ch for ch in (phone or "") if ch.isdigit())
        if len(phone) < 10:
            return
        phone = phone[-10:]
        with self._conn() as conn:
            conn.execute(
                "UPDATE customers SET phone = ?, updated_at = datetime('now') WHERE customer_id = ?",
                (phone, customer_id),
            )

    def set_open_task(self, customer_id: str, task: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO session_state(customer_id, open_task, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(customer_id) DO UPDATE SET
                    open_task = excluded.open_task,
                    updated_at = excluded.updated_at
                """,
                (customer_id, task),
            )

    def resolve_pending(self, event_id: str, status: str) -> None:
        if status not in {"approved", "rejected"}:
            return
        with self._conn() as conn:
            fila = conn.execute(
                "SELECT customer_id, intent, status FROM pending_approvals WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            conn.execute(
                "UPDATE pending_approvals SET status = ?, decided_at = datetime('now') WHERE event_id = ?",
                (status, event_id),
            )
            # Borrado aprobado: fuera nombre, correo y notas. El celular sigue en la identidad para no duplicar
            # al cliente. Pedidos, citas y auditoría se quedan.
            if fila and fila["intent"] == "borrar_datos" and fila["status"] == "pending" and status == "approved":
                cid = fila["customer_id"]
                conn.execute(
                    "UPDATE customers SET name = NULL, email = NULL, datos_borrados = 1, updated_at = datetime('now') WHERE customer_id = ?",
                    (cid,),
                )
                conn.execute("DELETE FROM customer_notes WHERE customer_id = ?", (cid,))
            conn.execute(
                "UPDATE audit_events SET approval_status = ? WHERE event_id = ?",
                (status, event_id),
            )
