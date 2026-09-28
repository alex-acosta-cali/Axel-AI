# Modelo de lenguaje (regla)

## Regla
- Plata, reembolso, descuentos y aprobar/rechazar: **listas y reglas fijas** en código. Nunca el modelo.
- El modelo solo **redacta** saludos y respuestas de FAQ.
- El modelo no decide, no aprueba y no cambia precios, citas ni pendientes.

## Cómo está hoy (`axel/router_model.py`)
- `route()` **no llama a ningún proveedor**. Solo devuelve un nombre de modelo y un motivo.
- El orquestador guarda ese nombre en `env.model` y en la auditoría. Es solo una etiqueta.
- Nombres por `.env`: `MODEL_FAST`, `MODEL_STANDARD`, `MODEL_FALLBACK`. Sin claves en el código.
- Las respuestas de hoy salen de plantillas, la KB y las reglas de `permissions.py`.

## Ojo
- `TASK_MATRIX` pone nombre de modelo también a `reembolso`, `queja`, `venta`, `reserva` y `admin`.
  Hoy no pasa nada, porque nada se llama. Cuando se enchufe un modelo, solo `saludo` y `pregunta` pueden usarlo.
- El respaldo por defecto es de otro proveedor (`gpt-4.1-mini`). Elegir proveedor se consulta con Grok.

## Niveles (`axel/permissions.py`)
- Nivel 1: automático (saludo, pregunta, datos).
- Nivel 2: el cliente confirma (reserva, reprogramar, cancelar).
- Nivel 3: solo el dueño (queja, reembolso, descuento grande). Axel no ejecuta.

## Reglas
- No llamar APIs de pago sin aprobación de Alex.
- Claves solo en `.env`. Nunca en git.
