# AXEL Core v0.1 — Módulo 2

Núcleo local: orquestador + model router + memoria SQLite + auditoría.

No necesita Meta ni Claude para esta prueba.

## Dónde va cada archivo

```
axel-core/
  requirements.txt
  .env.example
  README.md
  docker-compose.yml
  axel/
    __init__.py
    main.py
    envelope.py
    orchestrator.py
    router_model.py
    permissions.py
    memory.py
    agents/
      atencion.py
      reservas.py
      escalamiento.py
  tests/
    test_message.py
```

Copia esta carpeta a tu máquina. Trabaja desde `axel-core/`.

## Cómo ejecutarlo

```bash
cd axel-core
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn axel.main:app --reload --port 8080
```

Health: http://127.0.0.1:8080/health

## Prueba simple

En otra terminal:

```bash
cd axel-core
source .venv/bin/activate
python tests/test_message.py
```

O a mano:

```bash
curl -s http://127.0.0.1:8080/webhooks/test \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hola, quiero una cita mañana","channel":"test","channel_user_id":"ana"}'
```

Luego:

```bash
curl -s http://127.0.0.1:8080/audit
```

Debes ver `intent=reserva`, `agent=reservas`, `supervision_level=2`, `model` elegido y el evento en audit.

## Docker (opcional)

```bash
docker compose up --build
```
