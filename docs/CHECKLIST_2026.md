# Checklist piloto 2026

- [ ] 403 en el dominio (desde el celular sin wifi, el panel da 403 `solo_local`)
- [ ] health en el servidor (`curl -s http://127.0.0.1:8090/health`)
- [ ] El WhatsApp del negocio responde "horario"
- [ ] Dueño: "como vas" lee el STATE
- [ ] Cliente: "como vas" no ve el STATE
- [ ] Pedido se anota
- [ ] N3 se detiene (reembolso queda pendiente del dueño)
- [ ] `copia_vps.sh` corre a mano
- [ ] cron `0 8 * * *` (3:00 Cali)
- [ ] Panel por túnel SSH (ver `PANEL.md`)
- [ ] No Meta producción
