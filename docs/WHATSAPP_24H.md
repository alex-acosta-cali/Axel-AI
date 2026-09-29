# WhatsApp: ventana de 24 h

## La regla
- AXEL puede mandar **texto libre** a un número solo si esa persona le escribió hace **menos de 24 h**.
- Cada mensaje nuevo del cliente abre de nuevo la ventana de 24 h.
- Fuera de la ventana, Meta solo acepta **plantillas aprobadas** (mensaje fijo con huecos, revisado por Meta).
- Hoy AXEL solo usa `send_text` (texto libre). No tiene plantillas.

## Qué sí funciona hoy
- Responder al cliente cuando escribe: siempre está dentro de la ventana.

## Qué se cae sin plantilla
| Envío | Cuándo falla |
|-------|--------------|
| Aviso 24 h / 2 h antes de la cita | Si el cliente reservó hace más de 24 h y no ha vuelto a escribir. Pasa casi siempre con citas de varios días. |
| «Tu pedido quedó listo» | Si el dueño marca `pedido listo` más de 24 h después del último mensaje del cliente. |
| Respuesta N3 al cliente (aprobado / no se puede) | Si el dueño decide más de 24 h después del último mensaje del cliente. |
| Avisos al dueño (N3, pedido nuevo, recordatorio del día) | A veces: si el dueño no le ha escrito al 314 en las últimas 24 h. |

## Por qué no se nota en pruebas
- En pruebas se escribe seguido: la ventana siempre está abierta.
- En la vida real el fallo es silencioso: Meta devuelve error y hoy solo queda impreso en la consola del demo.

## Qué hacer (después, no en este commit)
1. Tabla de envíos con estado (enviado / falló / sin celular / fuera de 24 h). Post muro 18.
2. Elegir las plantillas mínimas: recordatorio de cita, pedido listo, respuesta N3, aviso al dueño.
3. Pedirlas a Meta solo cuando Grok y Alex lo decidan (idealmente con el VPS y la cuenta propia de Meta).
4. Mientras tanto, el dueño puede escribir al 314 una vez al día para mantener abierta su ventana.

**No se piden plantillas a Meta en este paso.**
