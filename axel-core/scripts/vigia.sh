#!/usr/bin/env bash
# Vigía de health. Reinicia axel solo si /health no contesta en 25 s.
# systemd con Restart=always no reinicia un proceso que sigue "active" pero mudo.
# Si contesta con kb_ok false, no reinicia: reiniciar no trae la KB. Deja una línea en el log.
# No toca .env ni la base. Se instala con cron (docs/OPERACION.md).
set -uo pipefail

FECHA="$(date '+%Y-%m-%d %H:%M:%S')"

if ! health="$(curl -s --max-time 25 http://127.0.0.1:8090/health)" || [ -z "$health" ]; then
    echo "$FECHA health sin respuesta. Reinicio axel."
    systemctl restart axel
    exit 0
fi

if ! printf '%s' "$health" | grep -q '"kb_ok": *true'; then
    echo "$FECHA KB ausente, no reinicio."
fi
