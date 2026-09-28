# Cuaderno AXEL — 27 sep 2026

Hito 27 sep: WhatsApp real de Colombia. Número +57 314 5801851. Phone ID 1362796690246222.
App de Meta sigue En desarrollo. Tokens solo en axel-core\.env, nunca en git.

## Hoy (27 sep)
Pruebas OK: test_memory_cross_channel y test_level3_approval.
El dueño configura nombre y horario: "configurar", "el negocio se llama X", "abrimos de 9 a 17".
Atención y reservas usan el horario de la KB. Domingo cerrado. Fuera de horario no agenda "hoy".
Franjas de cita: solo las que caben en el horario.
El cliente ya no ve plan interno ni IDs. Pitch y cuaderno: solo el dueño (panel o WA_OWNER_PHONE).
README al día: puerto 8090, demo con http.server.

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
App En producción, cobro real, servidor 24/7.

## Pendiente
Grok: un cliente podría pasar por dueño si guarda el número del dueño en su ficha (aprobar/rechazar). Hoy solo afecta canales que no son WhatsApp.
Push a GitHub de los commits del día.
