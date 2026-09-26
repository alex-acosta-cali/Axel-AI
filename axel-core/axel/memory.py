from __future__ import annotations

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
"""


def _new_customer_id() -> str:
    return f"cus_{uuid4().hex[:10]}"


class Memory:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            for col, typ in (("why", "TEXT"), ("data_used", "TEXT")):
                try:
                    conn.execute(f"ALTER TABLE audit_events ADD COLUMN {col} {typ}")
                except sqlite3.OperationalError:
                    pass

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

    def list_confirmed_reservas(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT s.event_id, s.customer_id, s.channel, s.summary, s.created_at, c.name
                FROM conversation_summaries s
                LEFT JOIN customers c ON c.customer_id = s.customer_id
                WHERE s.intent = 'reserva' AND s.result = 'ok'
                ORDER BY summary_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def last_reserva(self, customer_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT summary, created_at FROM conversation_summaries
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
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conversation_summaries(customer_id, event_id, channel, intent, summary, result, created_at)
                VALUES (?,?,?,?,?,?,datetime('now'))
                """,
                (customer_id, event_id, channel, intent, text[:240], result),
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
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_open_task(self, customer_id: str) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT open_task FROM session_state WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
        return str(row["open_task"]) if row and row["open_task"] else ""

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
            conn.execute(
                "UPDATE customers SET name = ?, updated_at = datetime('now') WHERE customer_id = ?",
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

    def purge_ghost_customers(self) -> int:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT customer_id FROM customers
                WHERE (name IS NULL OR TRIM(name) = '')
                  AND (phone IS NULL OR TRIM(phone) = '')
                  AND (email IS NULL OR TRIM(email) = '')
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
            conn.execute(
                "UPDATE pending_approvals SET status = ? WHERE event_id = ?",
                (status, event_id),
            )
            conn.execute(
                "UPDATE audit_events SET approval_status = ? WHERE event_id = ?",
                (status, event_id),
            )
