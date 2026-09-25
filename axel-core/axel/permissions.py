from __future__ import annotations

# Fuente de verdad v1. Si la accion no esta listada -> nivel 3.


LEVELS = {
    "pregunta": 1,
    "saludo": 1,
    "datos": 1,
    "cierre": 1,
    "admin_kb": 1,
    "nota": 1,
    "mi_cita": 1,
    "reserva": 2,
    "reprogramar": 2,
    "cancelar": 2,
    "venta": 1,
    "queja": 3,
    "reembolso": 3,
    "descuento_grande": 3,
    "admin": 3,
}


def classify_level(intent: str) -> int:
    return LEVELS.get(intent, 3)


def needs_customer_confirm(level: int) -> bool:
    return level == 2


def needs_owner_approval(level: int) -> bool:
    return level == 3


REASONS = {
    1: "accion automatica permitida",
    2: "requiere confirmacion explicita del cliente",
    3: "requiere aprobacion del dueno; AXEL no ejecuta",
}


def reason_for(intent: str, level: int) -> str:
    return f"intent={intent}; nivel={level}; {REASONS.get(level, 'nivel desconocido')}"