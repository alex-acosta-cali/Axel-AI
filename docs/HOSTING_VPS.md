# Hosting VPS — opción B

Lo más simple que aguante 24/7. Un solo proceso, igual que en el PC.
Sin Docker. Sin Kubernetes. `.env` nunca va por git.

## 1. El servidor
- VPS con Ubuntu 22.04 y 1 GB de RAM.
- Región lo más cerca de Colombia (São Paulo, si el proveedor la tiene).
- Ejemplos: Hetzner, DigitalOcean, Contabo. Los precios cambian: se miran el día de la compra.
- **El dueño elige, crea la cuenta y paga.** Claude no crea cuentas.

## 2. Instalar Axel
```bash
git clone <URL_DEL_REPO> axel
cd axel/axel-core
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
- Copiar `.env` **a mano** (por ejemplo con `scp`) a `axel-core/.env`. Nunca por git.
- La base `axel.db` se crea en `axel-core/`, que es la carpeta de trabajo.

## 3. systemd
El mismo comando del PC: `PYTHONPATH=. python -m axel.demo`.

`/etc/systemd/system/axel.service`:
```ini
[Unit]
Description=Axel demo
After=network-online.target

[Service]
WorkingDirectory=/home/<usuario>/axel/axel-core
Environment=PYTHONPATH=.
ExecStart=/home/<usuario>/axel/axel-core/.venv/bin/python -m axel.demo
Restart=always
User=<usuario>

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now axel
journalctl -u axel -f
```

## 4. Red (decidido por Grok)
- `axel.demo` **sigue en `127.0.0.1:8090`**. No se cambia el código para escuchar en `0.0.0.0`.
- Desde fuera **solo nginx con HTTPS** (Let's Encrypt / certbot), reenviando a `127.0.0.1:8090`.
- **Prohibido** probar por `IP:8090`. El puerto 8090 no se abre en el firewall.
- Meta solo acepta webhooks con HTTPS. Sin dominio y certificado, el webhook no se mueve al VPS.

## 5. Webhook en Meta
- Nueva URL: `https://DOMINIO/webhooks/whatsapp`.
- Token de verificación: el `WA_VERIFY_TOKEN` del `.env`.
- Cuando el VPS conteste, se apaga ngrok.

## 6. Recordatorios
- El recordatorio diario al dueño es un hilo dentro de `axel.demo`. Solo corre si el proceso está vivo. En el VPS queda vivo.
- Los avisos al cliente 24 h y 2 h antes ya existen: mismo hilo, hora Cali, uno por cita y plazo. Si el proceso está apagado a esa hora, se pierden.

## 7. Rollback
```bash
cd /opt/Axel-AI && git log --oneline -5
git checkout <commit_anterior>
sudo systemctl restart axel
```

## 8. Alerta de caída
- Queda para después. Este documento no define monitoreo.

## Después
- Pasar la app de Meta a producción: ver `META_PRODUCCION.md`.
