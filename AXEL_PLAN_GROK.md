# AXEL AI OS — Plan nuevo (Grok lidera)
Fecha: 2026-09-21 (noche, antes de dormir)
Dueño: Alex Acosta (Cali)
Arquitecto / profesor / revisor: Super Grok
Ejecutor en el PC (opcional): Claude Code
GPT Plus: NO es necesario si Grok hace arquitectura + revisión

---

## 0. La verdad que te tenía preocupado

En este chat del celular Grok **sí corrió pruebas** de los módulos 2, 3 y 4 (y el parseo + KB del 5).

Eso ocurrió en una computadora **remota de Grok**, no en tu PC de casa.

Ruta real de los archivos **hoy**:
`/home/workdir/artifacts/axel-core/`
y documentos:
- `AXEL_STATE.md`
- `AXEL_M01_Arquitectura.md`
- `AXEL_M05_WhatsApp.md`
- `AXEL_PLAN_GROK.md` (este)
- `CLAUDE.md` (instrucciones si usas Claude Code)
- `AXEL_core_y_docs.zip` (para bajar mañana al PC)

Hasta que copies el zip a `C:\Proyectos\Axel-AI`, **en tu disco no existe Axel**.
Mañana el primer trabajo es **pasar el código a un lugar que tú controlas** y repetir las pruebas **en tu máquina**.

Eso no anula lo hecho. Anula la ilusión de que “ya está en tu PC”.

---

## 1. Equipo (sin GPT)

```
TÚ = dueño + aprobación final + quien hace clic en Windows y Meta
GROK (Super Grok) = arquitecto + mentor + revisor + quien escribe specs
CLAUDE CODE (si lo tienes) = ejecutor en el PC: copiar, instalar, test, git
```

Flujo de validación (reemplaza ChatGPT → Grok):

1. Claude Code (o tú) ejecuta la prueba en el PC.
2. Me pegas la salida (texto / error / captura).
3. Yo reviso contra criterios de aceptación.
4. **Tú** apruebas.

Si una decisión toca arquitectura, seguridad, plata o un proveedor: **se detiene y me consultas**.

### ¿Necesitas GPT Plus?
No, para este plan. Ya pagaste Super Grok para ese rol.
No compres APIs, VPS ni voz mañana.
Claude Pro solo vale si vas a usar Claude Code en el PC. Si no lo tienes, Grok + VS Code + Python alcanzan para M5.

### Qué decirle a Claude Code (si lo abres)
Pégale `CLAUDE.md` + este párrafo:

“No rediseñes Axel. No cambies la arquitectura. Copia el zip, instala Python, corre las pruebas de tests/, no pongas secretos en git. Si algo falla, no reescribas el sistema: reporta el error.”

---

## 2. Qué está realmente listo (sandbox Grok)

| Módulo | Qué es | Prueba que Grok corrió | En tu PC |
|--------|--------|-------------------------|----------|
| M00 Fundación | visión + reglas | documento | no, hay que copiar |
| M01 Arquitectura | FastAPI + 1 proceso + router | diseño | copiar md |
| M02 Núcleo | orquestador + router + sqlite | mensaje “cita mañana” → reserva nivel 2 + audit | no |
| M03 Memoria | mismo cliente 2 canales | WA + IG mismo teléfono | no |
| M04 Control | nivel 3 reembolso se detiene | pending_owner + alerta | no |
| M05 WhatsApp | conector + KB + guía Meta | parse + “horario” desde kb.json | **falta tu cuenta Meta y HTTPS** |

Skills de Grok (29): cerebro de diseño. No son el servidor.

---

## 3. Mañana — 3 horas (Día PC-1)

Objetivo: Axel vive **en tu disco** y las pruebas 2-4 salen verdes **en tu PC**.
WhatsApp real solo si sobra tiempo y Meta + túnel salen en <15 min. Si no, se deja listo y se sigue al día 2.

### 00:00–00:15 Encender
- Contraseña de administrador de Windows a mano.
- Crea `C:\Proyectos\Axel-AI`
- Abre este chat de Grok y escribe: **Estoy frente al PC. Día 1.**

### 00:15–00:45 Instalar (máx. 10 min por herramienta)
Si una se atasca: anótala y sigue.
1. Python 3.12+ (python.org) — marca “Add to PATH”
2. VS Code
3. Git
4. Cuenta GitHub (oficial, tuya)
No instales Docker mañana salvo que Python + Git ya funcionen.

Comprueba en terminal:
```
python --version
git --version
```

### 00:45–01:15 Bajar el proyecto a un lugar tuyo
1. En este chat descarga `AXEL_core_y_docs.zip`
2. Descomprime en `C:\Proyectos\Axel-AI\`
3. Debe existir `C:\Proyectos\Axel-AI\axel-core\`

### 01:15–01:30 Descanso

### 01:30–02:15 Repetir pruebas EN TU PC
```
cd C:\Proyectos\Axel-AI\axel-core
python -m venv .venv
.venv\Scripts\activate
pip install pydantic python-dotenv httpx
set PYTHONPATH=.
python tests\test_memory_cross_channel.py
python tests\test_level3_approval.py
```
(Si pip trae fastapi, también `pip install -r requirements.txt`)

Me pegas las últimas líneas. Si dicen OK, M2-M4 existen de verdad en tu casa.

### 02:15–02:40 Git (memoria que no depende de ninguna IA)
```
cd C:\Proyectos\Axel-AI
git init
git add .
git commit -m "Traer nucleo AXEL desde Grok sandbox M00-M05"
```
Crea repo vacío en GitHub (privado) y `git remote add` + `git push`.
Nunca subas `.env` con tokens.

### 02:40–03:00 Solo si las pruebas pasaron
Empieza Meta **sin gastar**:
- business.facebook.com (portafolio a tu nombre)
- developers.facebook.com app WhatsApp
- Agrega TU número a la lista de prueba
- No pagues número definitivo mañana

WhatsApp con túnel (ngrok) es Día 2 si hoy se complica.

---

## 4. Cómo te voy a enseñar (método)

Cada paso:
1. Qué es
2. Por qué
3. Clic / comando exacto
4. Tú lo haces y me pegas lo que salió
5. Si hay error: diagnosticamos, no copiamos la solución a ciegas
6. Criterio de “sí funciona”
7. Lo anotamos en AXEL_STATE.md

No copies comandos que no entiendas. Pregúntame qué es `PYTHONPATH` si no lo ves claro.

---

## 5. Lo que se hereda del plan GPT/Claude (no se pierde)

- Empresa de IA, no un chatbot suelto
- Módulos pequeños, no 20.000 líneas de un golpe
- IA es una pieza, no el sistema
- Niveles de modelo barato/normal/caro
- CLAUDE.md + DECISIONS + no secretos en git
- Verificación Meta en paralelo (cuello de botella externo)
- Límite 10 min por instalador de Windows
- Tú apruebas al final
- No cuentas compartidas de Plus/Pro

Lo que cambia:
- El arquitecto ya no es ChatGPT. Soy Grok.
- El código núcleo **ya existe** (sandbox). Mañana se **traslada y se verifica**, no se inventa de cero.
- El “Día 1 no programes Axel” de GPT queda modificado: el Día 1 es **apropiarte del núcleo que ya diseñamos aquí**.

---

## 6. Lo que NO haces mañana

- Comprar GPT Plus, VPS, Twilio, Stripe
- Abrir WhatsApp a clientes reales
- Dejar que Claude reescriba el orquestador
- Multi-tenant, Instagram, voz, facturación

Duerme. Mañana: **Estoy frente al PC. Día 1.**
