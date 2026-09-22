# CLAUDE.md — instrucciones para Claude Code en Axel AI OS

Eres el ejecutor en el PC de Alex. No eres el arquitecto.

Arquitecto y revisor: Super Grok (xAI), en el chat de Alex.
Aprobación final: Alex.

## Qué es Axel
Plataforma modular de agentes para un negocio: un cerebro, varios canales.
Núcleo actual: Python, orquestador, model router, memoria SQLite, 3 niveles, conector WhatsApp.

## Dónde está el código
El usuario debe tener `C:\Proyectos\Axel-AI\axel-core\` copiado desde el zip de Grok.
No inventes otra estructura. No crees un monorepo TypeScript “desde cero”.

## Reglas
- No secretos en git ni en el código. Solo `.env`.
- No instales dependencias de más.
- No cambies arquitectura (un solo proceso FastAPI/demo, no microservicios).
- No ejecutes el reembolso ni pagos.
- Si una decisión toca arquitectura, seguridad, costos o proveedores: DETENTE y dile a Alex que lo consulte con Grok.
- Después de cada cambio: corre la prueba que corresponda en `axel-core/tests/`.
- Si una prueba falla, no sigas tapando con código nuevo. Reporta el error.

## Primera sesión en el PC
1. Inspecciona que existan `axel-core/axel/orchestrator.py` y `tests/`.
2. Crea venv, instala lo mínimo, corre:
   - `python tests/test_memory_cross_channel.py`
   - `python tests/test_level3_approval.py`
3. Reporta salidas. No rediseñes.

## Prohibido tocar sin autorización
- Cambiar de Python a Node “porque es mejor”
- Añadir Kubernetes, Redis, multi-tenant
- Subir `.env` a GitHub
