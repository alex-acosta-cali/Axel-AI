# Panel del dueño

El panel corre en el VPS, solo en `127.0.0.1:8090`. No tiene login y no se publica.

## Cómo verlo

Desde el PC del dueño, abre un túnel SSH al VPS:

```
ssh -L 8090:127.0.0.1:8090 <usuario>@<servidor>
```

Deja esa ventana abierta y entra en Chrome a http://127.0.0.1:8090/

Al cerrar la ventana del SSH, el panel deja de verse.

## Desde el dominio: 403

Por el dominio del VPS solo pasan `/webhooks/whatsapp` y `GET /health`.
El panel, `/panel`, `/audit` y `/decidir` responden 403 `solo_local`.

Falta la prueba real: abrir el dominio desde el celular sin wifi y ver el 403.

## Bloques

- Reporte de hoy
- Envíos (últimas 8 filas, sin texto ni celular entero)
- Clientes WhatsApp
- Pendientes
- Clientes
- Pedidos
- Catálogo
- Cupos de la semana
- Citas
- Últimos

## Después

El diseño (logo, colores) va después. Hoy el panel es funcional, no de marca.
