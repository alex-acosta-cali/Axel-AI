# AXEL: las dos puertas

AXEL tiene dos puertas de entrada. Hoy solo existe la puerta 2.

## Puerta 2 — cliente del comercio (hoy)
Quien entra: el cliente de un negocio que ya usa AXEL.

1. Escribe por WhatsApp al número del negocio.
2. AXEL lo ficha: nombre, celular, correo si lo da. Primer mensaje: aviso de datos («borrar mis datos» es N3).
3. Responde con la KB del negocio (`kb.json`): horario, precios, ubicación, políticas, FAQ.
4. Agenda solo si la KB la tiene activa: franjas, un cupo por franja, aviso 24 h y 2 h.
5. Pedido sin cobro: «me lo llevo X» anota el pedido. El dueño lo marca entregado. AXEL no cobra.
6. N3 (reembolso, queja, borrar datos): AXEL se detiene, avisa al dueño y no ejecuta. El dueño aprueba o rechaza.

Hoy: 1 negocio, 1 WhatsApp, 1 KB, 1 panel local. El dueño se reconoce por su número.

## Puerta 1 — dueño nuevo (2028, no se construye)
Quien entra: el dueño de un negocio que todavía no usa AXEL.

1. Habla con AXEL.
2. AXEL le hace un cuestionario (nombre, rubro, horario, agenda, servicios, precios, ubicación).
3. Sale una KB por negocio.
4. Cada negocio tiene su propio panel.

No se construye ahora. Hoy lo más cercano es `configurar`, que arma la KB del único negocio por chat.

## Proveedor
- Es un rol futuro dentro de AXEL (quien surte al negocio), no un canal nuevo.
- Si llega, entra por los mismos canales, con otros permisos.
- No se construye ahora.

## Qué no va en este papel
- Phone ID, tokens ni secretos: solo en `.env`.
