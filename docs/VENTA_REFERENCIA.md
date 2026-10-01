# Venta por referencia — papel

Solo papel. No toca código.

## Entrada
El cliente manda foto o código.

## Si está en el inventario del dueño
- AXEL dice precio de venta, stock y si hay entrega hoy.
- Sigue el pedido.

## Si no está
- AXEL no inventa precio.
- Pregunta por WhatsApp al contacto que el dueño configuró:
  - ¿Tienes esta referencia?
  - ¿Entrega hoy o en cuántos días?
- No le manda el precio del cliente.
- La respuesta vuelve al dueño.
- El dueño ve costo y plazo. Él pone el precio de venta.

## Lo que nadie ve
- El cliente no ve el costo del proveedor.
- El proveedor no ve el precio del cliente.

## El sí del dueño
- Sin el sí del dueño no hay venta.
- Con el sí, AXEL confirma precio y plazo al cliente.
- Nace el pedido `anotado`. Sigue el comprobante.

## Estados del pedido
1. `anotado`
2. `por verificar`
3. `pagado`
4. `en camino`
5. `entregado`

Aparte: `rechazado`.

## No hay
- Billetera.
- AXEL mirando el banco.
