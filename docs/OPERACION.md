# Operación del VPS
- `PYTHONUNBUFFERED=1` en el servicio axel: así los prints llegan al journal al momento.
- Cron del vigía: `*/5 * * * * /bin/bash /opt/Axel-AI/axel-core/scripts/vigia.sh >> /opt/Axel-AI/copias/vigia.log 2>&1`. Reinicia solo si `/health` no contesta en 5 s. Con `kb_ok` false no reinicia: escribe «KB ausente, no reinicio.»
- No correr `tests/test_message.py` con el túnel abierto.

## Antes de git pull
El 2 oct un `git pull` borró `kb.json` (salió de git en `188c4b6`) y AXEL quedó 14 h sin KB.

1. Copia de `kb.json` y `axel.db` a `/opt/Axel-AI/copias/`:
   `bash /opt/Axel-AI/axel-core/scripts/copia_vps.sh`
2. `cd /opt/Axel-AI && git pull`
3. Si el pull borró `kb.json`, devolver la copia más nueva:
   `[ -f axel-core/kb.json ] || cp "$(ls -1 copias/kb_*.json | sort | tail -n 1)" axel-core/kb.json`
4. `systemctl restart axel` y `curl -s http://127.0.0.1:8090/health`: debe decir `"kb_ok": true`.
