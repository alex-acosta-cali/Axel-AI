# AXEL_STATE.md
Actualizado: 2026-09-28 (Cali)
Dueño: Alex. Repo: C:\Proyectos\Axel-AI
GitHub: https://github.com/alex-acosta-cali/Axel-AI (privado)

## 0. Estado hoy
- Piloto 2026, lado dueño.
- WhatsApp real: +57 314 5801851, Phone ID 1362796690246222. Tokens solo en `.env`.
- Demo en http://127.0.0.1:8090 expuesto con ngrok para el webhook.
- Claude Code trabaja en el repo (ejecutor; Grok revisa, Alex aprueba).
- Pruebas OK: `test_memory_cross_channel` y `test_level3_approval`.
- App de Meta sigue **En desarrollo** (no publicada).
- 28 sep: un cupo confirmado por franja (probado). Cancelar y reprogramar sueltan el cupo viejo.
- 28 sep: reembolso N3, el dueño aprueba y el cliente recibe el aviso. Probado con un segundo celular.
- 28 sep: aprobar/rechazar y comandos del dueño solo desde WA_OWNER_PHONE o el panel.
- Hosting 24/7, Instagram y modelo de lenguaje: solo notas en `docs/`. No construidos.

## 1. Visión (fija hasta que Alex apruebe cambio)
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
| KB precios | construido (corte/barba piloto) |
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
- Reservas aceptan horas fuera de las franjas (ej. 17 o 10).
- Model router no llama APIs de pago.
- “am” dentro de palabras ya no debe contar como hora (corregido en reservas).
- Git a veces deja archivos sin commit: revisar `git status` antes de parar.

## 6. Criterios del piloto actual
- N1: horario, KB, nombre, celular, correo.
- N2: cita → día/hora → confirmar; cancelar; reprogramar pregunta y luego cambia.
- N3: reembolso frena; segundo reembolso no duplica pendiente; Aprobar/Rechazar.
- Ficha visible: Alex + celular + correo.
