from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

DEFAULT_KB = {
    "negocio": "Negocio piloto AXEL",
    "saludo": "Hola, soy AXEL del negocio. ¿En qué te ayudo?",
    "faqs": [],
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


def answer_pitch(text: str) -> Optional[str]:
    raw = (text or "").lower()
    path = Path(__file__).resolve().parents[1] / "pitch.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data.get("faqs", []):
        if any(k in raw for k in item.get("q", [])):
            return item.get("a")
    return None


def _cuaderno_path() -> Path | None:
    docs = Path(__file__).resolve().parents[1].parent / "docs"
    if not docs.exists():
        return None
    files = sorted(docs.glob("CUADERNO*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def answer_cuaderno(text: str) -> Optional[str]:
    raw = (text or "").lower()
    claves = (
        "cuaderno",
        "levantar",
        "github",
        "ngrok",
        "app id",
        "que hicimos",
        "qué hicimos",
    )
    if not any(k in raw for k in claves):
        return None
    path = _cuaderno_path()
    if path is None:
        return "No encuentro el cuaderno en docs. El avance corto está en cómo va el proyecto."
    body = path.read_text(encoding="utf-8", errors="ignore")
    if "levantar" in raw:
        if "## LEVANTAR" in body:
            bloque = body.split("## LEVANTAR", 1)[1].split("## ", 1)[0]
            return "Para levantar AXEL:\n" + bloque.strip()[:800]
    limpio = " ".join(line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#"))
    return limpio[:700]


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