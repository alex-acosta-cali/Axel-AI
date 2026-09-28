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

## 4. Red
- **Ojo:** hoy `axel.demo` escucha solo en `127.0.0.1:8090`. Abrir el puerto 8090 en el firewall **no basta** para entrar desde fuera.
- Camino recomendado: nginx en el mismo VPS, en los puertos 80/443, reenviando a `127.0.0.1:8090`. Así no se toca el código.
- HTTPS con Let's Encrypt (certbot) cuando haya dominio.
- Probar por `IP:8090` directo exigiría cambiar el código. Eso es una decisión: se consulta antes.
- Meta solo acepta webhooks con HTTPS. Sin dominio y certificado, el webhook no se puede mover al VPS.

## 5. Webhook en Meta
- Nueva URL: `https://DOMINIO/webhooks/whatsapp`.
- Token de verificación: `axel-verify` (o el `WA_VERIFY_TOKEN` del `.env`).
- Cuando el VPS conteste, se apaga ngrok.

## 6. Recordatorios
- El recordatorio diario al dueño es un hilo dentro de `axel.demo`. Solo corre si el proceso está vivo. En el VPS queda vivo.
- Los avisos al cliente 24 h y 2 h antes **todavía no existen en el código**. No se programan ahora.

## 7. Rollback
```bash
cd ~/axel && git log --oneline -5
git checkout <commit_anterior>
sudo systemctl restart axel
```

## 8. Alerta de caída
- Queda para después. Este documento no define monitoreo.

## Después
- Pasar la app de Meta a producción: ver `META_PRODUCCION.md`.
