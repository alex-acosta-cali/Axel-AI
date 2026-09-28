# Hosting 24/7 (pendiente)

## Hoy
- Axel corre en el PC con ngrok.
- Si el PC se apaga, Axel no responde.
- Al reiniciar ngrok, la URL cambia y hay que actualizar el webhook en Meta.

## Después
- VPS barato.
- Mismo arranque: `python -m axel.demo`.
- Webhook con URL fija. Ya no hay que cambiarlo.

## Reglas
- No Docker en este paso.
- Nunca subir `.env` a git ni al VPS por git. Se copia a mano.
