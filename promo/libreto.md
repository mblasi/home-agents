# Libreto — promo home-agents

Animación ASCII, narración con voz `es_AR-daniela-high` (la voz real de Capitán).
Estimado: ~75-90s. Español rioplatense (UY). Todo local-first.

Convención por escena:
- **EN PANTALLA** — qué se ve (ASCII / animación).
- **VOZ** — narración de daniela (lo que se escucha).
- **CAPTION** — texto sobreimpreso.

Leyenda de mejoras propuestas sobre tu outline: marcadas con ▶.

---

## 0. Cold open / Landing (0:00 – 0:08)

**EN PANTALLA**
Logo `home-agents` fade-in (cyan) sobre fondo oscuro. Debajo, un cursor que
escribe la tagline.

**VOZ**
> "Una red de agentes de IA, viviendo en tu casa. Sin nube. Sin que nada salga
> de tu red."

**CAPTION**
`home-agents` · tu voz · tu casa · tu red

▶ Mejora: arrancar con la promesa (privacidad + inteligencia local) antes de
mostrar arquitectura. Engancha primero, explica después.

---

## 1. Arquitectura (0:08 – 0:22)

**EN PANTALLA**
Diagrama ASCII animado. Aparecen primero los ambientes con su panel, después
el Brain, y al final las flechas de conexión (todas hacia adentro de la red):

```
   comedor        cocina        dormitorio        living
   [NSPanel]      [NSPanel]      [NSPanel]        [NSPanel]
       \             |              |               /
        \            |              |              /
         '---------> [ BRAIN · LAN local ] <------'
                     ┌───────────────────────┐
                     │  HAOS   ·  Ollama      │
                     │  qwen2.5:7b · core     │
                     └───────────────────────┘
```

Un pulso recorre las flechas de los paneles al Brain y vuelve (request/response).

**VOZ**
> "En cada ambiente, un panel te escucha. Todos hablan con el Brain: un servidor
> chico, en tu casa, que corre Home Assistant y los modelos de lenguaje. La nube
> no participa."

**CAPTION**
panel por ambiente → Brain (HAOS + Ollama) · 100% LAN

▶ Mejora: mostrar el pulso request→Brain→response refuerza visualmente que el
loop se cierra dentro de casa.

---

## 2. Los agentes (0:22 – 0:32)

**EN PANTALLA**
Montaje rápido: cada agente entra con su ícono ASCII y nombre, se alinean en
una grilla. Ritmo ágil (≈1.2s c/u), se quedan todos al final.

```
  ☀  clima        🏠 domótica      📈 inversiones
  📅 agenda        🛒 compras       🗺  mapas
```

**VOZ**
> "Adentro vive una red de agentes especializados: clima, domótica, agenda,
> inversiones, compras, mapas. Cada uno sabe lo suyo. Y colaboran entre ellos."

**CAPTION**
una red · no un asistente

▶ Mejora: cerrar con "y colaboran entre ellos" planta la semilla del caso 2 y 3
(la orquestación es el diferencial). El emoji puede caer a glifo ASCII si querés
mantener el look monocromático puro — decisión abierta (ver Decisiones).

---

## 3. Caso 1 — Domótica directa (0:32 – 0:46)

> El comando simple. Establece el patrón: wake → voice-id → pedido → acción.

**3.1 Wake word + VU-meter**
EN PANTALLA: ícono de mic, VU-meter en vivo (barras subiendo con el audio) y la
barra de score del wake word cruzando el umbral.
CAPTION: `WAKE WORD ▓▓▓▓▓▓▓░░  0.91  → Capitán`

**3.2 Voice-ID**
EN PANTALLA: tarjeta de identificación. Score de speaker, match.
CAPTION: `voice-id  ·  Matías  ✓  (0.78)`
VOZ (daniela, in-character): *(silencio — el sistema reconoce, no narra)*

**3.3 Pedido**
EN PANTALLA: typing del comando del usuario.
USUARIO: *"Capitán, prendé la luz del comedor y poné el aire en 23."*

**3.4 Domótica responde**
EN PANTALLA: agente domótica activo → la lámpara se enciende + termostato 23°.
VOZ (daniela): "Listo. Luz del comedor encendida y aire a 23 grados."
CAPTION: `light.comedor → ON · climate → 23°`

▶ Mejora: meter DOS acciones en un pedido muestra parsing multi-acción sin
alargar. El voice-id como gate (no narrado) comunica seguridad sin texto.

---

## 4. Caso 2 — Agenda + Clima colaboran (0:46 – 1:06)

> El salto: dos agentes colaboran y el sistema REPREGUNTA. Inteligencia, no obediencia.

**4.1 Wake + VU-meter** (igual al caso 1, más corto)
CAPTION: `Capitán  ▓▓▓▓▓▓▓▓░ 0.93`

**4.2 Voice-ID**
CAPTION: `voice-id · Matías ✓`

**4.3 Pedido**
USUARIO: *"Agendame una corrida para mañana a la tarde."*

**4.4 Orquestación + repregunta**
EN PANTALLA: el agente de agenda consulta al de clima (flecha entre los dos
íconos, "agenda → clima ?"). El de clima devuelve pronóstico.
```
   📅 agenda  ──pregunta──▶  ☀ clima
   ☀ clima:  mañana 16h  🌧  lluvia  ·  mañana 08h  ☀ despejado
```
VOZ (daniela): "Mañana a la tarde dan lluvia. Tenés la mañana despejada,
¿te la agendo a las ocho?"

**4.5 Confirmación y cierre**
USUARIO: *"Dale."*
EN PANTALLA: evento creado en el calendario, 08:00.
VOZ (daniela): "Listo, corrida mañana a las ocho. Te aviso si cambia el tiempo."
CAPTION: `agenda · corrida · mañana 08:00 ✓`

▶ Mejora: el "te aviso si cambia el tiempo" introduce proactividad como puente
natural al caso 3. La repregunta es el momento "wow" — darle aire (≈2s de hold).

---

## 5. Caso 3 — Goal complejo, proactividad y orquestación (1:06 – 1:32)

> El cierre fuerte: un objetivo difuso que el sistema persigue solo, en varios
> turnos y en el tiempo, coordinando varios agentes.

**5.1 Wake + VU-meter**
CAPTION: `Capitán ▓▓▓▓▓▓▓▓▓ 0.95`

**5.2 Voice-ID**
CAPTION: `voice-id · Matías ✓`

**5.3 Pedido (un goal, no un comando)**
USUARIO: *"Capitán, quiero escaparme un finde a la playa el mes que viene,
algo tranqui y que no se me dispare el presupuesto."*

EN PANTALLA: el pedido se convierte en un GOAL persistente (tarjeta "objetivo"
con estado: abierto).
CAPTION: `🎯 goal: finde playa · mes próximo · low-cost`

**5.4 Orquestación multi-agente**
EN PANTALLA: el goal dispara una cadena de consultas entre agentes (grafo que
se ilumina por pasos):
```
   🎯 goal ─┬─▶ 📅 agenda     finde libre: 18–19
            ├─▶ ☀ clima       mejor ventana: 18, soleado
            ├─▶ 🗺 mapas       2 destinos < 3h de auto
            └─▶ 📈 presupuesto estimado dentro del tope
```
VOZ (daniela): "Lo voy resolviendo. Cruzo tu agenda, el pronóstico, las rutas y
el presupuesto."

**5.5 Proactividad — vuelve después con una propuesta**
EN PANTALLA: salto temporal (reloj avanza, "más tarde"). Notificación proactiva
del sistema.
VOZ (daniela): "Te tengo algo. El finde del 18 está libre y va a estar soleado.
La Pedrera te queda a dos horas y entra en presupuesto. ¿Reservo?"
CAPTION: `propuesta proactiva · La Pedrera · 18–19 · ✓ presupuesto`

**5.6 Turno final — objetivo cumplido**
USUARIO: *"Reservá."*
EN PANTALLA: el goal pasa a "cumplido"; checklist se completa (agenda bloqueada,
recordatorio, ruta guardada).
VOZ (daniela): "Reservado. Te bloqueé la agenda y te guardé la ruta. Buen finde."
CAPTION: `🎯 goal cumplido · todo coordinado, local`

▶ Mejora: el salto temporal + notificación proactiva es lo que ningún asistente
de comando-respuesta hace. Es el clímax: el sistema trabaja por vos mientras no
estás. Mantener el grafo de orquestación legible (máx 4 ramas).

---

## 6. Cierre (1:32 – 1:40)

**EN PANTALLA**
Los íconos de los agentes colapsan de nuevo en el logo `home-agents`.

**VOZ**
> "Una red de agentes que entiende, coordina y se adelanta. En tu casa. Tuya."

**CAPTION**
`home-agents` · tu voz · tu casa · tu red
`nada sale de tu red local`

---

## Decisiones cerradas

1. **Íconos** — ✅ **con emojis** (☀🏠📅📈🛒🗺). Color + lectura rápida.
   ⚠ Técnico: el render PIL necesita fuente de emoji color (Noto Color Emoji);
   si no, los emojis caen a tofu. Verificar/instalar antes de animar (ver abajo).
2. **Voz** — ✅ **dos voces TTS**. Narrador: `es_AR-daniela-high`.
   Usuario: `es_ES-davefx-medium` (ya instalada). Diálogo real, requiere sync
   por escena.
3. **Versiones** — ✅ **full ~90s** (landing/web) + **corte 30s** (caso 1 +
   clímax caso 3) para redes.

## Decisiones abiertas (menores)

4. **Destino del caso 3** — "La Pedrera" (UY). Cambiable.
5. **Idioma** — es-UY. ¿Versión en inglés para difusión? (postergable)

## Nota técnica de build (emojis) — RESUELTO

Usar **`Noto Emoji` monocromático** (`/usr/share/fonts/noto-emoji/NotoEmoji-*.ttf`),
no el color. Glifos de un solo color → se **tiñen con la paleta** (☀ yellow,
🏠 cyan, 📅 blue, 📈 green, 🛒 orange, 🗺 magenta) y **caben en la grilla
monospace**. Mantiene el look terminal y no rompe layout. El render carga dos
fuentes: DejaVuSansMono (texto/arte) + NotoEmoji (glifos de agente).
