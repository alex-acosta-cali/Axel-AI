# AXEL_STATE.md
Actualizado: 2026-09-29 (Cali)
Dueño: Alex. Repo: C:\Proyectos\Axel-AI
GitHub: https://github.com/alex-acosta-cali/Axel-AI (privado)

## 0. Estado hoy
- Mapa al 29 sep. Siguiente: VPS. No Meta producción.
- 30 sep: VPS vivo. Ngrok apagado. El 314 responde por el dominio del VPS (HTTPS). El panel sigue solo en 127.0.0.1. No Meta producción.
- Piloto 2026, lado dueño.
- WhatsApp real: +57 314 5801851. Phone ID y tokens solo en `.env`.
- Desde el 30 sep el webhook entra por el VPS (nginx con HTTPS hacia `127.0.0.1:8090`). Ngrok apagado.
- Claude Code trabaja en el repo (ejecutor; Grok revisa, Alex aprueba).
- Pruebas OK: `test_memory_cross_channel`, `test_level3_approval`, `test_message`, `test_kb_cafeteria`, `test_kb_ferreteria`, `test_configurar`, `test_aviso_cita`, `test_panel_envios` y `test_piloto_2026`.
- App de Meta sigue **En desarrollo** (no publicada).
- 28 sep: un cupo confirmado por franja (probado). Cancelar y reprogramar sueltan el cupo viejo.
- 28 sep: reembolso N3, el dueño aprueba y el cliente recibe el aviso. Probado con un segundo celular.
- 28 sep: aprobar/rechazar y comandos del dueño solo desde WA_OWNER_PHONE o el panel.
- Hosting 24/7, Instagram y modelo de lenguaje: solo notas en `docs/`. No construidos.

## 0.1 Muro de comercio (hecho 28 sep)
AXEL es comercio, no barbería. Todo sale de la KB.
- FAQ sin precio quemado: los precios salen solo de `servicios[]`.
- `configurar`: el dueño arma el negocio por chat (nombre, rubro, agenda, horario, franjas, ubicación, servicios).
- Pedidos: "me lo llevo X" anota el pedido sin cobro. El dueño lo ve con `pedidos` y en el panel.
- Pedido y cita separados: comprar no abre una cita, y pedir cita no anota un pedido.
- Prueba ferretería (`test_kb_ferreteria`): sin agenda, sin corte, sin cita.
- Panel: muestra catálogo y pedidos.

## 0.2 Muro 5 (hecho 28 sep)
- Pedidos en tabla `pedidos` (cliente, servicio, precio, hora), no en nota. Los viejos se pasaron solos.
- Avisos al cliente 24 h y 2 h antes de la cita (hora Cali). Uno por cita y plazo. Solo citas vivas. Si el demo está apagado, el aviso se pierde.
- `reporte` del dueño: fecha Cali, citas de hoy, pedidos de hoy con total, pendientes N3. También en el panel.
- `/health` dice si `kb.json` está bien y cuántos servicios tiene.
- Pack de aceptación: `tests/test_piloto_2026.py`.

## 0.3 Muro 6 (hecho 29 sep)
- Español: reservas igualan tildes y ñ. «mañana 11» reserva el día siguiente a las 11 si la franja existe y está libre. Las citas con «mañana» ya tienen aviso 24h/2h y cuentan en `reporte`.
- `agenda_palabras` en `kb.json` (piloto: cita, reservar, reserva, turno, mesa). Con agenda, abren la reserva; sin agenda, AXEL dice que no agenda por este canal.
- El dueño la cambia: `agenda palabras cita reserva mesa turno` (reemplaza la lista). Sale en `catalogo` y `ayuda`. El cliente no la cambia.
- La oferta usa la palabra: con «mesa», «¿Reservamos mesa?»; con «turno», «¿Te anoto un turno?»; sin lista, «¿Quieres que te reserve un cupo?».

## 0.4 Muro 7 (hecho 29 sep)
- Piloto sin mesa: `agenda_palabras` = cita, reservar, reserva, turno. La oferta dice «¿Te anoto un turno?».
- Cancelar / reprogramar con palabras de agenda: «cancelar el turno», «cancelar la reserva», «reprogramar turno». «cita» vale siempre. Una palabra fuera de la lista («cancelar el pedido») no toca citas.
- El cliente ve solo lo suyo: «mi cita», «mis citas», «mi reserva», «mi turno» listan sus reservas vivas; si no tiene, «No tienes reserva.». El dueño sigue con `citas` para todas.

## 0.5 Muro 8 (hecho 29 sep)
- Pedidos con estado: `anotado` → `entregado`. El dueño escribe `pedido listo` (el último anotado). Entregado no es pagado: AXEL no cobra. El cliente no cambia estado.
- `pedidos` y el panel muestran el estado.
- `limpiar` no borra ventas: pedidos, citas y N3 quedan en la base. Solo borra clientes sin nombre, celular ni correo.
- `reporte` (y el panel) parte los pedidos de hoy en anotados y entregados, con total $ de cada uno.

## 0.6 Muro 9 (hecho 29 sep)
- Saludo con reserva o pedido: si el cliente dice hola/buenas y tiene cita viva, «Hola NOMBRE, soy AXEL. Tu turno es martes 11:00.» (palabra del piloto: turno; si no, cita). Sin cita pero con pedido anotado: «Tienes un pedido anotado: corte $25.000.». Gana la cita. Sin nada, el saludo de siempre. Al dueño no.
- El cliente ve sus pedidos: «mi pedido» / «mis pedidos» lista solo los suyos (servicio, precio, estado, hora Cali); si no tiene, «No tienes pedidos.». El dueño sigue con `pedidos` para todos.
- El dueño recibe aviso de pedido nuevo por el canal de alertas N3 (`WA_OWNER_PHONE`): «Pedido nuevo: quién · servicio $. AXEL no cobra.». Solo informa: no crea pendiente.

## 0.7 Habitación 10-13 (hecha 29 sep)
- 10. Saludo con cita o pedido: primera línea la cita o el pedido; segunda, negocio + abierto/cerrado. Sin ofrecer cita. Dueño sin cambios.
- 11. `pedido listo` del dueño: sin más, solo si hay un anotado hoy; con varios, lista (nombre, $, hora, cel …1234) y pide `pedido listo NOMBRE` o las 4 últimas cifras del celular. Mismo nombre en dos clientes: pide las cifras. Nunca marca el de otra persona. El cliente no lo usa.
- 12. Al entregar, aviso a ESE cliente: «Tu pedido de SERVICIO quedó listo. El dueño confirma el pago. AXEL no cobra.». Sin celular no se envía: queda en el log.
- 13. Pack en `test_piloto_2026.py`: hola con turno y negocio, hola sin reserva sin turno, dos anotados no se cierran juntos, texto al cliente al entregar.

Muros 14-17 hechos (29 sep): 14 tono en la KB, 15 stock 0 no se vende, 16 dueño edita stock, 17 dueño cambia tono.

## 0.8 Tono de la KB (muros 14 y 17)
- `kb.json` tiene `tono`: `cercano` (tú, piloto) o `formal` (usted). Si falta o no se entiende, cercano.
- Lo usan el saludo (con cita, pedido, abierto o cerrado), «No tengo esa información…» y la pregunta de nombre («¿Cómo quiere que le llame?» en formal).
- El dueño lo cambia por chat: `tono formal` / `tono cercano` (responde cuál quedó). El cliente no. Sale en `catalogo` y `ayuda`.
- No cambia precios ni permisos.

## 0.9 Stock (muros 15 y 16)
- `servicios[].stock` es opcional. Sin el campo, se vende como siempre.
- Stock 0 = no se vende: «No hay NOMBRE ahora.», sin pedido ni oferta de cita. En `precios` sale «agotado».
- El dueño lo cambia: `stock corte 0`, `stock corte 5`. El cliente no. `catalogo` muestra el stock si existe.
- No es inventario: vender no resta.

### Muro 18 — seguridad 1-3 (hecho 29 sep)
- 18.1 Panel solo local: desde ngrok (Host ngrok o `X-Forwarded-*`) solo pasan `/webhooks/whatsapp` y `GET /health`. Panel, `/audit`, `/panel`, `/decidir`: 403 `solo_local`.
- 18.2 Firma Meta: `X-Hub-Signature-256` con `WA_APP_SECRET` (solo en `.env`). Sin secreto o sin firma válida: 403.
- 18.3 wamid: el mismo mensaje reintentado por Meta se ignora. 200 a Meta antes de responder al cliente.
- Falta: prueba real en el 314 con el demo reiniciado.

### Muro 19 — envíos (hecho 29 sep)
- Tabla `envios`: una fila por aviso saliente. A quién, texto corto (80), para qué, estado, hora (se muestra en Cali).
- Para qué: `aviso_24h`, `aviso_2h`, `pedido_listo`, `n3_cliente`, `n3_dueno`, `pedido_nuevo`.
- Estado: `enviado`, `fallo`, `sin_celular`, `omitido_dueno` (el celular del cliente es el del dueño), `fuera_24h` (muro 23).
- Un solo intento. No reintenta solo. Si Meta falla (o falta token), queda `fallo` en la fila.
- Comando `envios` del dueño: últimas 10 filas (hora Cali · dueño o cel …1234 · para qué · texto corto · estado). El cliente no las ve.
- Panel local, debajo del reporte: últimas 8 filas (hora Cali, para qué, estado, a quién: dueño, nombre o …1234). Sin texto. Solo lectura.
- Prueba en `test_piloto_2026.py`. Panel con prueba desde el muro 23.
- Pendiente: la tabla crece sin límite.

### Cita con hora exacta (hecho 29 sep)
- Cita nueva o reprogramada guarda `cita_at` ('AAAA-MM-DD HH:MM', hora Cali UTC-5) en `conversation_summaries`. El texto de la cita se queda.
- Las viejas no se reescriben solas: siguen con `cita_at` vacío y se leen del texto como siempre.
- Leen `cita_at` si existe: aviso 24h/2h, `reporte` y «mis citas». Desde el muro 23 también cupos, saludo, `citas` y panel.
- Prueba en `test_aviso_cita.py`. `reporte` con hora exacta sin prueba propia.

### Siguiente, huecos 4-8 (según Grok)
- 4. Ventana 24 h / plantillas: papel hecho (`docs/WHATSAPP_24H.md`). No pedir plantillas a Meta todavía.
- 5. Tabla de envíos: hecha (muro 19). `fuera_24h` hecho (muro 23).
- 6. Cita con hora exacta: hecha (29 sep). Ver arriba.
- 7. Respaldo diario de `axel.db` y `kb.json`: con el VPS (Hetzner). Hoy solo copia manual (ver abajo).
- 8. Ley 1581 (habeas data): aviso de datos y borrado N3 hechos (muro 23). Lo demás, antes de Meta producción.

### Copia local (hecho 29 sep)
- Manual: `powershell -ExecutionPolicy Bypass -File C:\Proyectos\Axel-AI\axel-core\scripts\copia.ps1`.
- Copia `axel.db` (con backup de sqlite3, sirve con el demo prendido) y `kb.json` a `C:\Proyectos\Axel-AI\copias\`, con fecha y hora en el nombre. No copia `.env`. `copias/` está en `.gitignore`.
- No es el backup del VPS: mismo disco, no corre solo, no borra copias viejas.

### Aviso de datos y borrado (hecho 29 sep; el muro 23 lo cambia)
- Primer saludo de un cliente WhatsApp (una vez, antes de pedir nombre): «Tus datos (nombre y celular) quedan en la ficha de este negocio. Escribe borrar mis datos y el dueño lo revisa.» En tono formal, usted. Al dueño no.
- Si el primer mensaje no es saludo, el aviso sale en el primer saludo después.
- «borrar mis datos» es N3: pendiente del dueño. AXEL no borra nada solo.
- El dueño aprueba o rechaza como un reembolso. Aprobar no borra: el borrado lo hace el dueño. No hay comando de borrado.
- Prueba en `test_piloto_2026.py`.
- No es Meta producción.

### Muro 23 (hecho 29 sep)
- Panel envíos con prueba: `test_panel_envios.py` y el piloto. 8 filas, estado visible, sin texto ni celular de 10 dígitos.
- `fuera_24h`: pedido listo, aviso 24h/2h y N3 al cliente no mandan texto libre si el último mensaje entrante de WhatsApp de ese cliente tiene más de 24 h. Queda fila `fuera_24h`. Al dueño no se le mira (su ventana es la suya). No se piden plantillas a Meta.
- `cita_at` en cupos, saludo «Tu turno es…», `citas` (y `clientes`) del dueño y panel. Sin `cita_at`, el texto de siempre. Las citas viejas no se reescriben.
- Aviso de datos en el primer mensaje del cliente (hola o un precio), una vez, antes de pedir el nombre. Al dueño no.
- Aprobar «borrar mis datos» anonimiza la ficha: quita nombre, correo y notas; marca `datos_borrados`. Celular e identidad se quedan para no duplicar al cliente. «mi ficha» dice «datos borrados». No borra pedidos, citas, mensajes ni auditoría. Rechazar no toca la ficha.
- Huecos: si el cliente vuelve a dar su nombre, «mi ficha» sigue diciendo «datos borrados»; mensajes y auditoría guardan el texto tal cual.

### Siguiente
- Código de producto: ninguno por ahora.
- VPS: vivo desde el 30 sep. Falta respaldo con cron.
- Plantillas 24 h: solo papel (`docs/WHATSAPP_24H.md`).

## 0.10 Alcance
- Hoy: 1 negocio, 1 WhatsApp, dueño por número (`WA_OWNER_PHONE`), panel de ese negocio.
- 2028: varios negocios. No se construye ahora.

## 0.11 Capítulo VPS (vivo 30 sep)
- AXEL corre 24/7 en el VPS (nginx con HTTPS hacia `127.0.0.1:8090`). Ngrok apagado.
- Falta: respaldo diario con cron.
- No Meta producción.
- No segundo panel.
- No cobro.
- No Instagram.

## 1. Visión (fija hasta que Alex apruebe cambio)
AXEL es el asistente del comercio, no de un rubro. La barbería fue el primer catálogo de prueba, no el producto. Una categoría nueva = llenar la KB (`kb.json`), no un programa nuevo.
AXEL AI OS opera un negocio: atiende por WhatsApp, Instagram, web, email y voz; memoria de cliente; agenda; venta; cobro; marketing. Supervisión en 3 niveles. Trazabilidad de cada acto.
Hoy el piloto corre en el VPS; WhatsApp real entra por su dominio. El panel solo en http://127.0.0.1:8090. App de Meta en desarrollo.

## 2. Módulos
| Módulo | Estado |
|--------|--------|
| M1 Arquitectura + model router (concepto) | aprobado en diseño / router local simple |
| M2 Orquestador | construido y en uso |
| M3 Memoria SQLite + CRM ficha | construido |
| M4 Permisos 1/2/3 + auditoría + panel dueño | construido |
| M5 WhatsApp Cloud API | conectado por el VPS (ngrok apagado); app Meta en desarrollo |
| Panel local HTML | construido |
| Reservas confirmar / cancelar / reprogramar | construido (piloto): un cupo por franja, cancelar/reprogramar sueltan el cupo |
| Panel: cupos de la semana LIBRE/TOMADA | construido |
| KB del comercio | construido: negocio, rubro, agenda, horario, franjas, servicios, políticas, FAQ, ubicación. El dueño la edita por chat. Primer catálogo de prueba: barbería |
| Instagram | solo nota (`docs/CANAL_INSTAGRAM.md`) |
| Hosting 24/7 | solo nota (`docs/HOSTING_24_7.md`) |
| Modelo de lenguaje | solo nota (`docs/MODELO_LENGUAJE.md`); router no llama APIs |
| Llamadas / factura / marketing | pendiente |

## 3. Decisiones
- Nombre: AXEL AI OS.
- Simple primero: Python + SQLite + demo HTTP. Sin FastAPI obligatorio.
- Grok = arquitecto. Claude Code = ejecutor en el repo.
- Archivos completos, no parches de una línea.
- Reiniciar demo después de cada cambio de .py o kb.json.
- Intent no listado = nivel 3.
- `datos` y `venta` (consulta de precio) = nivel 1.
- Reserva / reprogramar / cancelar = nivel 2.
- Reembolso / queja = nivel 3. Un pendiente por cliente+intent.
- Meta: no portafolio en cuentas restringidas. Migrar a cuenta de Alex ~octubre.

## 4. Cómo arrancar
```
Set-Location C:\Proyectos\Axel-AI\axel-core
$env:PYTHONPATH = "."
python -m axel.demo
```
Chrome: http://127.0.0.1:8090/

## 5. Pendientes / bugs conocidos
- Meta WABA no creado en cuenta propia.
- Agenda: un cupo por franja, pero sin calendario real. La cita se guarda como texto.
- Reservas solo en franjas visibles, que salen de `kb.json` (hoy 9, 11 y 15). Las viejas fuera de franja salen aparte en el panel.
- Model router no llama APIs de pago.
- “am” dentro de palabras ya no debe contar como hora (corregido en reservas).
- Git a veces deja archivos sin commit: revisar `git status` antes de parar.

## 6. Criterios del piloto actual
- N1: horario, KB, nombre, celular, correo.
- N2: cita → día/hora → confirmar; cancelar; reprogramar pregunta y luego cambia.
- N3: reembolso frena; segundo reembolso no duplica pendiente; Aprobar/Rechazar.
- Ficha visible: Alex + celular + correo.
