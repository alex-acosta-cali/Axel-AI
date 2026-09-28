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


NO_HAY = "No tengo esa información en la base del negocio."
_PIDE_PRECIO = re.compile(r"\b(precios?|cuanto|vale|valen|valor|valores|cuesta|cuestan|cobran|lista|tarifas?)\b")
# Palabras que no nombran un servicio: si solo queda esto, piden la lista completa.
_RELLENO = set(
    "hola buenas el la los las de del un una unos unas por que cual cuales me te es son y a en al "
    "cuanto vale valen valor valores cuesta cuestan cobran precio precios lista tarifa tarifas "
    "servicio servicios tienen tiene hay sale salen favor porfa pls plis the su sus mas me dices "
    "dime quisiera saber quiero".split()
)


def _plano(text: str) -> str:
    return (text or "").lower().translate(str.maketrans("áéíóúü", "aeiouu"))


def agenda() -> bool:
    """kb["agenda"]; si falta, el negocio agenda (como hasta ahora)."""
    return bool(load_kb().get("agenda", True))


def servicios() -> list[dict]:
    return [s for s in load_kb().get("servicios") or [] if str(s.get("nombre") or "").strip()]


def precio_txt(valor) -> str:
    return f"${int(valor):,}".replace(",", ".")


def lista_servicios() -> str:
    items = servicios()
    if not items:
        return NO_HAY
    return "Lista: " + ", ".join(f"{s['nombre']} {precio_txt(s.get('precio') or 0)}" for s in items) + ". ¿Cuál te interesa?"


def servicio_en(text: str) -> Optional[dict]:
    """El servicio de la KB nombrado en el texto; el nombre más largo gana ('corte + barba' antes que 'corte')."""
    plano = _plano(text)
    for s in sorted(servicios(), key=lambda s: -len(str(s["nombre"]))):
        nombre = _plano(str(s["nombre"])).strip()
        for forma in {nombre, nombre.replace(" + ", " y ")}:
            if re.search(rf"(?<!\w){re.escape(forma)}(?!\w)", plano):
                return s
    return None


def answer_servicio(text: str) -> Optional[str]:
    """Precio de un servicio, la lista, o NO_HAY. None si el texto no habla de precios ni de servicios."""
    s = servicio_en(text)
    if s:
        cupo = " ¿Quieres que te reserve un cupo?" if agenda() else ""
        nombre = str(s["nombre"])
        return f"{nombre[:1].upper()}{nombre[1:]}: {precio_txt(s.get('precio') or 0)}.{cupo}"
    plano = _plano(text)
    if not _PIDE_PRECIO.search(plano):
        return None
    resto = [w for w in re.findall(r"\w+", plano) if w not in _RELLENO]
    return NO_HAY if resto else lista_servicios()


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
    """Cambia el precio en servicios[]. Las FAQ no llevan precios."""
    producto = (producto or "").lower().strip()
    pesos = pesos.replace(".", "").replace(",", "")
    kb = load_kb()
    cambiado = False
    for s in kb.get("servicios") or []:
        if _plano(str(s.get("nombre") or "")).strip() == _plano(producto):
            s["precio"] = int(pesos)
            cambiado = True
    if not cambiado:
        return ""
    _guardar(kb)
    return precio_txt(pesos)


def _guardar(kb: dict) -> None:
    _kb_path().write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")


def nombre_servicio(nombre: str) -> str:
    return " ".join((nombre or "").lower().split()).strip(" .,;:!¡¿?\"'")[:40]


def buscar_servicio(nombre: str) -> Optional[dict]:
    """Servicio con ese nombre exacto (sin tildes ni mayúsculas)."""
    buscado = _plano(nombre_servicio(nombre))
    for s in servicios():
        if _plano(nombre_servicio(str(s["nombre"]))) == buscado:
            return s
    return None


def set_rubro(rubro: str) -> str:
    rubro = " ".join((rubro or "").split()).strip(" .,;:!¡¿?\"'")[:40]
    if rubro:
        kb = load_kb()
        kb["rubro"] = rubro
        _guardar(kb)
    return rubro


def set_agenda(activa: bool) -> None:
    kb = load_kb()
    kb["agenda"] = bool(activa)
    _guardar(kb)


def add_servicio(nombre: str, precio: int) -> str:
    """'' si el nombre no sirve o ya existe."""
    nombre = nombre_servicio(nombre)
    if len(re.findall(r"[a-záéíóúüñ]", nombre)) < 2 or buscar_servicio(nombre):
        return ""
    kb = load_kb()
    kb.setdefault("servicios", []).append({"nombre": nombre, "precio": int(precio)})
    _guardar(kb)
    return nombre


def remove_servicio(nombre: str) -> bool:
    s = buscar_servicio(nombre)
    if not s:
        return False
    kb = load_kb()
    kb["servicios"] = [x for x in kb.get("servicios") or [] if x.get("nombre") != s["nombre"]]
    _guardar(kb)
    return True


_PIDE_UBICACION = re.compile(r"\b(donde|direccion|ubicacion|ubicados)\b")


def answer_ubicacion(text: str) -> Optional[str]:
    """kb["ubicacion"] o NO_HAY si el texto pregunta dónde queda. None si no pregunta eso."""
    if not _PIDE_UBICACION.search(_plano(text)):
        return None
    return str(load_kb().get("ubicacion") or "").strip() or NO_HAY


_PIDE_POLITICA = (
    ("cancelacion", re.compile(r"\b(cancelacion|cancelaciones|politica de cita)\b")),
    ("garantia", re.compile(r"\b(garantia|garantias)\b")),
)


def answer_politica(text: str) -> Optional[str]:
    """kb["politicas"][cancelacion|garantia] o NO_HAY si se pregunta por ella. None si no."""
    plano = _plano(text)
    for clave, patron in _PIDE_POLITICA:
        if patron.search(plano):
            return str((load_kb().get("politicas") or {}).get(clave) or "").strip() or NO_HAY
    return None


def set_ubicacion(texto: str) -> str:
    texto = " ".join((texto or "").split()).strip(" ¿?\"'")[:150]
    if texto:
        kb = load_kb()
        kb["ubicacion"] = texto
        _guardar(kb)
    return texto


def _faq_con(faqs: list[dict], clave: str) -> Optional[dict]:
    buscada = _plano(clave)
    for item in faqs:
        if any(_plano(str(k)) == buscada for k in item.get("q") or []):
            return item
    return None


def add_faq(clave: str, respuesta: str) -> str:
    """Crea o reemplaza la FAQ de esa clave con la respuesta del dueño. '' si la clave no sirve."""
    clave = nombre_servicio(clave)
    respuesta = " ".join((respuesta or "").split())[:300]
    if len(re.findall(r"[a-záéíóúüñ]", clave)) < 2 or not respuesta:
        return ""
    kb = load_kb()
    faqs = kb.setdefault("faqs", [])
    item = _faq_con(faqs, clave)
    if item:
        item["a"] = respuesta
    else:
        faqs.append({"q": [clave], "a": respuesta})
    _guardar(kb)
    return clave


def remove_faq(clave: str) -> bool:
    kb = load_kb()
    faqs = kb.get("faqs") or []
    item = _faq_con(faqs, nombre_servicio(clave))
    if not item:
        return False
    kb["faqs"] = [x for x in faqs if x is not item]
    _guardar(kb)
    return True


def set_franjas(franjas: list[tuple[int, int]]) -> None:
    kb = load_kb()
    kb["franjas"] = [h if m == 0 else f"{h}:{m:02d}" for h, m in sorted(set(franjas))]
    _guardar(kb)


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