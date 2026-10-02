# AXEL Módulo 5 — WhatsApp + atención básica

Hito: AXEL responde tu primer mensaje real.  
Canal oficial: WhatsApp Cloud API (Meta). No uses clientes no oficiales.

Documentación Meta: https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/

---

## A. Crear la cuenta a tu nombre (dueño)

Hazlo con **tu Facebook personal** y un **portafolio de negocio tuyo**. Así el WABA queda a tu nombre.

### A1. Portafolio de Meta Business
1. Entra a https://business.facebook.com/
2. Crea un portafolio (o usa el que ya tengas).
3. Pon el nombre legal o comercial real.
4. Completa verificación de negocio cuando Meta la pida (puede tardar; el piloto de prueba funciona antes).

### A2. App de desarrollador con WhatsApp
1. https://developers.facebook.com/apps/
2. Create App.
3. Nombre de la app + tu email.
4. Caso de uso: **Connect with customers through WhatsApp**.
5. Asocia el portafolio de negocio.

### A3. Número
En el panel de la app → WhatsApp → API Setup:
- Meta te da un **número de prueba** (sirve para el piloto).
- Agrega **tu celular personal** como destinatario de prueba (Add phone number / allow list).
- Anota:
  - `WA_PHONE_NUMBER_ID`
  - `WA_BUSINESS_ACCOUNT_ID`
  - token temporal (Generate access token)

El token temporal caduca. Para producción luego creas un System User token permanente en Business Settings. No lo pongas en el chat ni en git.

### A4. Por qué este camino
- El WABA queda bajo **tu** portafolio.
- No dependes de un reseller para el primer hito.
- Claude no interviene aquí. Meta es solo el canal.

---

## B. Exponer AXEL a internet (Meta no acepta localhost)

Necesitas HTTPS público hacia:

`https://TU-DOMINIO/webhooks/whatsapp`

Opciones simples:
- Un VPS con Caddy + Docker (módulo de deploy)
- Túnel de prueba: Cloudflare Tunnel o ngrok **solo para tu número**

Ejemplo ngrok (prueba):
```bash
ngrok http 8090
# URL: https://xxxx.ngrok.io/webhooks/whatsapp
```

---

## C. Conectar el webhook

1. Arranca AXEL:
```bash
cd axel-core
cp .env.example .env
# llena WA_VERIFY_TOKEN, WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID, WA_APP_SECRET
python -m axel.demo
```
El arranque es `python -m axel.demo` (puerto 8090). No `uvicorn axel.main:app`: `main.py` está marcado NO ARRANCAR (sin firma ni wamid).

2. En App Dashboard → WhatsApp → Configuration:
   - Callback URL: `https://TU-URL/webhooks/whatsapp`
   - Verify token: el mismo de `WA_VERIFY_TOKEN` (ej. `axel-verify`)
   - Verify and Save

3. Subscribe al campo **messages**.

Meta manda un GET. AXEL responde el `hub.challenge` si el token coincide.

---

## D. Activar solo atención + CRM + KB

Ya está en el núcleo:
- Saludo y FAQ: `kb.json` + `axel/knowledge_base.py`
- Registro de cliente: `memory.identify_customer` (guarda wa_id + teléfono + nombre)
- Auditoría: cada mensaje queda en `audit_events`

Edita `kb.json` con horarios y datos reales **antes** de probar con gente.

Reservas/ventas/reembolsos siguen las reglas de niveles, pero el hito de M5 es **preguntas + saludo + ficha**.

---

## E. Probar con TU número (antes que clientes)

1. En API Setup, tu número personal debe estar en la lista de prueba.
2. Desde **tu WhatsApp**, escribe al número de prueba de Meta:
   - `Hola`
   - `¿Cuál es el horario?`
3. Debes recibir respuesta de AXEL.
4. En el servidor:
```bash
curl -s http://127.0.0.1:8090/audit
```
Verifica `channel=whatsapp`, `customer_id` creado, `agent=atencion`.

5. Escribe otra vez. Debe reconocerte (misma ficha).

Si no llega el webhook: revisa HTTPS, verify token, suscripción `messages`, y que el POST responda 200 rápido.

---

## F. Criterios de aceptación M5

- [ ] WABA / app creados a nombre del dueño
- [ ] Webhook verificado por Meta
- [ ] Mensaje de tu celular → respuesta de AXEL
- [ ] FAQ de horario sale de `kb.json` (no inventada)
- [ ] Cliente queda en CRM (`customers` + `identities`)
- [ ] Evento en audit

No abras el número a extraños hasta tener esos 6 puntos en verde.

---

## G. Qué no es M5
- Plantillas HSM de marketing
- Instagram
- Llamadas de voz
- Token permanente de system user (hazlo cuando el piloto funcione 48 h)
