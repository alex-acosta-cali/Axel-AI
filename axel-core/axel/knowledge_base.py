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


def _kb_path() -> Path:
    return Path(__file__).resolve().parents[1] / "kb.json"


def set_price(producto: str, pesos: str) -> str:
    producto = (producto or "").lower().strip()
    pesos = pesos.replace(".", "").replace(",", "")
    path = _kb_path()
    kb = load_kb()
    marca = f"${int(pesos):,}".replace(",", ".")
    cambiado = False
    for item in kb.get("faqs", []):
        keys = " ".join(item.get("q") or [])
        if producto in keys:
            item["a"] = f"El {producto} quedó en {marca}."
            cambiado = True
    if producto == "corte":
        for item in kb.get("faqs", []):
            if "precio" in " ".join(item.get("q") or []):
                item["a"] = (
                    f"Lista piloto: corte {marca}, "
                    "barba $15.000, corte + barba $35.000. ¿Cuál te interesa?"
                )
                cambiado = True
    if not cambiado:
        return ""
    path.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    return marca