# Puerta phone — papel

Solo papel. Sin código.

## La regla
Cada mensaje de Meta trae el `phone_number_id` del número que lo recibió.
Ese `phone_number_id` apunta a un `business_id`.
Un número de WhatsApp = un negocio.

## Hoy
- Un solo número, en `.env` (`WA_PHONE_NUMBER_ID`).
- Todo es `biz_default`.
- Clientes, citas y pedidos ya tienen `business_id`.
- El webhook no mira el `phone_number_id` que llega.

## Cuando se haga (no ahora)
- Una tabla `phone_number_id → business_id`.
- Número desconocido: no se responde. Queda en el log.
- La respuesta sale por el mismo número que recibió el mensaje.
- Se hace solo cuando Alex lo apruebe con Grok.

## Antes
- Meta a la cuenta de Alex: octubre, después de la Ley 1581. No esta semana.

## No hay
- Segundo número.
- Cobro.
- Instagram.
