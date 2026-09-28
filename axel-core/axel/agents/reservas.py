from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from axel import knowledge_base as kb
from axel.envelope import Envelope

_CALI = timezone(timedelta(hours=-5))
FRANJAS_PILOTO = [(9, 0), (11, 0), (15, 0), (17, 0)]


def _hhmm(h: tuple[int, int]) -> str:
    return f"{h[0]}:{h[1]:02d}"


def _franjas() -> str:
    """Franjas piloto que caben en el horario de la KB, ya con 'a las' o 'entre'."""
    abre, cierra = kb.get_hours()
    validas = [_hhmm(f) for f in FRANJAS_PILOTO if abre <= f < cierra]
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
    return (text or "").lower().translate(str.maketrans("áéíóúü", "aeiouu"))


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
            return base.date() + timedelta(days=(num - base.weekday()) % 7)
    return None


def _dia_hora(text: str, base: datetime) -> tuple[str, int] | None:
    """Fecha (ISO) y hora pedidas en el texto, contando desde 'base'. None si falta algo."""
    t = _sin_tildes(text)
    fecha = _fecha(text, base)
    m = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?(?![\d/-])", t)
    if fecha is None or not m:
        return None
    hora = int(m.group(1))
    suf = re.sub(r"[\s.]", "", m.group(3) or "")
    if suf == "pm" and hora < 12:
        hora += 12
    elif not suf and 1 <= hora <= 7:
        hora += 12
    if hora > 23:
        return None
    return fecha.isoformat(), hora


def _creada_cali(created_at: str) -> datetime:
    try:
        utc = datetime.strptime(created_at or "", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return _ahora_cali()
    return utc.astimezone(_CALI)


def _ocupadas(memory, customer_id: str, fecha: str) -> set[int]:
    """Horas de 'fecha' ya confirmadas por otros clientes."""
    horas = set()
    for fila in memory.list_confirmed_reservas(500):
        if fila.get("customer_id") == customer_id:
            continue
        otra = _dia_hora(str(fila.get("summary") or ""), _creada_cali(str(fila.get("created_at") or "")))
        if otra and otra[0] == fecha:
            horas.add(otra[1])
    return horas


def _cupo_tomado(env: Envelope, memory) -> str:
    """Texto de 'ocupado' si otro cliente ya tiene ese día y hora; '' si está libre."""
    if memory is None:
        return ""
    pedida = _dia_hora(env.text or "", _ahora_cali())
    if not pedida:
        return ""
    ocupadas = _ocupadas(memory, env.customer_id or "", pedida[0])
    if pedida[1] not in ocupadas:
        return ""
    abre, cierra = kb.get_hours()
    libres = [_hhmm(f) for f in FRANJAS_PILOTO if abre <= f < cierra and f[0] not in ocupadas]
    if not libres:
        return "Ese cupo ya está tomado y ese día no quedan franjas libres. ¿Probamos otro día?"
    if len(libres) == 1:
        return f"Ese cupo ya está tomado. Ese día sigue libre a las {libres[0]}. ¿Te sirve?"
    opciones = ", ".join(libres[:-1]) + f" o {libres[-1]}"
    return f"Ese cupo ya está tomado. Ese día siguen libres las {opciones}. ¿Cuál te sirve?"


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
        fila = memory.last_reserva(env.customer_id or "")
        if fila:
            env.reply_text = f"Tu cita confirmada es: «{fila.get('summary')}»."
        else:
            env.reply_text = "No tienes una cita confirmada ahora."
        env.result = "ok"
        env.approval_status = "na"
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
        tomado = _cupo_tomado(env, memory)
        if tomado:
            env.reply_text = tomado
            env.result = "pending"
            env.approval_status = "pending_customer"
            return env
        memory.cancel_last_reserva(env.customer_id or "")
        nueva = _dia_hora(env.text or "", _ahora_cali())
        if nueva:
            dia = _NOMBRE_DIA[datetime.fromisoformat(nueva[0]).weekday()]
            mm = re.search(r"\b\d{1,2}[:.](\d{2})\b", env.text or "")
            env.reply_text = f"Pasé la cita a {dia} {nueva[1]}:{mm.group(1) if mm else '00'}."
        else:
            env.reply_text = f"Pasé la cita a «{env.text}»."
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
        tomado = _cupo_tomado(env, memory)
        if tomado:
            env.reply_text = tomado
            env.result = "pending"
            env.approval_status = "pending_customer"
            return env
        env.reply_text = (
            f"Quedó anotada la reserva para «{env.text}». "
            "En el piloto no hay agenda real todavía; el cupo queda como confirmado de prueba."
        )
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