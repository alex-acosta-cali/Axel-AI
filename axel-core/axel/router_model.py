from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ModelDecision:
    model: str
    fallback: str
    reason: str


# Matriz v1. No llama al proveedor: solo decide. El cliente LLM se enchufa despues.
TASK_MATRIX = {
    "clasificar": ("fast", "baja latencia, tarea simple"),
    "pregunta": ("fast", "FAQ / atencion"),
    "saludo": ("fast", "saludo corto"),
    "reserva": ("standard", "reserva requiere precision"),
    "reprogramar": ("standard", "cambio de cita"),
    "cancelar": ("standard", "cancelacion"),
    "venta": ("standard", "venta / objecion"),
    "queja": ("standard", "calidad alta, riesgo reputacional"),
    "reembolso": ("standard", "accion sensible"),
    "descuento_grande": ("standard", "accion sensible"),
    "admin": ("standard", "fuera de flujo de cliente"),
}


def _names() -> tuple[str, str, str]:
    fast = os.getenv("MODEL_FAST", "grok-fast")
    standard = os.getenv("MODEL_STANDARD", "grok-standard")
    fallback = os.getenv("MODEL_FALLBACK", "gpt-4.1-mini")
    return fast, standard, fallback


def route(task_type: str, quality: str = "media", latency_max_ms: int = 4000) -> ModelDecision:
    fast, standard, fallback = _names()
    tier, why = TASK_MATRIX.get(task_type, ("standard", "tarea no listada: usar calidad media-alta"))
    if quality == "alta":
        tier = "standard"
        why = f"{why} + calidad alta pedida"
    if latency_max_ms <= 1500:
        tier = "fast"
        why = f"{why} + latencia estricta"
    model = fast if tier == "fast" else standard
    return ModelDecision(model=model, fallback=fallback, reason=why)
