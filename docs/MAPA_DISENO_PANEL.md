# Mapa: diseño → panel vivo

Fecha: 2026-10-02. Solo lectura. No hay código en este archivo.
Fuente del aspecto: `axel desing.pdf` (es igual al lienzo de Claude).
Fuente de los datos: `axel-core/axel/demo.py`, `memory.py`, `orchestrator.py` y `kb.json`.
Reglas: las decide Grok. Están en la conversación del 2026-10-02.

---

## Barra de arriba (todas las puertas)

| Pieza | Ya existe | Falta |
|---|---|---|
| Λ AXEL | El texto "ΛXEL" en `<h1>` (la prueba lo exige) | El dibujo de la Λ en dorado. Es solo aspecto. |
| Nombre del negocio | `kb["negocio"]` | — |
| Hora de Cali | `_ahora_cali()` | — |
| Buscar | — | No va. No hay búsqueda con modelo. |

## Puerta 1: Día

| Pieza | Ya existe | Falta |
|---|---|---|
| Número grande = citas de hoy | `list_confirmed_reservas` + `cuando_fila` con fecha de hoy (igual que `_reporte`) | — |
| Debajo: "Anotado hoy, sin cobro $N" | Suma de `precio` de los pedidos creados hoy (igual que `_reporte`) | — |
| Tarjeta citas | El mismo número | — |
| Tarjeta pedidos en curso | `list_pedidos` con estado distinto de entregado y rechazado | — |
| Tarjeta por aprobar | `len(list_pending())` | — |
| Próximas citas: hora y nombre | `cuando_fila` y `name` | — |
| Próximas citas: servicio | — | La cita no guarda el servicio. `summary` es texto libre. No se pinta. |
| Próximas citas: "por confirmar" | — | Solo existen citas `ok`. Ese estado no existe. No se pinta. |
| Pedidos: nombre, qué, precio, estado | `pedidos_filas` | — |
| Vacío | — | Textos de Grok: "Hoy no hay pedidos." y, para citas, el texto que Grok indique. |
| Selector Ayer/Semana/Mes | — | No va. |

**Ventana Citas** (se abre al tocar):

| Pieza | Ya existe | Falta |
|---|---|---|
| Lista de hoy | Ver Día | — |
| Cupos de la semana (libre, tomada, pasó) | `_tabla_cupos()` | — |
| Fuera de franja | `_fuera_de_franja()` | — |
| Franjas | `kb["franjas"]`, las pone el dueño | — |

**Ventana Pedidos** (se abre al tocar):

| Pieza | Ya existe | Falta |
|---|---|---|
| Últimos 15 | `pedidos_filas` | — |
| Estados | anotado, por verificar, pagado, en camino, entregado y rechazado (`ESTADOS_PEDIDO`) | — |
| Total arriba | Suma de hoy | Dice "Anotado", nunca "Confirmados". |
| Ligar el pedido a la cita | — | No va en este paso. Se muestran aparte. |

## Puerta 2: Conversaciones

| Pieza | Ya existe | Falta |
|---|---|---|
| Fila: nombre, hora, último texto | `list_audit`: `received_at`, `customer_id` → `get_customer`, `input_summary` / `output_summary` | Una fila por cliente. Hoy hay una fila por evento. Hay que agrupar al leer. |
| Canal | `audit.channel` | Solo se muestra WhatsApp como vivo. "panel" y "test" son internos. |
| Punto pendiente (dorado) | Se puede sacar de `list_pending` o de un pedido abierto del cliente | Falta que Grok defina qué cuenta como pendiente. |
| Punto urgente (rojo) | — | Falta la regla. El diseño dice "más de 2 h sin tu respuesta", pero AXEL ya responde solo. Mientras no haya regla, no se pinta. |
| Vacío | — | "Al día. Nadie espera." |
| Envíos | Hoy están aquí | Pasan a la puerta Registro. |
| Clientes WhatsApp y Clientes | Hoy están aquí | Pasan a la ventana Clientes. |
| Ficha panel y "Escribe a AXEL" | Hoy están aquí | Ver la pregunta 3. |

**Ventana Hilo** (al tocar una fila):

| Pieza | Ya existe | Falta |
|---|---|---|
| Mensajes entrantes y salientes | La tabla `messages` (dirección, texto, canal, hora) | No hay función que los lea por cliente. Falta una lectura pequeña. |
| "Enviar al canal" | — | No va. |

## Puerta 3: Aprobaciones

| Pieza | Ya existe | Falta |
|---|---|---|
| Nombre | `pending.customer_id` → `get_customer` | — |
| "AXEL dice: …" | `why`, `requested_action` | — |
| Botones sí/no | — | Visibles y apagados, con el texto "Se aprueba por WhatsApp". |
| Vacío | — | "Nada por aprobar." |
| Chat | Abre el Hilo de ese cliente | Depende de la lectura del Hilo. |

## Ventana Clientes

| Pieza | Ya existe | Falta |
|---|---|---|
| Una sola lista | `list_customers` | — |
| Canal al lado | `identities.channel` | No hay función que traiga el canal de cada cliente. Falta una lectura. |
| Última vez | `list_whatsapp_customers.last_in` | — |
| Último pedido o "sin compras" | `last_pedido` | — |
| Celular | Está en `customers.phone` | El diseño no lo muestra y hoy el panel sí. Ver la pregunta 4. |

## Ventana Mi negocio

| Pieza | Ya existe | Falta |
|---|---|---|
| Nombre, rubro, agenda sí/no, tono | `kb` | — |
| Horario | `get_hours()`: una sola apertura y un solo cierre | El diseño muestra el horario por día. Ese dato no existe. Se pinta una sola línea. |
| Domingo cerrado | Está fijo en el código de cupos | No está en la base de conocimiento. |
| Franjas | `kb["franjas"]` | — |
| Dirección | `kb["ubicacion"]` | — |
| Servicios y precios | `kb.servicios()` | — |
| Productos: código, stock, disponible | `inventario_filas` | — |
| Políticas | `kb["politicas"]` | — |

## Puerta Registro (operador)

| Pieza | Ya existe | Falta |
|---|---|---|
| Envíos (8) | `_tabla_envios()` | — |
| Eventos técnicos (agente, nivel) | `list_audit` | — |
| Ficha panel | Sí | — |

## Quiénes somos y Marca

Son textos fijos. No usan datos. Aquí van el pin y "desde 2016".
El texto del PDF dice "Atiende el WhatsApp". Eso es cierto hoy.

---

## Choques con las pruebas (`tests/test_panel_envios.py`)

1. **Línea 63.** La prueba exige este orden: "Reporte de hoy", luego "Envíos" y luego "Clientes WhatsApp". Si Envíos pasa a Registro y Clientes a su ventana, el orden cambia.
2. **Línea 65.** Exige siete `<h2>`: Reporte de hoy, Cupos de la semana, Citas, Clientes WhatsApp, Catálogo, Pedidos y Envíos. Si "Catálogo" pasa a llamarse "Mi negocio", la prueba falla.
3. **Línea 87.** Exige este orden: ΛXEL, `id="dia"`, `id="conversaciones"`, `id="aprobaciones"` y por último `id="inventario"`. Registro y Mi negocio tienen que quedar después, o la prueba cambia.
4. **Línea 93.** Exige que "Últimos" esté dentro de Conversaciones. Si los eventos técnicos pasan a Registro, falla.

Los cuatro choques se arreglan cambiando la prueba a propósito. Grok debe aprobarlo antes de pintar.

## Preguntas para Grok

1. **`/decidir` está encendido hoy.** El panel actual tiene botones Aprobar y Rechazar que llaman a `resolve_pending`. Eso contradice "visibles y apagados". ¿Se apaga en el mismo paso de pintar o en uno aparte?
2. **Puntos de Conversaciones.** ¿Qué es "pendiente"? ¿Qué es "urgente"? Sin regla no se pintan.
3. **"Escribe a AXEL" (POST `/panel`).** El diseño no lo tiene. ¿Va a Registro o se quita de la vista?
4. **Celular en Clientes.** ¿Se muestra completo, solo las últimas 4 cifras o no se muestra?
5. **Inventario.** ¿Va dentro de Mi negocio, en Productos, y el `id="inventario"` se queda ahí?
6. **Pruebas.** ¿Se autoriza ajustar los cuatro choques de arriba?
7. **Hilo y Clientes.** Necesitan dos lecturas nuevas en `memory.py`: mensajes por cliente y canal por cliente. Solo leen, no escriben. ¿Se aprueban?
