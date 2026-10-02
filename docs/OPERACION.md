# Operación del VPS
- `PYTHONUNBUFFERED=1` en el servicio axel: así los prints llegan al journal al momento.
- Cron del vigía: `*/5 * * * * /bin/bash /opt/Axel-AI/axel-core/scripts/vigia.sh >> /opt/Axel-AI/copias/vigia.log 2>&1`
- No correr `tests/test_message.py` con el túnel abierto.
