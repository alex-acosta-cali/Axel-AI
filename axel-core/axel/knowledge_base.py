from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

DEFAULT_KB = {
    "negocio": "Negocio piloto AXEL",
    "saludo": "Hola, soy AXEL del negocio. ¿En qué te ayudo?",
    "faqs": [
        {"q": ["horario", "horarios", "abren", "cierran"], "a": "Atendemos de lunes a sábado, 9:00 a 18:00."},
        {"q": ["dirección", "direccion", "ubicación", "ubicacion", "donde"], "a": "Estamos en Cali. Escribe tu barrio y te confirmamos cómo llegar."},
        {"q": ["precio", "cuanto", "cuánto", "vale"], "a": "Dime qué servicio o producto buscas y te doy el precio de la lista."},
        {"q": ["pago", "transferencia", "efectivo"], "a": "Aceptamos efectivo y transferencia. El link de pago te lo envía el dueño si aplica."},
    ],
}


def load_kb() -> dict:
    path = Path(__file__).resolve().parents[1] / "kb.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return DEFAULT_KB


def answer(text: str) -> Optional[str]:
    raw = (text or "").lower()
    kb = load_kb()
    for item in kb.get("faqs", []):
        if any(k in raw for k in item.get("q", [])):
            return item.get("a")
    return None


def greeting() -> str:
    return load_kb().get("saludo", "Hola, soy AXEL. ¿En qué te ayudo?")
