# Cuaderno AXEL — hasta 24 sep 2026 (tarde, Cali)

Profesor: Super Grok (Fast/Auto). Expert solo para diseño grande.  
Alumno: Alex. PC: `C:\Proyectos\Axel-AI`  
GitHub privado: https://github.com/alex-acosta-cali/Axel-AI  
Último commit visto: `e8f0d18` + commits de CRM nombre/celular/ficha (locales; confirmar `git log -5`).

## Cómo trabajamos (para no malgastar Grok)
- Un ladrillo por mensaje. Archivo **completo**, no “cambia la línea 7”.
- Ritual: pegar → Ctrl+S → **reiniciar** `python -m axel.demo` → probar panel → `git add` + `commit` + `push`.
- Nunca pegar `>>` ni dos comandos pegados (`python -m axel.demoSet-Location`).
- Expert saturado ≠ se acabó Super Grok. Sigue en Fast/Auto.
- Skills de AXEL (orquestador, permisos, CRM, agenda, etc.) ya están en Grok. No se crea una skill nueva en cada Enter. Se usa la que toca. Claude Pro no es obligatorio.

## Qué es AXEL hoy (puedes explicarlo)
Sistema local en Python: mensaje → orquestador → memoria CRM → permisos 1/2/3 → agente → auditoría → panel en `http://127.0.0.1:8090`.  
No es WhatsApp todavía. Es el cerebro.

## Lo que SÍ está (probado en tu PC)
| Pieza | Evidencia |
|--------|-----------|
| Repo + Git local + GitHub privado | `alex-acosta-cali/Axel-AI` |
| Demo HTTP 8090 | health + panel |
| FAQ `kb.json` | horario 8:00–19:00 |
| Nivel 1 | horario, nombre, celular |
| Nivel 2 reserva | `quiero una cita` → día/hora → confirmado |
| Nivel 3 reembolso | no ejecuta; Aprobar/Rechazar en panel |
| Contexto de reserva | “mañana a las 10” sigue la cita |
| CRM | `me llamo Alex` + celular 10 dígitos |
| Ficha en panel | Nombre Alex · celular · cus_… |
| Citas confirmadas | tabla en el panel |
| Escritura local | `rembolso` ≈ `reembolso`; sin tildes |

## Lo que NO está
- WhatsApp Cloud API (Meta: portafolio bloqueado por restricción de ads en las cuentas probadas; página “Axel ai” es de cuenta familiar = **préstamo**. Migrar a cuenta de Alex ~octubre).
- Servidor 24/7, HTTPS, ngrok.
- Model router llamando APIs de pago.
- Agenda real (hoy anota texto, no cupos).
- Factura, marketing, voz, Instagram.

## Decisiones
- Nombre del producto: **AXEL AI OS** (no Quantum).
- Grok = arquitecto; Claude Code instalado, sin Pro aún.
- Cuentas Meta de familiares = solo piloto, no producción.
- Lo no listado en `permissions.py` = nivel 3. Por eso `datos` tuvo que entrar como nivel 1.

## Ritual de arranque cada día
1. `Set-Location C:\Proyectos\Axel-AI\axel-core`
2. `$env:PYTHONPATH = "."`
3. `python -m axel.demo`
4. Chrome: http://127.0.0.1:8090/
5. Frase a Grok: `Sigo Axel. PC C:\Proyectos\Axel-AI. Panel 8090 ok. GitHub alex-acosta-cali/Axel-AI. Meta pausado. Siguiente ladrillo.`

## Próximos ladrillos (orden)
1. Correo en la ficha (`mi correo es …`).
2. Un pendiente N3 por cliente+intent (no 5 reembolsos).
3. Cancelar cita (`cancelar la cita`).
4. Actualizar `AXEL_STATE.md` y este cuaderno en Git.
5. Meta otra vez **solo** con cuenta de Alex cuando se libere.
6. Túnel HTTPS (Cloudflare/ngrok) cuando haya WABA de prueba.
7. Primer mensaje WhatsApp = tú contra el número de prueba.

Tiempo honesto: cerebro local **ya existe**. Primer WhatsApp real = días o semanas según Meta, no según código.
