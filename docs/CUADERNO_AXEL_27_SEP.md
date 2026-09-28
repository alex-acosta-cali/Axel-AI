# Cuaderno AXEL — 27 y 28 sep 2026

WhatsApp del negocio: +57 314 5801851. App de Meta sigue En desarrollo. Tokens solo en axel-core\.env, nunca en git.

## Hoy (28 sep)
Un cupo confirmado por franja: si otro cliente ya tiene ese día y hora, no se guarda y AXEL dice qué franja sigue libre. Probado.
Cancelar y reprogramar sueltan el cupo viejo. Si la franja nueva está tomada, la cita vieja no se borra.
Hora corta ("11", "a las 11") confirma la franja ofrecida.
Panel: tabla de cupos de la semana, LIBRE o TOMADA.
Reembolso N3: el dueño aprueba y el cliente recibe el aviso. Probado con un segundo celular.
Aprobar, rechazar y comandos del dueño: solo WA_OWNER_PHONE o el panel. Nunca Instagram ni otro número.
Hosting 24/7, Instagram y modelo de lenguaje: solo notas en docs. No están construidos.

## 27 sep
WhatsApp real de Colombia conectado por ngrok.
El dueño configura nombre y horario: "configurar", "el negocio se llama X", "abrimos de 9 a 17".
Atención y reservas usan el horario de la KB. Domingo cerrado. Fuera de horario no agenda "hoy".
Franjas de cita: solo las que caben en el horario.
El cliente ya no ve plan interno ni IDs. Pitch y cuaderno: solo el dueño (panel o WA_OWNER_PHONE).

## LEVANTAR
scripts\levantar.ps1
O a mano:
Set-Location C:\Proyectos\Axel-AI\axel-core
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python -m axel.demo
Ngrok (otra ventana): ngrok http 8090
Webhook: https://LA-URL-NGROK/webhooks/whatsapp
Verify: el valor de WA_VERIFY_TOKEN en .env.
Campo: WhatsApp Business Account -> messages Suscrito.

## Comandos del dueño
estado, pendientes, citas, limpiar, aprobar, rechazar, ayuda, configurar.

## No es
App En producción, cobro real, servidor 24/7, Instagram, modelo de lenguaje conectado.

## Pendiente
Push a GitHub de los commits del día.
Hosting 24/7 en VPS (ver docs/HOSTING_24_7.md).
