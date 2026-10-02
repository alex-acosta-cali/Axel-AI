# Ritual VPS

## Actualizar
```bash
cd /opt/Axel-AI && git pull
sudo systemctl restart axel
curl -s http://127.0.0.1:8090/health
journalctl -u axel -n 30
```

## KB fuera de git (muro 39)
`kb.json` ya no está en git. Lo edita el dueño por chat. En git queda `kb.example.json`.
El primer `git pull` después del muro 39 borra `kb.json` del VPS. Antes de ese pull:
```bash
cp /opt/Axel-AI/axel-core/kb.json /opt/Axel-AI/kb.json.antes
cd /opt/Axel-AI && git pull
cp /opt/Axel-AI/kb.json.antes /opt/Axel-AI/axel-core/kb.json
```
Si `kb.json` falta o está roto, AXEL usa `kb.ultima.json` o la copia más nueva de `copias/`. No se cae.

## Copia
```bash
bash /opt/Axel-AI/axel-core/scripts/copia_vps.sh
```
Copia `axel.db` y `kb.json` a `/opt/Axel-AI/copias/`. No copia `.env`. Deja las 14 más nuevas.

Cron diario, `crontab -e`:
```
0 8 * * * bash /opt/Axel-AI/axel-core/scripts/copia_vps.sh
```
El VPS está en UTC: 8:00 UTC = 3:00 Cali.

## Panel
Por túnel SSH, no por el dominio (el dominio da 403). Ver `PANEL.md`.

## No
- No Meta producción.
