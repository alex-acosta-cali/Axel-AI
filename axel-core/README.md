# AXEL Core — demo local

Núcleo local: orquestador + model router + memoria SQLite + auditoría + conector WhatsApp.

El demo es un servidor mínimo con `http.server` de Python (sin FastAPI).
Escucha en `http://127.0.0.1:8090`.

## Estructura

```
axel-core/
  requirements.txt
  .env.example
  README.md
  axel/
    demo.py            <- servidor que se usa (http.server, puerto 8090)
    main.py            <- versión FastAPI antigua, no es la que se arranca
    envelope.py
    orchestrator.py
    router_model.py
    permissions.py
    memory.py
    knowledge_base.py
    notify.py
    agents/
      atencion.py
      reservas.py
      escalamiento.py
    connectors/
      whatsapp.py
  scripts/
    levantar.ps1
    enviar_prueba.ps1
    enviar_reembolso.ps1
  tests/
    test_memory_cross_channel.py
    test_level3_approval.py
    test_message.py
```

## Instalar (una vez)

```powershell
cd C:\Proyectos\Axel-AI\axel-core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Llena `.env` a mano. Nunca lo subas a git.

## Arrancar

Opción 1, con el script:

```powershell
C:\Proyectos\Axel-AI\axel-core\scripts\levantar.ps1
```

Opción 2, a mano:

```powershell
cd C:\Proyectos\Axel-AI\axel-core
.\.venv\Scripts\Activate.ps1
python -m axel.demo
```

El demo carga `.env`, usa `./axel.db` y abre:

- Panel: http://127.0.0.1:8090/
- Health: http://127.0.0.1:8090/health
- Auditoría: http://127.0.0.1:8090/audit y `/audit/<event_id>`
- Prueba: `POST /webhooks/test`
- WhatsApp: `GET` y `POST /webhooks/whatsapp`

Ojo: si `.env` tiene token de WhatsApp y `WA_OWNER_PHONE`, el demo envía mensajes reales
(respuestas, alertas de nivel 3 y el recordatorio diario al dueño).

## Pruebas

Sin servidor (usan una base temporal):

```powershell
cd C:\Proyectos\Axel-AI\axel-core
.\.venv\Scripts\Activate.ps1
python tests/test_memory_cross_channel.py
python tests/test_level3_approval.py
```

Con el demo corriendo en 8090:

```powershell
python tests/test_message.py
.\scripts\enviar_prueba.ps1
.\scripts\enviar_reembolso.ps1
```

`enviar_prueba.ps1` consulta `/health` y manda un mensaje a `/webhooks/test`.
`enviar_reembolso.ps1` pide un reembolso: AXEL no lo ejecuta, lo deja pendiente del dueño.
