# AXEL_STATE.md
Actualizado: 2026-09-29 (Cali)
Dueño: Alex. Repo: C:\Proyectos\Axel-AI
GitHub: https://github.com/alex-acosta-cali/Axel-AI (privado)

## 0. Estado hoy
- Piloto 2026, lado dueño.
- WhatsApp real: +57 314 5801851. Phone ID y tokens solo en `.env`.
- Demo en http://127.0.0.1:8090 expuesto con ngrok para el webhook.
- Claude Code trabaja en el repo (ejecutor; Grok revisa, Alex aprueba).
- Pruebas OK: `test_memory_cross_channel`, `test_level3_approval`, `test_message`, `test_kb_cafeteria`, `test_kb_ferreteria`, `test_configurar`, `test_aviso_cita` y `test_piloto_2026`.
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

## 0.6 Alcance
- Hoy: 1 negocio, 1 WhatsApp, dueño por número (`WA_OWNER_PHONE`), panel de ese negocio.
- 2028: varios negocios. No se construye ahora.

## 0.7 Siguiente capítulo: VPS
- VPS cuando haya tarjeta.
- No cobro real.
- No segundo panel.
- Llevar AXEL a un VPS 24/7 (nginx con HTTPS hacia `127.0.0.1:8090`).
- No Meta producción.
- No Instagram.

## 1. Visión (fija hasta que Alex apruebe cambio)
AXEL es el asistente del comercio, no de un rubro. La barbería fue el primer catálogo de prueba, no el producto. Una categoría nueva = llenar la KB (`kb.json`), no un programa nuevo.
AXEL AI OS opera un negocio: atiende por WhatsApp, Instagram, web, email y voz; memoria de cliente; agenda; venta; cobro; marketing. Supervisión en 3 niveles. Trazabilidad de cada acto.
Hoy el piloto corre en local (panel http://127.0.0.1:8090) con ngrok hacia WhatsApp real. App de Meta en desarrollo.

## 2. Módulos
| Módulo | Estado |
|--------|--------|
| M1 Arquitectura + model router (concepto) | aprobado en diseño / router local simple |
| M2 Orquestador | construido y en uso |
| M3 Memoria SQLite + CRM ficha | construido |
| M4 Permisos 1/2/3 + auditoría + panel dueño | construido |
| M5 WhatsApp Cloud API | conectado vía ngrok; app Meta en desarrollo |
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
- `limpiar` borra al cliente fantasma aunque tenga pedido, cita viva o N3: esas filas quedan sin dueño («sin nombre»); si vuelve a escribir es cliente nuevo y no ve ni cancela su cita. Sin arreglar.
- Nombre: si AXEL acaba de preguntar el nombre y el cliente escribe «cancelar la mesa», se guarda como nombre. Sin arreglar.

## 6. Criterios del piloto actual
- N1: horario, KB, nombre, celular, correo.
- N2: cita → día/hora → confirmar; cancelar; reprogramar pregunta y luego cambia.
- N3: reembolso frena; segundo reembolso no duplica pendiente; Aprobar/Rechazar.
- Ficha visible: Alex + celular + correo.
