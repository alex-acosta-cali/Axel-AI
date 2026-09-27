from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

DEFAULT_KB = {
    "negocio": "Negocio piloto AXEL",
    "saludo": "Hola, soy AXEL del negocio. ¿En qué te ayudo?",
    "faqs": [],
}


def load_kb() -> dict:
    path = _kb_path()
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


def set_business_name(nombre: str) -> str:
    nombre = " ".join((nombre or "").split()).strip(" .,;:!¡¿?\"'")[:60]
    if not nombre:
        return ""
    kb = load_kb()
    kb["negocio"] = nombre
    respuesta = f"El negocio se llama {nombre}."
    faqs = kb.setdefault("faqs", [])
    for item in faqs:
        if "nombre del negocio" in (item.get("q") or []):
            item["a"] = respuesta
            break
    else:
        faqs.append(
            {
                "q": ["nombre del negocio", "como se llama el negocio", "cómo se llama el negocio"],
                "a": respuesta,
            }
        )
    _kb_path().write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    return nombre


def get_hours() -> tuple[tuple[int, int], tuple[int, int]]:
    """(hora, minuto) de apertura y cierre desde kb["horario"]. Si falta, 8:00 a 19:00."""
    m = re.match(r"^(\d{1,2}):(\d{2}) a (\d{1,2}):(\d{2})$", str(load_kb().get("horario") or ""))
    if not m:
        return (8, 0), (19, 0)
    return (int(m.group(1)), int(m.group(2))), (int(m.group(3)), int(m.group(4)))


def set_hours(abre: str, cierra: str) -> str:
    horario = f"{abre} a {cierra}"
    kb = load_kb()
    kb["horario"] = horario
    faqs = kb.setdefault("faqs", [])
    for item in faqs:
        if "horario" in (item.get("q") or []):
            nuevo, n = re.subn(r"\d{1,2}:\d{2} a \d{1,2}:\d{2}", horario, item.get("a") or "")
            item["a"] = nuevo if n else f"Atendemos de {horario}."
            break
    else:
        faqs.insert(0, {"q": ["horario", "horarios", "abren", "cierran"], "a": f"Atendemos de {horario}."})
    _kb_path().write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    return horario