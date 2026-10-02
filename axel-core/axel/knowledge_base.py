from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

DEFAULT_KB = {
    "negocio": "Negocio piloto AXEL",
    "saludo": "Hola, soy AXEL del negocio. ¿En qué te ayudo?",
    "faqs": [],
}


def load_kb(business_id: str = "biz_default") -> dict:
    """Muro 34-35: hoy solo existe biz_default (kb.json). Otro id no ve la KB del piloto.
    Muro 39: si kb.json falta o está roto, usa la última copia buena. No tumba AXEL."""
    if business_id != "biz_default":
        return dict(DEFAULT_KB, faqs=[])
    path = _kb_path()
    datos = _leer_json(path)
    if datos is not None:
        return datos
    for copia in _copias_kb():
        datos = _leer_json(copia)
        if datos is not None:
            print(f"KB: {path.name} falta o está roto. Uso la copia {copia.name}.")
            return datos
    return DEFAULT_KB


def _leer_json(path: Path) -> Optional[dict]:
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def _ultima_path() -> Path:
    """Copia de la última KB guardada bien, junto a kb.json."""
    path = _kb_path()
    return path.with_name(path.stem + ".ultima.json")


def _copias_kb() -> list[Path]:
    """Primero la última guardada; después las de copia.ps1 / copia_vps.sh, la más nueva primero."""
    copias = Path(__file__).resolve().parents[2] / "copias"
    viejas = sorted(copias.glob("kb_*.json"), reverse=True) if copias.is_dir() else []
    return [_ultima_path(), *viejas]


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


def tono() -> str:
    """kb["tono"]: 'cercano' (tú) o 'formal' (usted). Si falta o no se entiende, cercano."""
    return "formal" if _plano(str(load_kb().get("tono") or "")).strip() == "formal" else "cercano"


def set_tono(valor: str) -> str:
    """Guarda kb["tono"] ('cercano' o 'formal'). Devuelve el que quedó."""
    kb = load_kb()
    kb["tono"] = "formal" if _plano(valor).strip() == "formal" else "cercano"
    _guardar(kb)
    return kb["tono"]


def agenda_palabras() -> list[str]:
    """kb["agenda_palabras"]: palabras del negocio que piden reserva ('mesa', 'turno')."""
    return [str(p).strip() for p in load_kb().get("agenda_palabras") or [] if str(p).strip()]


# Pregunta para ofrecer hueco según la palabra del negocio; "mesa" gana a "turno". Sin ninguna, la de siempre.
OFERTAS_AGENDA = (("mesa", "¿Reservamos mesa?"), ("turno", "¿Te anoto un turno?"))
OFERTA_CITA = "¿Quieres que te reserve un cupo?"


def oferta_agenda() -> str:
    palabras = {_plano(p) for p in agenda_palabras()}
    return next((texto for palabra, texto in OFERTAS_AGENDA if palabra in palabras), OFERTA_CITA)


def set_agenda_palabras(texto: str) -> list[str]:
    """Reemplaza kb["agenda_palabras"] con las palabras del dueño. [] si no trae ninguna."""
    palabras = []
    for p in re.findall(r"[a-záéíóúüñ]{2,20}", (texto or "").lower()):
        if p not in palabras:
            palabras.append(p)
    palabras = palabras[:15]
    if palabras:
        kb = load_kb()
        kb["agenda_palabras"] = palabras
        _guardar(kb)
    return palabras


def servicios(business_id: str = "biz_default") -> list[dict]:
    return [s for s in load_kb(business_id).get("servicios") or [] if str(s.get("nombre") or "").strip()]


def precio_txt(valor) -> str:
    return f"${int(valor):,}".replace(",", ".")


def agotado(s: dict) -> bool:
    """Solo stock 0 bloquea. Sin 'stock' (o no entero) se trata como hay. No es inventario: no se resta al vender."""
    try:
        return "stock" in s and int(s["stock"]) == 0
    except (TypeError, ValueError):
        return False


def no_hay_ahora(s: dict) -> str:
    return f"No hay {s['nombre']} ahora."


def lista_servicios() -> str:
    items = servicios()
    if not items:
        return NO_HAY
    return "Lista: " + ", ".join(
        f"{s['nombre']} agotado" if agotado(s) else f"{s['nombre']} {precio_txt(s.get('precio') or 0)}" for s in items
    ) + ". ¿Cuál te interesa?"


def servicio_en(text: str) -> Optional[dict]:
    """El servicio de la KB nombrado en el texto; el nombre más largo gana ('corte + barba' antes que 'corte')."""
    plano = _plano(text)
    for s in sorted(servicios(), key=lambda s: -len(str(s["nombre"]))):
        nombre = _plano(str(s["nombre"])).strip()
        for forma in {nombre, nombre.replace(" + ", " y ")}:
            if re.search(rf"(?<!\w){re.escape(forma)}(?!\w)", plano):
                return s
    palabras = set(re.findall(r"\w+", plano))
    for nombre, sinonimos in _SINONIMOS.items():
        if palabras & sinonimos:
            return buscar_servicio(nombre)
    return None


# Palabra del cliente -> nombre del servicio. Solo sirve si ese servicio existe en la KB.
_SINONIMOS = {"corte": {"cortarme", "pelo"}}
_PIDE_LISTA = re.compile(r"\b(precios|lista|tarifas)\b")


def answer_servicio(text: str) -> Optional[str]:
    """Precio de un servicio, la lista, o NO_HAY. None si el texto no habla de precios ni de servicios."""
    s = servicio_en(text)
    if s and _PIDE_LISTA.search(_plano(text)):
        return lista_servicios()
    if s and agotado(s):
        return no_hay_ahora(s)
    if s:
        cupo = f" {oferta_agenda()}" if agenda() else ""
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


def set_stock(producto: str, cantidad: int) -> bool:
    """Pone servicios[].stock. Solo lo escribe el dueño; vender no lo resta."""
    kb = load_kb()
    cambiado = False
    for s in kb.get("servicios") or []:
        if _plano(str(s.get("nombre") or "")).strip() == _plano(producto).strip():
            s["stock"] = int(cantidad)
            cambiado = True
    if cambiado:
        _guardar(kb)
    return cambiado


def productos() -> list[dict]:
    """kb["productos"]: código, nombre, precio, stock. Vacía al empezar. Los precios al cliente siguen en servicios[]."""
    return list(load_kb().get("productos") or [])


def buscar_producto(codigo: str) -> Optional[dict]:
    codigo = " ".join((codigo or "").split()).upper()
    return next((p for p in productos() if str(p.get("codigo") or "") == codigo), None)


def set_producto(codigo: str, nombre: str, precio: int, stock: int) -> dict:
    """Crea o reemplaza el producto con ese código. {} si código o nombre no sirven."""
    codigo = " ".join((codigo or "").split()).upper()[:20]
    nombre = nombre_servicio(nombre)
    if not codigo or len(re.findall(r"[a-záéíóúüñ]", nombre)) < 2:
        return {}
    item = {"codigo": codigo, "nombre": nombre, "precio": int(precio), "stock": int(stock)}
    kb = load_kb()
    kb["productos"] = [p for p in kb.get("productos") or [] if p.get("codigo") != codigo] + [item]
    _guardar(kb)
    return item


def bajar_stock(servicio: str) -> Optional[dict]:
    """Muro 45: al entregar, el producto de ese pedido ('CODIGO nombre') baja 1. Nunca de 0. None si no es del inventario."""
    kb = load_kb()
    for p in kb.get("productos") or []:
        if f"{p.get('codigo')} {p.get('nombre')}" == (servicio or "").strip():
            p["stock"] = max(int(p.get("stock") or 0) - 1, 0)
            _guardar(kb)
            return p
    return None


def _guardar(kb: dict) -> None:
    """Muro 39: escribe en un temporal y reemplaza al final. Un apagón no deja kb.json a medias."""
    texto = json.dumps(kb, ensure_ascii=False, indent=2)
    for destino in (_kb_path(), _ultima_path()):
        tmp = destino.with_name(destino.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, destino)


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


def vaciar_servicios() -> None:
    kb = load_kb()
    kb["servicios"] = []
    _guardar(kb)


def remove_servicio(nombre: str) -> bool:
    s = buscar_servicio(nombre)
    if not s:
        return False
    kb = load_kb()
    kb["servicios"] = [x for x in kb.get("servicios") or [] if x.get("nombre") != s["nombre"]]
    _guardar(kb)
    return True


_PIDE_UBICACION = re.compile(r"\b(donde quedan?|direccion|ubicacion)\b")


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


def set_politica(clave: str, texto: str) -> str:
    """kb["politicas"][cancelacion|garantia] con el texto del dueño."""
    texto = " ".join((texto or "").split())[:300]
    if texto:
        kb = load_kb()
        kb.setdefault("politicas", {})[clave] = texto
        _guardar(kb)
    return texto


def set_ubicacion(texto: str) -> str:
    texto = " ".join((texto or "").split()).strip(" ¿?\"'")[:150]
    if texto:
        kb = load_kb()
        kb["ubicacion"] = texto
        _guardar(kb)
    return texto


def set_proveedor_contacto(numero: str) -> str:
    """Muro 46: solo el número del proveedor. AXEL no le escribe. Sin costo. '' si no son 7 a 15 cifras."""
    cifras = re.sub(r"\D", "", numero or "")
    if not 7 <= len(cifras) <= 15:
        return ""
    kb = load_kb()
    kb["proveedor_contacto"] = cifras
    _guardar(kb)
    return cifras


def proveedor_contacto() -> str:
    return str(load_kb().get("proveedor_contacto") or "")


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
    _guardar(kb)
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
    _guardar(kb)
    return horario