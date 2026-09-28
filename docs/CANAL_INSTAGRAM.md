# Canal Instagram (pendiente)

Todavía no existe `connectors/instagram.py`. Esto es la nota antes de escribirlo.

## La verdad corta
- **Misma app Meta** que WhatsApp. No hace falta otra app.
- **Otro webhook.** Hay que suscribir el objeto `instagram` (campo `messages`), aparte del de WhatsApp. Ruta sugerida: `POST /webhooks/instagram`, en el mismo proceso `axel.demo`.
- **Otro parseo.** El JSON no se parece al de WhatsApp:
  - WhatsApp: `entry[].changes[].value.messages[]`, trae el número del cliente.
  - Instagram: `entry[].messaging[]`, trae `sender.id` (un ID de Instagram), **sin teléfono**.
- **Otro envío.** Se responde por la Graph API de mensajes de Instagram, con su propio token. No sirve `whatsapp.send_text`.

## Requisitos
- Cuenta de Instagram profesional (empresa o creador), conectada a la app Meta.
- Permiso de mensajes de Instagram. Para clientes reales, Meta pide revisión de la app.
- Solo se puede responder dentro de la ventana de 24 h desde el último mensaje del cliente.

## Qué cambia en Axel
- El cliente de Instagram entra con `channel="instagram"` y `channel_user_id=<sender.id>`.
- Solo se une con su ficha de WhatsApp si da su celular en el chat.
- Instagram **nunca** es dueño. Aprobar y rechazar siguen siendo solo del WhatsApp del dueño o del panel.

## Reglas
- Tokens solo en `.env`. Nunca en git.
- Sin dependencias nuevas.
