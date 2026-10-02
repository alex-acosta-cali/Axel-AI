#!/usr/bin/env bash
# Vigía de health. Si /health no contesta en 5 s o no trae "kb_ok": true, reinicia axel.
# systemd con Restart=always no reinicia un proceso que sigue "active" pero mudo.
# Solo imprime una línea con fecha. No toca .env ni la base. Se instala con cron (docs/OPERACION.md).
set -uo pipefail

FECHA="$(date '+%Y-%m-%d %H:%M:%S')"
health="$(curl -s --max-time 5 http://127.0.0.1:8090/health || true)"

if printf '%s' "$health" | grep -q '"kb_ok": *true'; then
    exit 0
fi

echo "$FECHA health sin kb_ok: ${health:-sin respuesta}. Reinicio axel."
systemctl restart axel
