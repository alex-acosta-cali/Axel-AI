# AXEL — Módulo 1
Arquitectura técnica simplificada  
Estado: en diseño (espera aprobación)  
Fecha: 2026-09-21

Regla de este módulo: lo más simple que funcione. Un solo servicio. Un solo tenant. Model Router desde el día 1.

---

## 1. Diagrama del flujo (texto)

```
Cliente escribe (WhatsApp / IG / Web / Email / Voz)
        |
        v
[Conector del canal]
  - verifica firma del webhook
  - responde 200 al proveedor
  - normaliza al SOBRE INTERNO
        |
        v
[Cola liviana]  (en v1: la misma app, job en background)
        |
        v
[Orquestador]
  1. Identificar customer_id (CRM / memoria)
  2. Cargar contexto minimo
       - perfil del negocio
       - extracto KB
       - ficha + ultimos resumenes
       - sesion abierta (si hay)
  3. Clasificar intencion
  4. Elegir AGENTE
  5. Consultar PERMISOS  -> nivel 1 / 2 / 3
  6. Pedir MODEL ROUTER  -> modelo + fallback
  7. Ejecutar agente (herramientas: KB, CRM, agenda, etc.)
  8. Si nivel 2: pedir SI al cliente y PAUSAR
     Si nivel 3: notificar al dueno y PAUSAR
  9. Enviar respuesta por el mismo canal
 10. Escribir AUDITORIA + actualizar memoria
        |
        v
Fin del evento
```

Si el modelo principal falla (timeout, 429, basura):
```
Model Router cambia en caliente al fallback -> reintenta 1 vez
Si falla otra vez -> respuesta segura + alerta al dueno + log error
```

### Sobre interno (v1)

```json
{
  "event_id": "evt_01",
  "received_at": "2026-09-21T08:00:00-05:00",
  "channel": "whatsapp",
  "direction": "in",
  "channel_user_id": "57300...",
  "customer_id": null,
  "business_id": "biz_default",
  "intent": null,
  "agent": null,
  "supervision_level": 1,
  "model": null,
  "text": "Quiero una cita manana",
  "context_refs": [],
  "result": null
}
```

---

## 2. Componentes y tecnologías (barato para empezar)

### Lo que SÍ construimos en v1 (un solo proceso)

| Pieza | Qué es | Tech recomendada | Costo inicio |
|-------|--------|------------------|--------------|
| API HTTP | Webhooks + /health + admin minimo | Python + FastAPI + Uvicorn | $0 |
| App unica | Orquestador + agentes + router + permisos | Mismos archivos Python (paquetes, no microservicios) | $0 |
| Base de datos | Clientes, resumenes, sesiones, reservas, facturas, audit_events, kb | PostgreSQL en Supabase (free) o SQLite si aun no hay cuenta | $0 |
| Archivos / secretos | Tokens Meta, API keys | `.env` + variables del host | $0 |
| Contenedor | Correr 24/7 con restart | Docker Compose | $0 |
| Host | 1 mini VPS | Hetzner CX22 / Railway trial / un VPS de $4-6 | ~$5/mes |
| HTTPS | Webhooks de Meta exigen TLS | Caddy o Nginx + Let's Encrypt (o el TLS del PaaS) | $0 |
| Modelos | Grok + 1 fallback | xAI API + OpenAI o Anthropic | pago por uso |

### Servicios externos (solo cuando el canal se active)

| Canal | Servicio | Nota |
|-------|----------|------|
| WhatsApp | Meta Cloud API | Prioridad 1 para piloto |
| Instagram / Messenger | Graph API | Despues de WA |
| Web | Endpoint propio `/webhooks/web` | Widget simple despues |
| Email | Gmail API | Despues |
| Voz | Twilio (u otro) | Lo ultimo |

### Lo que NO es un microservicio en v1

No separamos:
- orquestador
- model router
- permisos
- auditoria
- memoria

Son **módulos de código** dentro del mismo FastAPI.

```
axel/
  main.py              # FastAPI, /health, webhooks
  envelope.py          # sobre interno
  orchestrator.py      # flujo de la seccion 1
  router_model.py      # elige modelo + fallback
  permissions.py       # nivel 1/2/3
  agents/              # sales, reservas, atencion...
  memory.py            # lee/escribe DB
  audit.py             # escribe audit_events
  connectors/whatsapp.py
  tools/               # kb_lookup, crm_get, slot_search
```

### Model Router (desde el diseño, no “después”)

Función, no servicio:

```
route(task_type, quality, latency_max, budget) -> {model, fallback, reason}
```

Default v1:
- Clasificar intención / FAQ: modelo rápido/barato (Grok fast o similar)
- Venta, queja, política ambigua: modelo estándar
- Fallback: segundo proveedor
- Registrar modelo y costo estimado en audit_events

---

## 3. Qué construimos primero y qué dejamos para después

### Primero (Módulo 1 cerrado + piloto mínimo)

1. Repo + Docker Compose + `/health`
2. Tabla `audit_events` + `customers` + `conversation_summaries` + `session_state`
3. Webhook WhatsApp (verificar + normalizar + 200)
4. Orquestador v1 con 2 agentes: **atención** y **reservas** (el resto responde “te paso con el dueño”)
5. Model Router v1 (2 modelos)
6. Permisos v1 (si es reserva → nivel 2; si es queja → nivel 3)
7. Respuesta de vuelta por WhatsApp
8. Log de cada evento

Con eso AXEL ya “vive”: entra un mensaje, piensa, responde, recuerda, registra.

### Después (no bloquear M1)

- Instagram, web, email, voz
- Ventas / facturación / marketing / postventa
- Cola Redis / workers separados
- Multi-tenant
- Dashboard
- Kubernetes
- Evaluación automática de calidad del modelo
- Botones interactivos avanzados de WhatsApp
- Reportes diarios automáticos

---

## 4. Criterios de aceptación del Módulo 1

M1 se aprueba cuando exista un diseño (este documento) que el dueño acepte y que cumpla:

- [ ] El flujo de un mensaje está descrito paso a paso, sin cajas mágicas
- [ ] Hay un solo servicio de aplicación (no sopa de microservicios)
- [ ] El Model Router está en el flujo, no como idea futura
- [ ] La lista de tech es gratuita o barata y se puede montar en un VPS
- [ ] Está claro el piloto: WhatsApp + atención + reservas
- [ ] Está escrito qué NO se construye ahora
- [ ] Los secretos no viven en el código
- [ ] Cada evento termina en un registro de auditoría

Criterios de *construcción* (siguiente módulo, no este):
- Eso se prueba cuando escribamos código. Este M1 solo aprueba el plano.

---

## Decisiones de M1 (propuestas)

1. Python + FastAPI + Docker Compose
2. Postgres (Supabase free) ; SQLite solo para demo local de un día
3. Un tenant `biz_default`
4. Piloto por WhatsApp
5. Model Router como módulo interno
6. Sin Redis en v1

Si apruebas M1, el siguiente módulo de implementación es: **esqueleto del servicio + webhook WhatsApp + orquestador hueco + audit log**.
