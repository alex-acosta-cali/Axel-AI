# Cuaderno AXEL — 26 sep 2026

Hito: AXEL respondio por WhatsApp de prueba (Cloud API).

## LEVANTAR AXEL
Demo:
Set-Location C:\Proyectos\Axel-AI\axel-core
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python -m axel.demo
Bien: ENV token= True y Webhook WhatsApp.

Ngrok (otra ventana): ngrok http 8090
Webhook: https://LA-URL-NGROK/webhooks/whatsapp
Verify: axel-verify
Campo: WhatsApp Business Account -> messages Suscrito.

.env en axel-core\.env — NUNCA a GitHub.

## IDs Meta (prueba, cuenta del hijo)
App: Axel AI OS piloto
App ID: 1757107295343375
Business ID: 1112991918054759
Phone Number ID: 1337796982749616
WABA: 1095434866790545
Numero test: +1 555 189 7197

Token EAA de Paso 1 caduca ~24 h. Siguiente: token de usuario del sistema (gratis).

## Ya hace
Panel 8090, CRM, citas, N1/N2/N3, KB, WhatsApp entra y sale.

## No es
Numero real, cobro real, app En produccion, cuenta Meta definitiva.
