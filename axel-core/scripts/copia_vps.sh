#!/usr/bin/env bash
# Copia axel.db y kb.json del VPS a /opt/Axel-AI/copias/ con fecha y hora en el nombre.
# Usa sqlite3 .backup si está instalado (sirve con AXEL prendido); si no, cp.
# No copia .env. Solo imprime rutas y tamaños. Deja las 14 copias más nuevas de cada archivo.
set -euo pipefail

BASE="${AXEL_BASE:-/opt/Axel-AI}"
CORE="$BASE/axel-core"
DESTINO="$BASE/copias"
FECHA="$(date +%Y-%m-%d_%H%M)"
GUARDAR=14

mkdir -p "$DESTINO"

db="$CORE/axel.db"
db_copia="$DESTINO/axel_$FECHA.db"
if [ -f "$db" ]; then
    if command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 "$db" ".backup '$db_copia'"
    else
        cp "$db" "$db_copia"
    fi
    echo "OK $db_copia ($(stat -c %s "$db_copia") bytes)"
else
    echo "No existe $db"
fi

kb="$CORE/kb.json"
kb_copia="$DESTINO/kb_$FECHA.json"
if [ -f "$kb" ]; then
    cp "$kb" "$kb_copia"
    echo "OK $kb_copia ($(stat -c %s "$kb_copia") bytes)"
else
    echo "No existe $kb"
fi

# Solo las 14 más nuevas de cada tipo. El nombre lleva la fecha: el orden por nombre es el orden por fecha.
for patron in 'axel_*.db' 'kb_*.json'; do
    find "$DESTINO" -maxdepth 1 -type f -name "$patron" | sort -r | tail -n +$((GUARDAR + 1)) | while read -r vieja; do
        rm -f -- "$vieja"
        echo "Borrada copia vieja $vieja"
    done
done
