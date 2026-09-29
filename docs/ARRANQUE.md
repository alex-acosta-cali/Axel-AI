# Arranque AXEL (PC local)

Tres accesos en el escritorio, en este orden:

1. **AXEL demo**: levanta el demo (`axel-core\scripts\levantar.ps1`, venv + `python -m axel.demo`).
   Panel: http://127.0.0.1:8090/
2. **AXEL ngrok**: `ngrok http 8090`. Copia la URL `https://....ngrok-free.app` que muestra.
3. **AXEL Claude**: abre Claude Code en `C:\Proyectos\Axel-AI`.

Deja abiertas las ventanas de demo y ngrok. Si cierras una, el 314 deja de responder.

## Webhook en Meta
- URL de devolución: URL de ngrok + `/webhooks/whatsapp`
  (ejemplo: `https://....ngrok-free.app/webhooks/whatsapp`).
- Token de verificación: `axel-verify`.
- Si ngrok cambia de URL (al reiniciarlo), hay que volver a pegarla en Meta.

## Prueba
- Desde un celular tester, escribe `horario` al WhatsApp del negocio (314).
- Debe responder el horario y si está abierto o cerrado (hora Cali).
- Si no responde: mira la ventana del demo (errores) y la de ngrok (llegan POST).

## No hacer
- No imprimir ni pegar el `.env` (tokens y Phone ID). No subirlo a GitHub.
- No pulsar Meta producción.
