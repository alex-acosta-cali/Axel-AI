from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from axel import knowledge_base as kb
from axel.envelope import Envelope

_CALI = timezone(timedelta(hours=-5))
SIN_AGENDA = "Este negocio no agenda citas por este canal."


def _hhmm(h: tuple[int, int]) -> str:
    return f"{h[0]}:{h[1]:02d}"


def _franjas_kb() -> list[tuple[int, int]]:
    """kb["franjas"]: horas como 9 o "9:30"."""
    out = set()
    for f in kb.load_kb().get("franjas") or []:
        m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", str(f).strip())
        if m and int(m.group(1)) < 24 and int(m.group(2) or 0) < 60:
            out.add((int(m.group(1)), int(m.group(2) or 0)))
    return sorted(out)


def franjas_validas() -> list[tuple[int, int]]:
    """Franjas de la KB que caben en el horario de la KB. Son las únicas que se pueden reservar."""
    abre, cierra = kb.get_hours()
    return [f for f in _franjas_kb() if abre <= f < cierra]


def _franjas() -> str:
    """Franjas de la KB que caben en el horario, ya con 'a las' o 'entre'."""
    abre, cierra = kb.get_hours()
    validas = [_hhmm(f) for f in franjas_validas()]
    if not validas:
        return f"entre {_hhmm(abre)} y {_hhmm(cierra)}"
    if len(validas) == 1:
        return f"a las {validas[0]}"
    return "a las " + ", ".join(validas[:-1]) + f" o {validas[-1]}"


def _ahora_cali() -> datetime:
    return datetime.now(_CALI)


def _cerrado_ahora(now: datetime | None = None) -> bool:
    now = now or _ahora_cali()
    abre, cierra = kb.get_hours()
    actual = (now.hour, now.minute)
    return now.weekday() == 6 or actual < abre or actual >= cierra


def _fuera_de_horario_hoy(now: datetime | None = None) -> str:
    now = now or _ahora_cali()
    abre, cierra = kb.get_hours()
    horario = f"lunes a sábado, {_hhmm(abre)} a {_hhmm(cierra)}"
    proximo = "el lunes" if now.weekday() in (5, 6) else "mañana"
    if now.weekday() == 6:
        inicio = "Hoy es domingo y no abrimos."
    else:
        inicio = "Hoy ya no agendo: estamos fuera de horario."
    return f"{inicio} Atendemos {horario}. ¿Te sirve {proximo} {_franjas()}?"


_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
_NOMBRE_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _sin_tildes(text: str) -> str:
    return (text or "").lower().translate(str.maketrans("áéíóúüñ", "aeiouun"))


def _fecha(text: str, base: datetime) -> date | None:
    """Día pedido en el texto, contando desde 'base'. None si no nombra día."""
    t = _sin_tildes(text)
    if re.search(r"\bpasado manana\b", t):
        return base.date() + timedelta(days=2)
    if re.search(r"\bmanana\b", t):
        return base.date() + timedelta(days=1)
    if re.search(r"\bhoy\b", t):
        return base.date()
    for nombre, num in _DIAS.items():
        if re.search(rf"\b{nombre}\b", t):
            # El mismo día de la semana que hoy es el de la próxima semana; hoy se dice "hoy".
            return base.date() + timedelta(days=(num - base.weekday()) % 7 or 7)
    return None


def _hora(text: str) -> tuple[int, int] | None:
    """Hora y minuto del texto. 1 a 7 sin am/pm cuenta como tarde."""
    m = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?(?![\d/-])", _sin_tildes(text))
    if not m:
        return None
    hora, minuto = int(m.group(1)), int(m.group(2) or 0)
    suf = re.sub(r"[\s.]", "", m.group(3) or "")
    if suf == "pm" and hora < 12:
        hora += 12
    elif not suf and 1 <= hora <= 7:
        hora += 12
    if hora > 23 or minuto > 59:
        return None
    return hora, minuto


def _cuando(text: str, base: datetime) -> tuple[date, int, int] | None:
    """Fecha, hora y minuto pedidos en el texto, contando desde 'base'. None si falta algo."""
    fecha = _fecha(text, base)
    hm = _hora(text)
    if fecha is None or hm is None:
        return None
    return fecha, hm[0], hm[1]


def _texto_cuando(c: tuple[date, int, int]) -> str:
    return f"{_NOMBRE_DIA[c[0].weekday()]} {c[1]}:{c[2]:02d}"


def _creada_cali(created_at: str) -> datetime:
    try:
        utc = datetime.strptime(created_at or "", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return _ahora_cali()
    return utc.astimezone(_CALI)


def franja_de(summary: str, created_at: str) -> str:
    """'miércoles 30/09 11:00' a partir de la cita guardada; el texto tal cual si no se entiende."""
    return _franja_txt(_cuando(summary, _creada_cali(created_at)), summary)


def _franja_txt(cuando: tuple[date, int, int] | None, summary: str) -> str:
    if not cuando:
        return (summary or "")[:60]
    return f"{_NOMBRE_DIA[cuando[0].weekday()]} {cuando[0].strftime('%d/%m')} {cuando[1]}:{cuando[2]:02d}"


def _cita_at(c: tuple[date, int, int]) -> str:
    """'AAAA-MM-DD HH:MM' hora Cali (UTC-5), para la columna cita_at."""
    return f"{c[0].isoformat()} {c[1]:02d}:{c[2]:02d}"


def franja_fila(fila: dict) -> str:
    """Como franja_de, pero con cita_at si la fila lo trae."""
    return _franja_txt(cuando_fila(fila), str(fila.get("summary") or ""))


def cuando_fila(fila: dict) -> tuple[date, int, int] | None:
    """Fecha y hora de una cita guardada: cita_at si existe; si no, el cálculo de siempre desde el texto."""
    try:
        exacta = datetime.strptime(str(fila.get("cita_at") or ""), "%Y-%m-%d %H:%M")
        return exacta.date(), exacta.hour, exacta.minute
    except ValueError:
        return _cuando(str(fila.get("summary") or ""), _creada_cali(str(fila.get("created_at") or "")))


def avisos_cita(memory, ahora: datetime | None = None) -> list[tuple[dict, str]]:
    """(fila, texto) de las citas confirmadas que entraron en el plazo de 2 h o de 24 h.
    Cada aviso se marca al salir: no se repite aunque el envío falle."""
    ahora = ahora or _ahora_cali()
    salida = []
    for fila in memory.list_confirmed_reservas(500):
        c = cuando_fila(fila)
        if not c:
            continue
        cita = datetime(c[0].year, c[0].month, c[0].day, c[1], c[2], tzinfo=_CALI)
        falta = cita - ahora
        if falta <= timedelta(0) or falta > timedelta(hours=24):
            continue
        plazo = "2h" if falta <= timedelta(hours=2) else "24h"
        if memory.marcar_aviso(str(fila.get("event_id") or ""), plazo):
            dia = "hoy" if c[0] == ahora.date() else f"el {_NOMBRE_DIA[c[0].weekday()]} {c[0].strftime('%d/%m')}"
            salida.append(({**fila, "plazo": plazo}, f"Recordatorio: tu cita es {dia} a las {c[1]}:{c[2]:02d}."))
    return salida


def proxima_viva(memory, customer_id: str, ahora: datetime | None = None) -> str:
    """'martes 11:00' de la próxima cita confirmada y futura del cliente. '' si no tiene."""
    ahora = ahora or _ahora_cali()
    proxima = None
    for fila in memory.list_confirmed_reservas(500):
        if not customer_id or fila.get("customer_id") != customer_id:
            continue
        c = cuando_fila(fila)
        if c and datetime(c[0].year, c[0].month, c[0].day, c[1], c[2], tzinfo=_CALI) > ahora:
            proxima = min(proxima, c) if proxima else c
    return _texto_cuando(proxima) if proxima else ""


def cupos_de(memory, fecha: date, excepto: str = "") -> dict[tuple[int, int], dict]:
    """Franjas válidas de 'fecha' ya confirmadas, con su fila. Las citas fuera de franja no ocupan cupo."""
    validas = franjas_validas()
    tomadas: dict[tuple[int, int], dict] = {}
    for fila in memory.list_confirmed_reservas(500):
        if excepto and fila.get("customer_id") == excepto:
            continue
        otra = cuando_fila(fila)
        if otra and otra[0] == fecha and otra[1:] in validas:
            tomadas.setdefault(otra[1:], fila)
    return tomadas


def paso(fecha: date, franja: tuple[int, int], now: datetime | None = None) -> bool:
    now = now or _ahora_cali()
    return fecha < now.date() or (fecha == now.date() and franja <= (now.hour, now.minute))


def _texto_libres(libres: list[tuple[int, int]]) -> str:
    if not libres:
        return "Ese día no quedan franjas libres. ¿Probamos otro día?"
    txt = [_hhmm(f) for f in libres]
    if len(txt) == 1:
        return f"Ese día sigue libre a las {txt[0]}. ¿Te sirve?"
    return "Ese día siguen libres las " + ", ".join(txt[:-1]) + f" o {txt[-1]}. ¿Cuál te sirve?"


def _no_disponible(env: Envelope, memory) -> str:
    """'' si el texto pide una franja visible, libre y futura. Si no, qué responder."""
    now = _ahora_cali()
    fecha = _fecha(env.text or "", now)
    if fecha is None:
        return f"¿Qué día? Atendemos lunes a sábado {_franjas()}."
    if fecha.weekday() == 6:
        return "Los domingos no abrimos. Elige lunes a sábado."
    tomadas = cupos_de(memory, fecha, env.customer_id or "") if memory is not None else {}
    libres = [f for f in franjas_validas() if f not in tomadas and not paso(fecha, f, now)]
    hm = _hora(env.text or "")
    if hm is None:
        return _texto_libres(libres)
    if hm not in franjas_validas():
        return f"A las {_hhmm(hm)} no hay cita. {_texto_libres(libres)}"
    if paso(fecha, hm, now):
        return f"Esa hora ya pasó. {_texto_libres(libres)}"
    if hm in tomadas:
        return f"Ese cupo ya está tomado. {_texto_libres(libres)}"
    return ""


def _tiene_cuando(text: str) -> bool:
    t = (text or "").lower()
    if re.search(r"\b\d{1,2}([:.]\d{2})?\s*(am|pm)?\b", t):
        return True
    if re.search(
        r"\b(manana|mañana|hoy|tarde|noche|lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\b",
        t,
    ):
        return True
    return False


_HORA_CORTA = re.compile(r"^(?:a\s+)?(?:las?\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?\s*\.?$")
_OFERTA_ABIERTA = {"reserva", "reprogramar", "oferta_cita"}


def _hora_corta(env: Envelope, memory) -> str:
    """Respuesta solo con hora ('11', 'a las 11', '11:00') a una oferta abierta.
    Completa el día con el último mensaje del cliente que lo nombró.
    Devuelve '' si no aplica, o un texto para pedir el día."""
    m = _HORA_CORTA.match(_sin_tildes(env.text).strip())
    if not m or memory is None or memory.get_open_task(env.customer_id or "") not in _OFERTA_ABIERTA:
        return ""
    hoy = _ahora_cali().date()
    dia = None
    for h in memory.last_summaries(env.customer_id or "", 3):
        creada = _creada_cali(str(h.get("created_at") or ""))
        if creada.date() != hoy:
            break
        dia = _fecha(str(h.get("summary") or ""), creada)
        if dia is not None:
            break
    hora = f"{m.group(1)}:{m.group(2) or '00'}{(' ' + m.group(3)) if m.group(3) else ''}"
    if dia is None or dia < hoy:
        return f"¿Para qué día a las {hora}? Dime día y hora, por ejemplo: lunes a las {hora}."
    env.text = f"{_NOMBRE_DIA[dia.weekday()]} a las {hora}"
    return ""


def handle(env: Envelope, memory=None) -> Envelope:
    if env.intent == "mi_cita" and memory is not None:
        # Solo las del cliente, vivas: sin canceladas ni pasadas. Las que no se entienden se muestran tal cual.
        ahora = _ahora_cali()
        suyas = []
        for fila in memory.list_confirmed_reservas(500):
            if not env.customer_id or fila.get("customer_id") != env.customer_id:
                continue
            c = cuando_fila(fila)
            if c and datetime(c[0].year, c[0].month, c[0].day, c[1], c[2], tzinfo=_CALI) < ahora:
                continue
            suyas.append(f"- {_franja_txt(c, str(fila.get('summary') or ''))}")
        env.reply_text = "Tus reservas:\n" + "\n".join(reversed(suyas)) if suyas else "No tienes reserva."
        env.result = "ok"
        env.approval_status = "na"
        return env

    if not kb.agenda() and env.intent != "cancelar":
        if memory is not None:
            memory.set_open_task(env.customer_id or "", "")
        env.reply_text = SIN_AGENDA
        env.result = "ok"
        env.approval_status = "na"
        env.intent = "sin_agenda"
        return env

    pedir_dia = _hora_corta(env, memory)
    if pedir_dia:
        env.reply_text = pedir_dia
        env.result = "pending"
        env.approval_status = "pending_customer"
        return env

    bajo = (env.text or "").lower()
    if "domingo" in bajo and env.intent in {"reserva", "reprogramar"}:
        env.reply_text = "Los domingos no abrimos. Elige lunes a sábado."
        env.result = "denied"
        env.approval_status = "na"
        env.intent = "reserva_denegada"
        return env

    if "hoy" in bajo and _cerrado_ahora() and env.intent in {"reserva", "reprogramar"}:
        env.reply_text = _fuera_de_horario_hoy()
        env.result = "denied"
        env.approval_status = "na"
        env.intent = "reserva_denegada"
        return env

    if "reprogram" in bajo or "cambiar la cita" in bajo or "cambiar cita" in bajo:
        env.intent = "reprogramar"

    if env.intent == "cancelar" and memory is not None:
        baja = memory.cancel_last_reserva(env.customer_id or "")
        if baja:
            env.reply_text = f"Cancelé la cita «{baja.get('summary')}»."
            env.result = "ok"
            env.approval_status = "cancelled_customer"
            return env
        env.reply_text = "No tienes una cita confirmada para cancelar."
        env.result = "ok"
        env.approval_status = "na"
        return env

    vigente = None
    if memory is not None:
        vigente = memory.last_reserva(env.customer_id or "")

    if env.intent == "reprogramar":
        if memory is None:
            env.reply_text = "No pude tocar la agenda."
            env.result = "error"
            return env
        if not vigente:
            env.reply_text = "No tienes cita para reprogramar. ¿Agendamos una nueva?"
            env.result = "pending"
            env.approval_status = "pending_customer"
            env.intent = "reserva"
            return env
        if not _tiene_cuando(env.text or ""):
            env.reply_text = (
                f"Tienes «{vigente.get('summary')}». "
                f"¿La pasamos {_franjas()}?"
            )
            env.result = "pending"
            env.approval_status = "pending_customer"
            return env
        falta = _no_disponible(env, memory)
        if falta:
            env.reply_text = falta
            env.result = "pending"
            env.approval_status = "pending_customer"
            return env
        memory.cancel_last_reserva(env.customer_id or "")
        nueva = _cuando(env.text or "", _ahora_cali())
        env.payload["cita_at"] = _cita_at(nueva)
        env.reply_text = f"Pasé la cita a {_texto_cuando(nueva)}."
        env.result = "ok"
        env.approval_status = "confirmed_customer"
        env.intent = "reserva"
        return env

    if vigente and env.intent == "reserva":
        if _tiene_cuando(env.text or ""):
            env.reply_text = (
                f"Ya tienes «{vigente.get('summary')}». "
                f"Si quieres pasarla a «{env.text}», escribe: reprogramar la cita."
            )
        else:
            env.reply_text = (
                f"Ya tienes una cita: «{vigente.get('summary')}». "
                "No te agendo otra. Escribe cancelar la cita o reprogramar la cita."
            )
        env.result = "denied"
        env.approval_status = "na"
        env.intent = "reserva_denegada"
        return env

    if _tiene_cuando(env.text or "") and "cita" not in bajo and "reserva" not in bajo:
        falta = _no_disponible(env, memory)
        if falta:
            env.reply_text = falta
            env.result = "pending"
            env.approval_status = "pending_customer"
            return env
        nueva = _cuando(env.text or "", _ahora_cali())
        env.payload["cita_at"] = _cita_at(nueva)
        cuando = _texto_cuando(nueva)
        env.reply_text = f"Quedó tu cita: {cuando}. Para cambiar escribe cancelar la cita o reprogramar la cita."
        env.result = "ok"
        env.approval_status = "confirmed_customer"
        return env

    env.reply_text = (
        f"Puedo reservarte {_franjas()}, lunes a sábado. "
        "Dime día y hora."
    )
    env.result = "pending"
    env.approval_status = "pending_customer"
    return env