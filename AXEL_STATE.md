# AXEL_STATE.md
Documento maestro de AXEL AI OS  
Última actualización: 2026-09-21 05:37 -05  
Dueño: Alex Acosta (Cali)  
Arquitecto: Super Grok  
Ejecutor PC (opcional): Claude Code  

Regla de cambio:
- La sección 1 solo cambia con aprobación explícita del dueño.
- El resto se actualiza al cierre de sesión.

---

## 1. Visión y arquitectura de AXEL

### Visión
AXEL AI OS es una plataforma de agentes de IA que opera un negocio completo:

- Atiende por WhatsApp, Instagram, Messenger, web, email y voz.
- Memoria y contexto por cliente.
- Agenda, vende, factura, cobra, fideliza y hace marketing.
- Supervisión humana en acciones sensibles.
- Trazabilidad de cada acción.

Objetivo cercano: un comercio piloto. Objetivo lejano: el mismo núcleo configurable para varios rubros.

### Principios (aprobados)
1. Mensaje → orquestador → agente → ejecución → registro.
2. No inventar precios, stock, políticas ni datos de cliente.
3. Tres niveles: automático / confirmación cliente / aprobación dueño.
4. Canales solo con APIs oficiales.
5. Secretos fuera del código.
6. Lo más simple que funcione 24/7.
7. Si no está en el log, no ocurrió.
8. Módulo por módulo. No avanzar sin aprobación.
9. El código de producción vive en el PC/GitHub del dueño, no solo en un chat.

### Arquitectura lógica (aprobada)
Canal → conector → orquestador → permisos + model router → agente → memoria/CRM/KB → auditoría → respuesta.

Un tenant por ahora (`biz_default`). Un proceso de aplicación (Python).

---

## 2. Módulos y estado

Leyenda: pendiente | en diseño | construido (sandbox Grok) | verificado en PC | aprobado

| ID | Módulo | Estado |
|----|--------|--------|
| M00 | Fundación | aprobado |
| M01 | Arquitectura técnica | aprobado (implícito al pedir M2) |
| M02 | Núcleo orquestador + router | construido + prueba OK en sandbox Grok. Falta verificar en PC |
| M03 | Memoria / identidad entre canales | construido + prueba OK en sandbox. Falta PC |
| M04 | Niveles + auditoría + aviso dueño | construido + prueba OK en sandbox. Falta PC |
| M05 | WhatsApp oficial + atención KB | código + guía listos. Falta cuenta Meta + HTTPS + prueba con el celular de Alex |
| M10-M21 | Producto resto | pendiente |
| M22-M29 | Plataforma resto | diseño en skills; infra real pendiente |

---

## 3. Decisiones técnicas

| Decisión | Por qué |
|----------|---------|
| Grok lidera arquitectura; GPT Plus no es obligatorio | Alex ya tiene Super Grok; evita doble pago de arquitecto |
| Claude Code solo ejecuta en PC si existe | No rediseña |
| Python + FastAPI/demo + SQLite local | Más simple para v1 |
| Postgres/Supabase cuando salga del PC | Gestionado y barato |
| WhatsApp Cloud API oficial | Menos riesgo de ban |
| Identidad entre canales por teléfono/email | No fusionar a ciegas por nombre |
| Nivel 3 no ejecuta | Reembolsos y quejas no son automáticos |
| Código canónico mañana: `C:\Proyectos\Axel-AI` | Lugar físico controlado por Alex |

Pendiente de decidir: VPS, proveedor de voz, presupuesto de tokens, descuento máximo.

---

## 4. Dónde está el trabajo HOY

Sandbox Grok (no es tu PC):
- `/home/workdir/artifacts/axel-core/`
- `/home/workdir/artifacts/AXEL_STATE.md`
- `/home/workdir/artifacts/AXEL_M01_Arquitectura.md`
- `/home/workdir/artifacts/AXEL_M05_WhatsApp.md`
- `/home/workdir/artifacts/AXEL_PLAN_GROK.md`
- `/home/workdir/artifacts/CLAUDE.md`
- `/home/workdir/artifacts/AXEL_core_y_docs.zip`

Pruebas que Grok ejecutó aquí:
- M2: cita → reservas nivel 2 + audit
- M3: mismo customer_id WhatsApp + Instagram
- M4: reembolso → pending_owner + alerta
- M5 interno: parse WA + FAQ horario desde kb.json

---

## 5. Pendientes y riesgos

- Copiar zip al PC y repetir tests
- Repo GitHub privado
- Verificación Meta / WABA (puede tardar días)
- HTTPS público (ngrok o VPS) para webhook
- Token permanente de system user (después del piloto)
- No hay bugs de runtime en producción porque aún no hay producción en el PC

---

## 6. Criterios del bloque actual (PC-1)

Mañana se da por bueno cuando:
- [ ] Existe `C:\Proyectos\Axel-AI\axel-core\`
- [ ] `test_memory_cross_channel.py` imprime OK en el PC
- [ ] `test_level3_approval.py` imprime OK en el PC
- [ ] Primer commit en Git (sin `.env`)
- [ ] Alex pega las salidas en el chat de Grok

WhatsApp real es extra del mismo día o Día 2. No bloquea PC-1.

---

## Bitácora

- 2026-09-21 — 29 skills. M00-M01 docs. M02-M04 código + tests en sandbox. M05 conector + guía Meta.
- 2026-09-21 noche — Alex aclara que el plan GPT/Claude era otro hilo. Nuevo plan: Grok lidera, sin GPT Plus obligatorio. Código aún no está en el PC de Alex.
- Próxima sesión: “Estoy frente al PC. Día 1.”
