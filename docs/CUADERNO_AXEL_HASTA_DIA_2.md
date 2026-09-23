# Cuaderno del alumno — AXEL AI OS
De cero hasta el Día 2 (23 sep 2026, ~01:20 Cali)

Profesor: Super Grok  
Alumno: Alex Acosta  
Máquina: Windows, usuario `Usuario`  
Carpeta real del proyecto: `C:\Proyectos\Axel-AI`

Este archivo sirve para **leer, entender y explicar** qué estamos construyendo.  
No es un tutorial de 200 herramientas. Es lo que **ya te pasó a ti**.

---

## 1. En una frase

AXEL AI OS es un **sistema operativo para un negocio pequeño**: recibe mensajes, recuerda al cliente, decide qué puede hacer solo y qué no, responde, y deja rastro.

No es “un ChatGPT con WhatsApp”.  
La inteligencia es **una pieza**. El sistema es el resto.

---

## 2. Por qué existe (la idea que casi nadie aplica)

La mayoría hace esto:

```
idea → “IA, hazme la app” → 20 mil líneas → no corre en mi PC → se abandona
```

Nosotros hacemos esto:

```
pensar → especificar → un paso pequeño → probar en TU disco → guardar con Git → siguiente paso
```

Si el código solo vive en un chat, no tienes producto. Tienes una conversación.  
Por eso el Día 1 no fue WhatsApp: fue **pasar Axel a `C:\Proyectos\Axel-AI`**.

---

## 3. Cómo se parte el trabajo (equipo)

| Quién | Rol | Qué no es |
|-------|-----|-----------|
| Tú | Dueño. Haces clic. Apruebas. | No tienes que memorizar 70 mil comandos |
| Super Grok (este chat) | Arquitecto + profesor + revisor | No está instalado “dentro” de tu carpeta |
| Claude Code (`claude` en PowerShell) | Puede editar archivos **en tu disco** | El chat de claude.ai **no** ve tu PC |
| ChatGPT | Ya no está en el equipo | No hace falta Plus para seguir |

**Claude Pro:** no lo compres todavía.  
Lo vas a necesitar cuando te canse pegar parches a mano. Hoy Grok + terminal alcanzan.

**Opción 2 de Claude (“Console API”):** no. Cobra aparte por token. Es la forma cara de aprender.

---

## 4. Arquitectura (dibujo que debes poder explicar)

```
Mensaje (hoy: una prueba HTTP en tu PC)
        ↓
   Conector (más adelante: WhatsApp de Meta)
        ↓
   SOBRE INTERNO  (event_id, canal, texto, cliente…)
        ↓
   ORQUESTADOR
        ├─ identifica al cliente (memoria)
        ├─ mira historial
        ├─ clasifica intención (saludo, reserva, reembolso…)
        ├─ elige AGENTE (atención, reservas, escalamiento)
        ├─ consulta PERMISOS → nivel 1 / 2 / 3
        ├─ consulta MODEL ROUTER → qué modelo usaría
        ├─ el agente responde (o se detiene)
        └─ AUDITORÍA (qué pasó, por qué, con qué modelo)
        ↓
   Respuesta
```

Un cerebro. Varios canales después.  
No queremos cinco chatbots distintos.

### Los 3 niveles (esto es el corazón ético y de negocio)

| Nivel | Qué hace AXEL | Ejemplo |
|-------|----------------|---------|
| 1 | Ejecuta | “¿Cuál es el horario?” |
| 2 | Propone y espera el sí del cliente | Reservar una cita |
| 3 | **No ejecuta.** Avisa al dueño | Reembolso, queja grave |

Si no está en la tabla → se trata como nivel 3.  
Así un agente no “se inventa” permiso para mover dinero.

---

## 5. Qué hay hoy en tu PC (mapa físico)

```
C:\Proyectos\Axel-AI\
│
├── AXEL_STATE.md          cerebro del proyecto (estados, decisiones)
├── AXEL_PLAN_GROK.md      plan cuando Grok tomó el mando
├── AXEL_M01_Arquitectura.md
├── AXEL_M05_WhatsApp.md   guía Meta (aún no conectada)
├── CLAUDE.md              reglas para Claude Code
├── .gitignore             para que Git no suba .env, .venv, ni .db
├── .git\                  historial local (commit 1b5be45 = Día 1)
│
└── axel-core\             EL PROGRAMA
    ├── kb.json            preguntas frecuentes del piloto
    ├── .env.example       nombres de secretos, sin secretos
    ├── axel\
    │   ├── orchestrator.py    el cerebro
    │   ├── router_model.py    elige modelo (aún no llama APIs de pago)
    │   ├── memory.py          clientes, historial, audit (SQLite)
    │   ├── permissions.py     niveles 1/2/3
    │   ├── notify.py          aviso al dueño en nivel 3
    │   ├── demo.py            servidor HTTP local puerto 8090
    │   ├── main.py            versión FastAPI (para más adelante)
    │   ├── knowledge_base.py  lee kb.json
    │   ├── agents\            atencion, reservas, escalamiento
    │   └── connectors\        whatsapp.py (código listo, Meta no)
    └── tests\
        ├── test_memory_cross_channel.py
        └── test_level3_approval.py
```

**GitHub** todavía no. El historial está solo en tu disco. Eso ya es Git. GitHub es la copia en internet.

---

## 6. Palabras que ya usaste (sin humo)

**Terminal / PowerShell**  
Ventana donde le hablas a Windows con texto. El Explorador es para ver carpetas; PowerShell es para **hacer**.

**PATH**  
Lista de carpetas donde Windows busca programas. Si `python` o `claude` “no se reconoce”, casi nunca es que “no existe”: es que no está en esa lista.

**Python**  
El idioma del núcleo. Lo instalamos de python.org, no de la Tienda. La Tienda deja un atajo falso.

**pip**  
Instala librerías de Python (`pydantic`, `httpx`).

**venv (`.venv`)**  
Caja de herramientas solo para este proyecto. Evita mezclar Axel con otros programas.

**PYTHONPATH=.**  
Le dice a Python: “el paquete `axel` está en esta carpeta”.

**Git**  
Máquina del tiempo. `commit` = foto con etiqueta.  
El Día 1 quedó: `1b5be45` — *nucleo Axel en el PC. Pruebas OK.*

**.gitignore**  
Lista de lo que Git no debe fotografiar: contraseñas (`.env`), la caja `.venv`, bases `.db`.

**HTTP**  
Idioma con el que se hablan programas por red.  
`GET /health` = “¿sigues vivo?”  
`POST /webhooks/test` = “toma este mensaje”.  
Meta (WhatsApp) un día hará un POST parecido a una URL pública. Hoy lo simulamos en `127.0.0.1` (tu propia máquina).

**JSON**  
Texto con forma de datos: `{"text":"hola"}`.  
PowerShell **rompe las comillas** si las pegas en la misma línea. Por eso el truco del archivo `axel.json` + `curl.exe --data-binary`.

**SQLite / `axel.db`**  
Base de datos en un archivo. Primera versión de la memoria.  
Si el archivo es viejo (sin columna `business_id`), se borra y se crea de nuevo. En piloto eso es legal.

**Webhook**  
“Cuando pase X, llama a esta URL”. WhatsApp no espera que Axel pregunte: **empujará** el mensaje a tu servidor.

**Orquestador**  
El único jefe de tráfico. Evita que atención y ventas contesten el mismo mensaje.

**Model router**  
Hoy solo **elige el nombre** del modelo (`grok-fast`, `grok-standard`). Todavía no cobra tokens de API. Está ahí para no casarnos con un solo proveedor.

---

## 7. Diario de lo que SÍ hicimos

### Antes de sentarte al PC (en el celular, con Grok)

- Se definieron 29 “skills” (instrucciones de cómo debe comportarse cada agente). Eso vive en Grok, no hace falta en el PC.
- Se diseñó el plano: un solo servicio Python, no un enjambre de microservicios.
- Se escribió el núcleo y se probaron M2–M4 **en un servidor de Grok**, no en tu disco.
- Confusión importante que ya aclaramos: “el módulo está OK” significaba **probado allá**. Hasta copiar el zip, **en tu casa no existía**.

### Día 1 — el taller

1. El PC no tenía Python real, ni Git, ni `claude` en la terminal.
2. Apagamos el alias de la Tienda (`python.exe` / `python3.exe`).
3. Instalamos Python 3.13.15 (con “Add to PATH”) y Git 2.55.
4. Creamos `C:\Proyectos\Axel-AI` y extraímos `AXEL_core_y_docs.zip`.
5. Vimos `orchestrator.py` en tu disco.
6. Corrieron **en tu máquina**:
   - Misma persona por WhatsApp simulado e Instagram simulado → **mismo** `customer_id`.
   - “Quiero un reembolso” → nivel 3, **no ejecuta**, avisa al dueño.
7. `git init` + primer commit `1b5be45`.
8. Windows bloqueaba scripts; pusiste ExecutionPolicy `RemoteSigned` para tu usuario.

### Día 2 — el puente HTTP

1. `claude --version` → `2.1.280`. Eso **sí** es Claude Code (no el chat web).
2. Arrancamos `python -m axel.demo` → escucha en `http://127.0.0.1:8090`.
   Esa ventana **no se usa para escribir comandos**. Es el servidor. El cursor parado es normal.
3. `GET /health` funcionó desde el primer intento.
4. Los POST fallaban por dos motivos, ya vistos:
   - Base vieja sin `business_id` → se borró `axel.db`.
   - PowerShell destrozaba el JSON → se mandó un archivo.
5. Prueba que **sí** cerró el Día 2:

```
reply_text: Atendemos de lunes a sábado, 9:00 a 18:00.
customer_id: cus_8b205159e3
event_id: evt_74fa561734bd
agent: atencion
supervision_level: 1
model: grok-fast
```

Eso es Axel atendiendo un mensaje **como si** viniera de un canal, dentro de tu casa, sin internet de Meta.

---

## 8. Cómo explicarlo en 40 segundos (si te preguntan)

“Estoy construyendo AXEL, un sistema para que un negocio atienda clientes con reglas. No es solo un chatbot. En mi PC ya corre un cerebro en Python: recibe un mensaje, busca al cliente, mira si puede actuar solo o tiene que parar, responde con una base de conocimiento y deja un registro. Hoy lo probé en local. WhatsApp real es el siguiente puente, con la API oficial de Meta, no con trucos.”

---

## 9. Qué NO está hecho (para no mentir)

- WhatsApp no está conectado a tu número.
- No hay servidor 24/7 ni dominio HTTPS.
- El model router no llama a Grok/Claude de pago todavía.
- Claude Code está instalado, pero **no lo usamos como obrero** esta noche (y no pagamos Pro).
- GitHub remoto no existe.
- No hay facturación, voz, Instagram real, ni multi-negocio.

Mentir sobre el avance es la forma más rápida de hundir el proyecto.

---

## 10. Cómo seguir estudiando (método)

Cada bloque:

1. Yo te digo **un** comando o un clic.
2. Tú lo ejecutas.
3. Pegas **solo** la salida nueva.
4. Si hay error, no improvises diez cosas: una causa.
5. Cuando algo queda verde, se escribe en este cuaderno o en `docs/DIA_XX.md`.
6. Git cuando hay cambio de archivos (no hace falta commit si solo probamos).

Tres niveles de esfuerzo (tokens y dinero):

- A — “qué significa este error de Windows”
- B — un parche o un webhook
- C — cambiar arquitectura o pagar un proveedor

No uses C para preguntar qué es `cd`.

---

## 11. Dónde vamos (secuencia real, no fantasía)

1. **Hecho:** taller + núcleo + pruebas + HTTP local.  
2. **Siguiente:** cuenta Meta Business + app WhatsApp + número de **prueba** + tu celular en la lista.  
3. Luego: URL HTTPS (túnel o VPS) para que Meta llame a Axel.  
4. Luego: tú le escribes al número de prueba y Axel responde con `kb.json`.  
5. Recién ahí hay “primer cliente real = tú”.

Las aprobaciones de Meta pueden tardar días. Se inician en paralelo; el desarrollo no se detiene.

---

## 12. Criterio de “voy bien”

Vas bien si puedes decir, sin leer:

- Dónde está el código.
- Qué hace el orquestador.
- Qué es nivel 3.
- Por qué no subimos `.env`.
- Qué comprobó el JSON del horario.

Si eso lo puedes explicar, no eres un espectador. Estás dirigiendo el sistema.
