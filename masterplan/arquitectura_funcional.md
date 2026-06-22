# Arquitectura Funcional — home-agents

Documento de referencia funcional del sistema. Se actualiza con cada cambio de funcionalidad.

_Última actualización: 2026-06-11_

---

## Visión general

home-agents es una red de agentes de IA que corre en el **Brain** (Beelink SER9 Pro — Ryzen AI 7, Proxmox VE; core + backoffice + WA + audio_server en un LXC, HAOS en una VM, Ollama con GPU ROCm). La laptop quedó como entorno de desarrollo. No hay dependencias de servicios externos de pago ni telemetría; el perímetro de red es la LAN local. Los nodos de voz son NSPanel Pro.

El sistema combina tres capacidades:

1. **Reactiva** — responde a comandos de voz o WhatsApp en tiempo real
2. **Proactiva** — cada agente monitorea su historial y detecta patrones autónomamente
3. **Orientada a objetivos** — los goals de largo plazo se revisan periódicamente y se avanza sobre ellos

---

## Componentes del sistema

### ear (home-agents-ear) — capa de audio

Arquitectura distribuida: **nodos** (NSPanel Pro) capturan el wake word y graban el comando;
el **audio_server** (en el Brain, co-ubicado con el core) hace STT/TTS y resuelve voice-id.
El nodo es agnóstico al usuario: solo graba y manda audio crudo.

| Archivo | Función |
|---------|---------|
| `satellite.py` | Nodo NSPanel: wake word (openWakeWord) → graba comando → POST /process-audio → reproduce respuesta. Duck de volumen (18.2), pull del modelo (16.17), enrollment inline (16.21). |
| `satellite_ui.py` | Indicador visual overlay (Termux:GUI): barra de estado del pipeline (18.3) + VU-meter de wake word de N leds discretos (un overlay por led, tono fijo rojo→verde, encendido bottom-up por score). |
| `audio_server.py` | FastAPI `:8766` en el Brain: STT (faster-whisper) + TTS (Piper) + voice-id (speaker_id) + canal de enrollment + registry de nodos. |
| `speaker_id.py` | Voice-ID por embeddings (resemblyzer/GE2E). Perfiles en `embeddings/<uid>.npy`. |
| `tts.py` | Piper TTS (voz `es_AR-daniela-high`). |
| `listen.py` | Pipeline local de la laptop (DEPRECADO — reemplazado por satellite+audio_server). |
| `wakeword/` | Training data + modelo openWakeWord "Capitán" (ONNX). |

**Pipeline de audio (nodo → server):**
```
[NSPanel] mic → openWakeWord → graba COMMAND_SECS → POST /process-audio (WAV)
   [audio_server Brain] → normaliza RMS → faster-whisper (vad+confianza) → strip wake word
       → voice-id: speaker_id.identify → gate REQUIRE_KNOWN_SPEAKER (TV/guest → 204)
       → POST core /process → respuesta → Piper TTS → WAV
[NSPanel] reproduce WAV. Falsos positivos (STT vacío / agent unknown+guest) → 204 + hard negative.
```

**Voice-ID (server-side, 16.18-16.20):** identifica quién habló comparando con perfiles enrolados.
CRÍTICO: el embedding debe enrolarse con el MISMO mic (re-enroll desde el nodo). Gate
`REQUIRE_KNOWN_SPEAKER` + `SPEAKER_THRESHOLD` descarta el TV. Validación: `/verify-voice` (16.28).
Ante una voz no enrolada, el gate sintetiza `UNKNOWN_VOICE_REPLY` (default `"Voz desconocida."`)
en vez de un `204` mudo, para dar feedback; vacío conserva el `204` silencioso.

**Canal de enrollment backoffice→nodo (16.21):** el backoffice deja una orden pendiente
(`POST /nodes/{id}/enroll` type wakeword|voice|verify); el satellite la consume en su loop,
graba inline (usando el stream del mic, evita conflicto OpenSLES) y reporta progreso.

**Endpoints del audio_server:** `POST /process-audio`, `GET /nodes`, `GET|POST /nodes/{id}/enroll*`,
`POST /enroll-sample` (wake word), `POST /enroll-voice`, `POST /verify-voice`, `GET /wakeword/negatives`,
`GET /wakeword/model[/version]` (propagación a nodos, 16.17).

**Registro de paneles:** tabla `panels` en SQLite (name/room/ip/node_id/users/area_id/config, FASE 32).
Alta/provisioning: `scripts/nspanel.sh provision` o backoffice `/panels`.

**Configuración por panel (FASE 38):** cada panel tiene una `config` JSON (columna `panels.config`,
fuente de verdad en core) administrable desde **ambos backoffices**. Claves iniciales (allow-list,
extensible): `screen_timeout_secs` (segundos de inactividad para apagar la pantalla; `0` = nunca) y
`default_dashboard` (deeplink de HA Companion que abre el panel). El **satélite hace PULL** de su
config —mismo patrón que el auto-update de código/modelo— y la aplica en el dispositivo: el apagado
de pantalla con el ajuste nativo de Android (`settings put system screen_off_timeout`, vía `su`) y
el dashboard con `am start -d <url>`. Flujo: el backoffice (local) o el comando `panel.config` (cloud,
egress-only) upsertan la config en core y marcan el nodo en `audio_server` (`POST /nodes/{id}/config-changed`);
el próximo heartbeat (~30s) lleva `config_update: true` y el satélite consulta `GET /nodes/{id}/config`
(proxy de `core /panels/config/{node_id}` + versión md5) y reaplica sólo si cambió. Sin el flag,
converge igual en el ciclo de sync (`MODEL_SYNC_SECS`) y al arrancar. El selector de dashboard se
puebla desde `GET /dashboards` (core consulta los dashboards de lovelace por WebSocket
`lovelace/dashboards/list`, no expuesto en la REST API; cacheado). El satélite es el **único
aplicador** del dashboard (no se toca `start-ha.sh`, que reescribe `nspanel.sh converge`).
El form se **prellena con la config REAL del dispositivo** (38.7): el satélite lee su
`screen_off_timeout` vigente (`settings get`) y reporta su config aplicada en el heartbeat
(`dev_screen_timeout_secs`/`dev_dashboard`); `audio_server` la expone en `/nodes` como
`device_config` y viaja en el snapshot. Ambos backoffices prefieren ese valor (estado real) sobre
la config guardada en core, así el admin ve lo que efectivamente corre en el panel.

**Ambientes (16.7):** la fuente de verdad de los ambientes son las **áreas de Home Assistant**
(`ha_client.get_areas()` vía `/api/template`, porque el area registry no está en la REST API de
estados). El core las expone en `GET /areas` y `GET /rooms` (áreas + augmentación local del
`media_player`/Echo + paneles bindeados); el backoffice `/rooms` edita el Echo por área y `/panels`
bindea cada panel a un `area_id`. Endpoints core: `GET /areas`, `GET|POST /rooms`, `DELETE /rooms/{area_id}`.

**Latencia warm:** ~5s (STT + LLM con GPU ROCm + TTS).

---

### core (home-agents-core) — capa de orquestación

FastAPI en `:8765`. Recibe texto de cualquier cliente y lo pasa por el pipeline de agentes.

#### Ciclo de vida de un request

```
POST /process {text, source, conversation_id?}
    ↓
1. Identificar usuario (desde source.wa_phone o usuario por defecto)
2. Resolver/crear conversación
3. Coordinator.plan(text, user, conversation)
   a. fast_classifier: keyword matching sin LLM (< 10ms)
   b. Si no hay match claro: qwen2.5:7b genera ExecutionPlan
      ExecutionPlan = [Step(agent_id, query, depends_on?), ...]
4. _run_plan():
   - Para cada step en orden (respetando depends_on):
     _build_agent_prefix(user, agent_id)
       → contexto de usuario + intents activos + goals activos + rutinas activas
     agent.process(query, conversation, source, user)
     → (response, action?, updates?)
     - updates.intent_updates  → intent_state
     - updates.goal_updates    → goal_store
     - updates.context_updates → user_context
     - updates.routine_updates → routine_store  ← nuevo
     - Registrar en agent_history
5. Sintetizar respuesta final
6. Actualizar conversación y trazas
```

#### Auditoría del flujo de ejecución — cortocircuitos y elección de agente (FASE 40.1)

**Principio rector:** la elección de agente debe ser SIEMPRE producto de la planeación del LLM
(coordinador) sobre `(prompt del usuario + AgentCards disponibles)`. El uso de un agente es
*orgánico y eventual*, nunca prefijado. Está PROHIBIDO cualquier corte determinista pre-coordinador
que **decida el agente** o sesgue el routing. Los únicos cortes admisibles antes del LLM son
housekeeping de canal verdaderamente agnóstico (cierre/ack) que **no eligen agente**.

Mapa real de puntos donde se elige o se puentea el agente, end-to-end. Cada punto marcado
**[AGNÓSTICO]** (no decide agente / housekeeping puro) o **[NO-AGNÓSTICO]** (viola el principio).

**Path voz/web — `server.py:process` (POST /process):**

| # | Punto | file:line | Veredicto |
|---|-------|-----------|-----------|
| 3  | Frase de cierre → cierra conversación, responde "Hasta luego." | `server.py:599` (`is_close_phrase`, `conversations.py:48`) | **[AGNÓSTICO]** housekeeping de canal — no elige agente. Riesgo: falso positivo si una frase de comando contiene un substring de cierre (`_CLOSE_PHRASES` se matchea por `in`, no por igualdad). |
| 3b | Ack/confirmación → ignora en silencio | `server.py:608` (`is_acknowledgment`, `conversations.py:53`) | **[AGNÓSTICO]** match por igualdad estricta contra `_ACK_WORDS`. No elige agente. Riesgo menor de falso positivo. |
| 3c | **Captura de request intent** → el texto del usuario se trata como la respuesta a un request pendiente y se rutea al agente dueño (`handle_captured_reply`) | `server.py:615-632` | **[NO-AGNÓSTICO]** — **el bug central de la fase.** Decide el agente (el dueño del request) sin pasar por el coordinador, sólo porque existe un request pendiente. |
| 4  | **fast_classifier** fast-path: clasificador entrenado elige agente sin LLM | `coordinator.py:206-223` | **[NO-AGNÓSTICO en intención, atenuado]** elige agente sin el planner, pero gateado por `not conv_context` + `conf >= CLASSIFIER_THRESHOLD` y entrenado de ejemplos del propio routing. Es una *aproximación barata del planner*, no un bias hacia un agente fijo. Falta guard de ambigüedad/umbral más explícito. |
| 4b | fast_classifier fallback ante excepción del LLM | `coordinator.py:279-297` | **[AGNÓSTICO degradado]** sólo se usa cuando el planner falló; mejor que devolver `unknown`. |
| 5  | Agregación multi-step | `_run_plan` (server.py) | **[AGNÓSTICO]** sintetiza resultados de agentes ya elegidos por el plan; no elige agente. |

**Causa raíz del 3c (hijack cross-canal):** `get_pending_request` (`intent_state.py:224-235`)
matchea CUALQUIER conversación cuando el intent no tiene `conversation_id`:

```python
# intent_state.py:231-234
# Si tiene conversation_id, debe coincidir; si no tiene, aplica a cualquiera
if e.get("conversation_id") and e["conversation_id"] != conversation_id:
    continue
return e
```

Los request proactivos de finanzas se crean SIN `conversation_id` (`finance_agent.py:485-498` →
`proactive.py:_persist_proactive_item:711` → `intent_state.upsert(conversation_id=item.get("conversation_id"))`
= `None`). Resultado: un request pendiente de finanzas captura el siguiente enunciado de
cualquier canal/conversación —p.ej. "¿cómo está el clima?"— como su respuesta, lo pasa por
`handle_captured_reply` con `_is_affirmative("¿cómo está el clima?") = False` y devuelve
"Entendido, el plan 'X' queda sin cambios" (`finance_agent.py:521`). El clima nunca llega al
planner.

Además, el 3c **no verifica que la conversación esté esperando esa respuesta**: ignora el
`ContinuationState` (FASE 36, `conversations.py:68`), que es el mecanismo correcto para saber si
un exchange espera la próxima respuesta del usuario (`conv.is_waiting`, `kind=field|clarification|reply`).

**Path WhatsApp — `server.py:wa_inbound` (POST /wa/inbound):**

| # | Punto | file:line | Veredicto |
|---|-------|-----------|-----------|
| W1 | Intercept `CAPITAN_OAUTH:` | `server.py:920` | **[AGNÓSTICO]** mensaje de sistema, no comando. |
| W2 | Ack con `intent_id` → cierra el intent | `server.py:925` | **[AGNÓSTICO]** housekeeping. |
| W3 | Captura de request con `intent_id` (quoted-reply) | `server.py:937-938` (`get_request_by_id`) | **[NO-AGNÓSTICO acotado]** dirigido explícitamente por el usuario a ESE intent (reply citado) → match estricto por id, sin agarrar el primer pendiente. Aceptable: hay intención explícita del usuario. |
| W4 | Captura de request sin `intent_id` (fallback por conversación) | `server.py:940` (`get_pending_request`) | **[NO-AGNÓSTICO]** mismo bug que 3c: cae al match laxo por conversación. |

**Conclusión de la auditoría:** los cortes 3c (voz) y W4 (WhatsApp) violan el principio rector —
deciden agente por precedencia dura sobre la existencia de un request pendiente, agravado por el
match laxo de `get_pending_request`. El fast_classifier (4) es una aproximación del planner, no un
bias, pero necesita guard de ambigüedad. Cierre (3) y ack (3b) son housekeeping pero deben acotarse
para no dispararse sobre comandos reales. Las etapas B–E de FASE 40 corrigen en ese orden.

**Etapa B — fix del secuestro de captura (40.2/40.3, resuelto).** `get_pending_request`
(`intent_state.py`) pasa a **match estricto** por `conversation_id`: un request sin
`conversation_id` (o de otra conversación) ya no matchea — muere el hijack cross-canal. Las
capturas 3c (`server.py`) y W4 (`wa_inbound`) sólo proceden si la conversación está **esperando un
reply** (`ContinuationState.kind == "reply"`, FASE 36) y limpian la continuación al capturar. Los
request proactivos **sellan su `conversation_id` al entregarse** (`proactive._seal_request_to_wa_conversation`
fija el id de la conversación canónica de WhatsApp y la marca a la espera del reply); los reactivos
lo sellan al `conversation_id` del turno (`apply_agent_updates`). La pregunta "¿esto es la respuesta
o un comando nuevo dentro de la MISMA conversación?" queda para la Etapa C (40.4).

#### Persistencia de datos (SQLite — FASE 32)

Toda la data del sistema vive en **`~/.local/share/capitan/capitan.db`** (SQLite) vía
`core/db.py`. Tablas normalizadas para `users` y `panels`; el resto (conversations, intents,
goals, routines, plan_events, portfolios, finance_templates, user_context, agent_history,
tokens, agent_config, finance_news, ml_prices, feriados) en una tabla genérica `documents(kind,
key, data)`. Migración con `scripts/migrate_to_db.py` (idempotente). Las menciones por-módulo a
archivos `.json` más abajo describen el **modelo lógico**; físicamente son filas/documentos en
la DB. Quedan como archivos por diseño: embeddings `.npy`, traces JSONL, sesión de WhatsApp,
samples de audio, y `panels.yaml` (config del repo leída por backoffice/scripts).

#### Watchdog de HAOS y alertas (FASE 8.28)

La **detección y recuperación** de HAOS caído las hace un watchdog **externo** en el SER9
(`ha-watchdog.timer`, cada 60s): chequea `:8123`, y ante fallos sostenidos escala
`ha core restart` (3 fallos) → `qm reset 100` (6 fallos). Cubre el caso "core colgado pero
vivo" que el supervisor de HAOS no agarra. El core sólo aporta el **canal de notificación**:
el hook del watchdog (`ha-watchdog-notify`) hace `POST /alerts/haos` con el evento
(`down|restarted|reset|recovered`) y el core avisa a los **admins por WhatsApp** (usuarios
`role=admin` con `wa_phone`, + `HAOS_ALERT_PHONE` override; token opcional `X-Alert-Token`),
persistiendo el evento en `metrics_store.haos_health_events`. Health-check propio:
`ha_client.ping()` y `GET /health/haos` (`{up}`). No hay loop de ping dentro del core: la
detección vive en el watchdog para no duplicarla.

### cloud (backoffice en la nube) — FASE 33

Backoffice accesible desde internet **sin exponer el Brain ni HAOS**, con principio
egress-only: la nube nunca inicia conexiones hacia la casa. Patrón command/executor por
inversión de control.

- **Servicio** (`cloud/`, Cloud Run + Firestore, scale-to-zero): endpoints del bridge
  (`/ingest/state`, `/commands/pending` con claim atómico, `/commands/{id}/result`) y API
  del dashboard (`/api/state|commands|catalog`, emisión). Login Firebase Auth (Google) con
  allow-list por email; rate limiting por identidad + límite de payload.
- **Bridge** (`cloud/bridge/`, daemon systemd en el LXC): empuja el snapshot de estado y
  polea la cola de comandos — **sólo conexiones salientes**. Reusa datos de core/audio_server.
  Executor seguro: cada tipo del catálogo tipado → función concreta (sin shell). Auth por ID
  token OIDC de una Service Account sin roles de proyecto (permiso mínimo absoluto).
- **Seguridad**: secretos y PII nunca cruzan a la nube (allow-list de campos en el snapshot);
  comandos tipados y cerrados; reglas Firestore deny-all de cliente.
- **Failover**: si la nube cae, el core sigue local y el bridge reintenta con backoff; si el
  bridge cae, el backoffice local en LAN (`:8080`, FASE 12) sigue operando.
- **Login consistente + RBAC** (Etapa E): el login del dashboard se valida contra los usuarios
  reales (roster email→rol que el bridge materializa desde la DB). RBAC por rol: admin ve todo y
  emite comandos; familiar read-only; adolescente read-only vista básica (sin PII/auditoría);
  resto sin acceso. El backoffice **local** reusa este mismo login vía SSO (la nube emite un
  token HMAC firmado tras el Google sign-in y redirige al `:8080`), con sesión por usuario y
  RBAC (admin escribe; familiar/adolescente read-only). `BACKOFFICE_TOKEN` queda como
  bootstrap de emergencia offline. Identidad de login = `User.email` (o `gcal_email`).

**SPA con sidebar + secciones (FASE 37).** El dashboard cloud pasó de una página única con
tarjetas apiladas a un **SPA con sidebar** (taxonomía del backoffice local: Monitoreo / Sistema
/ Administración), router client-side por hash y cada link/vista gated por capacidad. Secciones:
Resumen, Servicios, Métricas, Alertas, Logs, Actividad, Agentes, Wake word, Paneles, Deploy,
Usuarios, Acciones, Auditoría. **Mobile-first**: la sidebar colapsa a drawer en viewport chico,
las tablas anchas scrollean dentro de su card (el acceso remoto es típicamente desde el celular).

- **RBAC ampliado**: nueva capacidad `view_pii` (admin-only, distinta de `view_full`). Sin ella,
  `filter_state` redacta el **contenido** (texto de comandos en `recent_commands`) dejando la
  metadata y los conteos. El snapshot sólo lleva conteos de intents/goals/rutinas/conversaciones
  (nunca el contenido), más `alerts` (texto, vía `/alerts/recent` no-consumible del core) y
  `wakeword.status`.
- **UI de comandos final-user (37.5/37.6)**: se eliminó el `<select>` + JSON crudo. Acciones
  contextuales junto a la entidad (reiniciar servicio, activar/desactivar y correr agente,
  reiniciar panel, reentrenar wake word) con confirmación en destructivos y feedback inline del
  estado; y un formulario tipado para comandos sin entidad-ancla, con widgets renderizados desde
  la metadata de presentación de `/api/catalog` (enum→dropdown, int→número, bool→toggle,
  node/user/agent→selector). Comandos de operación nuevos en el catálogo: `agent.toggle`,
  `panel.reboot`, `proactive.run`, `logs.satellite`.
- **Logs del satélite (37.10)**: `audio_server` es la fuente única del fetch del log del panel
  (`GET /nodes/{id}/satellite-log`, ssh a Termux); el backoffice local lo llama directo (LAN) y el
  cloud vía el comando `logs.satellite` → bridge. Sin duplicar la lógica.
- **Observabilidad de detección (37.11/37.12)**: serie temporal del **score de wake word** vs
  threshold (el satélite reporta los frames `>= SCORE_LOG_MIN` → `audio_server` → core
  `ww_scores`) y del **voice-id** (`speaker_conf` known/guest vs `SPEAKER_THRESHOLD`), con charts
  en Métricas de ambos backoffices (view_full). Viajan por el push de métricas egress-only.

Contrato y modelo de amenazas: `masterplan/fase33_cloud_backoffice.md`. Paridad de secciones y
detalle de FASE 37: `masterplan/estado.md`.

---

## Agentes

### haos — Domótica

- **Archivo:** `agent.py`
- **LLM prompt:** genera `ACTION: domain.service | entity_id: X [| param: value]`
- **Entidades mapeadas:** 13 entity IDs (luces WiZ, aire Midea, persiana, zonas de riego Rachio, TV Samsung, Echo, llaves de agua/patio/garaje)
- **Contexto de área (16.33):** resuelve el área del panel que originó el comando (binding panel→área de 16.7) y trae nombre+entidades del área (`ha_client.get_area_info`); inyecta la ubicación en el prompt para desambiguar comandos sin lugar explícito (ej. "apagá el televisor" → el TV del ambiente del panel; el del living vs el del cuarto).
- **Config HAOS:** `ha_client` lee `HAOS_URL`/`HAOS_TOKEN` del doc store SQLite (`agent_config/haos`, FASE 32), con fallback a `agents.json`/`.env`.
- **Proactivo:** detecta patrones de uso (olvidó apagar, horario habitual, etc.)

### clima — Clima

- **Archivo:** `clima_agent.py`
- **Fuente:** Open-Meteo API (sin API key)
- **Funciones:** temperatura, lluvia, viento, forecast, alertas meteorológicas
- **Proactivo:** detecta si va a llover y recomienda cerrar persianas o llevar paraguas
- **Contexto de usuario:** `preferred_location` → resuelve coordenadas vía `geocoding.py`

### calendar — Agenda

- **Archivo:** `calendar_agent.py`
- **Fuente:** Google Calendar (único backend) vía protocolo CalDAV con App Password. Se apunta
  directo a la URL del calendario primario del usuario (sin `.principal()`). Radicale removido.
- **Funciones:** consultar eventos, crear recordatorios, alerta de eventos próximos
- **Proactivo:** detecta eventos del día siguiente, feriados (sync desde FERIADOS_COUNTRY=UY)

### finance — Inversiones

- **Archivo:** `finance_agent.py`
- **Fuentes:** BCRA (dólar oficial, blue, MEP), Yahoo Finance, MercadoLibre cotizaciones
- **Funciones:** dólar actual, portfolio de inversiones, alertas de precio, planes de inversión por perfil de riesgo
- **Perfil de riesgo:** conservador / moderado / agresivo — guardado en `user_context` vía tag `[PROFILE:...]`. Informa al LLM en cada conversación. Configurable desde el backoffice o por voz.
- **Proactivo — dos capas:**
  - `_strategic_checks()` (hardcodeado): detecta si el usuario no tiene perfil → intent de configuración; tiene perfil pero no tiene planes → intent de creación; P&L ponderada de algún plan cae bajo umbral del perfil → intent + notify WA.
  - `proactive_check()` override: llama `_strategic_checks()` + `super().proactive_check()` (LLM sobre historial de conversación). Sin perfil, omite el escaneo LLM. `proactive_system_prompt` específico para finanzas.
  - Intervalo: 3600s (cada 1h). Alertas reactivas de precios van por `alerts()` (cada 15min), sin duplicación.
- **Reporte P&L horario por WA:** `finance_alerts._send_portfolio_pnl_hourly_wa()` — se llama desde `check()` (cada 15min, cooldown configurable por usuario). Por cada usuario con planes y `wa_phone`, envía: P&L del día (`intraday_pct` = `change_pct` de `get_quote()`) y P&L acumulada desde creación. Emojis: 🚀 si total ≥ umbral up, ⚠️ si total ≤ umbral down, 📈/📉 para el resto. Se omite si toda la P&L < 0.05%. `portfolio.calculate_plan_pnl()` incluye `intraday_pct` en cada row.
- **Todas las alertas por usuario:** `finance_alerts._get_user_alert_config(uid)` reemplaza `_get_user_pnl_config` y devuelve los 7 umbrales: `dollar_gap_pct`, `btc_move_pct`, `stock_move_pct`, `briefing_hour`, `plan_pnl_up_pct`, `plan_pnl_down_pct`, `plan_pnl_hours`. `check()` itera por usuario en todas las reglas; cooldown keys incluyen `uid`. Los 7 campos son editables desde backoffice (sección Contexto de finanzas). Defaults globales configurables en `.env`.
- **Histograma P&L planes:** `portfolio.get_plan_pnl_history(plan)` → `(series, trend)`. `series`: lista `{date, pnl_pct}` con P&L ponderada diaria desde `created_at` hasta hoy (precios vía `finance_client.get_history_range()`, cacheado 1h). `trend`: regresión lineal con `slope_per_day`, `projection_30d`, `r2` y `points` (histórico ajustado + 30d proyección). Endpoint `GET /finance/plans/{uid}/history?plan=NAME`. Backoffice: sección "Evolución P&L" en `/users/{uid}` con Chart.js 4 (línea por plan, toggle individual, línea punteada tendencia/proyección).
- **Templates de planes:** `portfolio.py` mantiene un CRUD de templates persistentes (`finance_templates.json`). Cada template tiene `name`, `positions` (ticker:pct) y `review_threshold`. Al primer `proactive_check` sin planes, `create_plans_from_templates()` crea uno por template faltante (silencioso, sin intents). CRUD en backoffice `/finance/templates`. REST: `GET/POST /finance/templates`, `DELETE /finance/templates/{name}`.
- **RAG de noticias:** `finance_news.py` — scraping RSS Yahoo Finance por ticker, embeddings con `nomic-embed-text` (Ollama), búsqueda semántica cosine (numpy), fallback keyword si Ollama no responde. Índice persistido en `~/.local/share/capitan/finance_news_index.json` (TTL 30min). Las noticias más relevantes a la query del usuario se inyectan al system prompt del LLM. El refresh corre en background thread tanto en `process()` como en `alerts()`, por lo que el índice se mantiene fresco independientemente de la interacción del usuario. — físicamente en SQLite (`capitan.db`, FASE 32).
- **Companion:** `finance_alerts.py` para alertas reactivas de precio y P&L horario, `portfolio.py` para portfolio + templates, `finance_news.py` para RAG de noticias

### travel — Viajes

- **Archivo:** `travel_agent.py`
- **Fuentes:** documentos del usuario (pasaporte, DNI, visas), weather del destino
- **Funciones:** vencimiento de documentos, itinerario, clima en destino
- **Proactivo:** alerta de documentos próximos a vencer, clima en destinos de viajes próximos
- **Companion:** `travel_alerts.py`, `media_store.py` para documentos

### maps — Mapas

- **Archivo:** `maps_agent.py`
- **Fuente:** Open-Meteo Geocoding API
- **Funciones:** geocoding de ciudades, distancias, direcciones

### ml — MercadoLibre

- **Archivo:** `ml_agent.py`
- **Fuente:** MercadoLibre API (OAuth 2.0)
- **Funciones:** búsqueda de productos, tracking de precio, comparación
- **Auth:** `ml_auth.py` + `marketplace_oauth.py` — OAuth flow completo

### profile — Perfil

- **Archivo:** `profile_agent.py`
- **Función:** onboarding de usuario nuevo, consulta/actualización de preferencias, contexto
- **Proactivo:** detecta preferencias no configuradas, sugiere completar perfil

### system — Sistema

- **Archivo:** `system_agent.py`
- **Función:** health check, estado de agentes, latencias, diagnósticos

### user_mgmt — Gestión de usuarios

- **Archivo:** `user_mgmt_agent.py`
- **Función:** CRUD de usuarios, asignación de roles, enrollment de voz

---

## BackendCard — scoring y ejemplos por acción

`backend_router.py` registra dos tipos de estadísticas por agente:

- **AgentCard** (`record_agent_outcome`): estadísticas a nivel agente — `total_calls`, `successes`, `failures`, `learned_examples` (frases que llegaron al agente y tuvieron éxito, usadas por el coordinator).
- **BackendCard** (`record_action_outcome`): estadísticas por acción discreta dentro del agente — `action_stats[action_id]` con contadores y `action_examples` (frases que dispararon esa acción con éxito).

Los `learned_examples` de cada AgentCard se incorporan al catálogo del coordinator (vía `get_registry()`) y al `fast_classifier`, mejorando el ruteo con el uso real del sistema.

### Patrones de implementación

Los agentes se dividen en tres patrones según cómo seleccionan acciones internas:

**Patrón A — BackendCard completo** (`select_action()` + `record_action_outcome()`):
El agente llama a `select_action(text, _ACTIONS, model)` que usa el LLM para elegir entre sus `BackendCard`s. Luego registra el outcome de la acción elegida.
- **Agentes:** `calendar_agent`, `ml_agent`, `maps_agent`

**Patrón B — BackendCard híbrido** (clasificación nativa LLM + `record_action_outcome()`):
El LLM resuelve la acción junto con los parámetros en una sola llamada (prompt de clasificación directo). El agente registra `record_action_outcome(agent_id, act, text, success)` en cada rama de su `process()`.
- **Agentes:** `profile_agent`, `system_agent`, `user_mgmt_agent`

**Patrón C — Sin BackendCard** (espacio LLM continuo):
El agente no tiene acciones discretas seleccionables — la respuesta emerge directamente del LLM con contexto de dominio. Solo se registra `record_agent_outcome()` a nivel agente (desde `server.py`).
- **Agentes:** `haos` (agent.py), `clima_agent`, `finance_agent`, `travel_agent`, `generic_agent`

---

## Sistema proactivo

### ProactiveMixin

Mixin que todos los agentes heredan. Agrega:

- `proactive_schedule` — intervalo en segundos (default 86400s = 24h)
- `proactive_check(user, user_context, active_intents)` — LLM analiza `agent_history` del usuario + contexto de agentes afines, detecta patrones, retorna lista de intents a crear/actualizar
- `proactive_system_prompt` (class attr opcional) — system prompt propio para el check proactivo; si no se define, se usa el genérico del mixin

`proactive_check()` retorna vacío si no hay historial Y no hay intents activos Y no hay contexto de afines relevante.

### Afinidades entre agentes

Cada agente puede declarar relaciones de **afinidad** con otros. Durante `proactive_check`, el mixin llama a `_build_affinity_context(agent_id)` que:

1. Lee `affinities` del agente desde `agent_config` (configurable por el usuario en el backoffice)
2. Para cada agente afín, obtiene su `shared_state_prefix` (el namespace que ese agente publica en `SharedState`)
3. Llama a `SharedState.get_by_prefix(prefix)` para obtener los datos vigentes
4. Construye un bloque de texto: `"- clima (weather.*): temp=22.5, is_raining=False, conditions=Soleado"`
5. Lo inyecta al prompt del LLM entre el contexto de intents activos y el historial

Esto permite que el LLM del agente reciba datos de otros dominios sin que el agente tenga acoplamiento directo con ellos. La colaboración emerge de la configuración de afinidades y de los datos publicados en `SharedState`.

**Atributos declarables en la clase del agente:**

| Atributo | Descripción |
|---|---|
| `shared_state_prefix` | Namespace que este agente publica en SharedState (ej: `"weather"`) |
| `default_affinities` | Lista de agent_ids con afinidad por defecto (sobrescribible desde backoffice) |
| `proactive_system_prompt` | System prompt para el check proactivo (si es None, usa el genérico) |

**Agents con proactividad declarada (FASE 27):**

| Agente | prefix | default_affinities | schedule |
|---|---|---|---|
| `HaosAgent` | — | — | 86400s |
| `ClimaAgent` | `weather` | — | — (override propio) |
| `MapsAgent` | — | `["weather"]` | 3600s |
| `GenericAgent` | configurable | configurable | — |

### ProactiveScheduler

Thread en background (`proactive.py`). Loop:

```
loop cada 60s:
    para cada agente registrado:
        si (ahora - last_run) >= proactive_schedule:
            para cada usuario activo:
                agent.proactive_check(user, user_ctx)
                → aplicar intent_updates
    
    _review_goals():
        para cada goal pendiente de revisión:
            _plan_goal_steps(goal) → [{"agent_id": "...", "query": "..."}]
            para cada step:
                agent.process(query, _ReviewConv(goal_id), source_goal_review, user)
                → _apply_review_updates(updates)
            _finalize_goal_review(user, goal, results)
            → actualizar estado del goal (LLM decide si avanzar)
```

### Alert queue

`alert_queue.py` — cola de alertas proactivas pendientes de entrega. Las alertas se acumulan durante `proactive_check()` y se entregan en el próximo request del usuario (o vía WhatsApp si tiene `wa_phone` configurado).

---

## Conversaciones y continuidad

`conversations.py` — una `Conversation` agrupa los turnos de un exchange con una fuente
(voz/`ear`, WhatsApp, etc.), identificada por `source_key`. Se persiste en SQLite (doc store,
FASE 32.4) y sobrevive reinicios. `conv.context()` inyecta los últimos `MAX_TURNS` pares
usuario/asistente al LLM.

- **TTL channel-aware (36.1):** el TTL de inactividad es por canal (`CHANNEL_TTL`/
  `ttl_for_channel`): voz ~120s (síncrono), **WhatsApp 6h** (asíncrono — el usuario puede
  responder mucho después). `resume_latest(source)` reanuda la última conversación vigente
  del source en vez de crear una nueva por gap temporal.
- **Captura de respuestas y ruteo (19.4):** cuando el usuario responde a un request intent,
  si el mensaje trae `intent_id` (quoted-reply de WhatsApp) se rutea al agente **dueño de ese
  intent** (`intent_state.get_request_by_id`), evitando el cruce con el primer request
  pendiente de otro agente. Sin `intent_id`, fallback por conversación
  (`get_pending_request`).
- **Estado de continuación unificado (36.2):** `ContinuationState` (waiting/kind/prompt/field/
  agent_id) modela "esperando respuesta del usuario" como UN estado persistido en la
  conversación, vista única para todos los canales. `kind ∈ {clarification, field, reply}`.
  `pending_field` es una propiedad respaldada por él; los flags legacy (`needs_reply`,
  `is_clarification`, `pending_field`) se **derivan**; las respuestas exponen `continuation`.
- **Contexto uniforme a agentes (36.3):** el server inyecta `source["user_context"]`
  (por-agente) **siempre** que hay usuario, independiente del prefix de intents; junto con
  `conv.context()` (historial) cada agente recibe contexto consistente. Accessor:
  `base_agent.user_context_from(source)`.
- **Continuidad multi-turno en voz (36.4/36.5):** el `audio_server` propaga el
  `conversation_id` al core en cada `/process-audio` (antes se descartaba) y devuelve la
  metadata de continuación en la respuesta WAV vía headers `X-Conversation-Id` y
  `X-Needs-Reply` (derivado del `ContinuationState`). El `satellite`, ante `needs_reply`,
  **reabre el mic SIN re-disparar la wake word** (beep + grabación) threadeando el
  `conversation_id`: los turnos se encadenan (`_run_turn`) hasta que el agente deja de
  preguntar, el usuario no contesta (silencio = timeout) o se alcanza `FOLLOWUP_MAX`
  (anti-loop). Una repregunta del agente cae en contexto sin que el usuario diga "Capitán"
  de nuevo.
- **Desenlace del turno visible + feedback de STT dudoso:** `/process-audio` emite
  `X-Status` en toda respuesta (`ok | low-confidence | no-speech | unknown-voice |
  core-unknown`); el satellite lo logea en el panel (antes el motivo del 204 solo se veía
  en el audio_server del Brain). Si el STT descarta un comando por baja confianza
  (anti-alucinación) pero el voice-id reconoce al hablante, el server NO calla: sintetiza
  "no te entendí, repetí" con `needs_reply` (reabre el mic). Voz guest con STT dudoso →
  204 mudo + hard negative (probable TV). `_transcribe` devuelve `(texto, motivo)`.

> Fronteras de continuidad pendientes (FASE 36): deploy + verificación e2e en paneles (36.6),
> proactivos como turnos + reanudar conversación en WhatsApp (etapa C), saludo por sesión
> (etapa D). La sección se consolida en 36.11.

---

## Sistema de intents

### Tipos

| Tipo | Descripción | Ciclo de vida |
|------|-------------|---------------|
| `advise` | Sugerencia para el usuario | `detected → active → delivered → dismissed` |
| `request` | Pregunta proactiva que espera respuesta | `detected → pending_capture → captured \| abandoned` |
| `goal` | Objetivo de largo plazo | Ver ciclo de goals |

### Flujo de creación

Un intent se crea de tres maneras:

1. **Desde `proactive_check()`** — agente analiza historial y detecta patrón
2. **Desde `process()`** — agente retorna `intent_updates` en el tercer elemento del tuple
3. **Vía API** — `POST /users/{id}/intents`

### Captura asincrónica de información (request intent + context_key)

Un request intent puede incluir un campo `context_key` dentro de su `context`:

```python
intent_updates=[{
    "title":       "¿En qué ciudad estás?",
    "intent_type": "request",
    "question":    "¿En qué ciudad preferís que consulte el clima?",
    "context": {
        "context_key": "preferred_location",
        "ttl_days":    180,
    }
}]
```

Cuando el usuario responde (voz o WhatsApp), `server.py` llama `capture_reply()` y,
si el intent tiene `context_key`, **persiste automáticamente la respuesta en `user_context`**
del agente correspondiente (`_maybe_persist_context_from_reply()`). A partir de ese momento,
el valor estará disponible en `build_agent_prefix()` en todas las interacciones siguientes —
sin que el agente tenga que implementar ningún hook.

El hook `handle_captured_reply()` sigue disponible para casos más complejos donde el agente
necesita ejecutar una acción (no solo almacenar) en respuesta al reply.

### Persistencia

`intent_state.py` — almacena en `~/.local/share/capitan/intents_{user_id}.json`. — físicamente en SQLite (`capitan.db`, FASE 32).

---

## Sistema de goals

### Estados

```
discovered → planning → in_progress → completed
                    ↘                ↘
                  abandoned         blocked
```

### Campos

| Campo | Descripción |
|-------|-------------|
| `id` | UUID |
| `title` | Descripción corta |
| `description` | Detalle del objetivo |
| `status` | Estado actual |
| `owner_agent_id` | Agente que lo creó |
| `collaborating_agents` | Lista de agentes que participan |
| `review_interval_hours` | Cada cuántas horas revisarlo (default 6) |
| `last_reviewed_at` | Timestamp de última revisión |
| `notes` | Lista append-only de entradas de progreso |
| `children` | Sub-goals relacionados |

### Identificación de goals

Cualquier agente puede identificar un goal en dos momentos:

1. Durante `process()`: retornar `goal_updates` con `{"action": "create", "title": "...", ...}`
2. Durante `proactive_check()`: retornar intent de tipo `goal`

El **Goal Engine** (en `ProactiveScheduler._review_goals()`) revisa goals pendientes y orquesta los agentes para avanzarlos. Los nuevos intents emergentes se aplican naturalmente — no se fuerzan.

### Persistencia

`goal_store.py` — almacena en `~/.local/share/capitan/goals/{user_id}.json`. — físicamente en SQLite (`capitan.db`, FASE 32).

---

## Sistema de rutinas

Las rutinas son patrones de comportamiento **inferidos** del historial de interacciones. A diferencia de los goals (intenciones explícitas declaradas por el usuario), las rutinas son detectadas por observación repetida y se construyen iterativamente.

### Estados

```
candidate → active → paused
         ↘        ↘       ↘
          dismissed  dismissed  dismissed
```

Promoción automática `candidate → active` cuando `confidence ≥ 0.6` y `occurrence_count ≥ 3`.

### Campos principales

| Campo | Descripción |
|-------|-------------|
| `routine_id` | UUID |
| `title` | Descripción corta del patrón |
| `trigger_type` | `time` / `periodic` / `context` / `mixed` |
| `trigger_time` | Rango horario (`HH:MM-HH:MM`) o null |
| `trigger_days` | Días de la semana o [] |
| `trigger_context` | Descripción de contexto situacional o null |
| `agent_id` | Agente principal que ejecuta la acción |
| `action_template` | Descripción de la acción típica |
| `confidence` | 0.0–1.0, actualizado con EMA (30% nuevo / 70% acumulado) |
| `occurrence_count` | Número de veces observada |
| `status` | Estado actual |
| `discovered_by` | `"routine_detector"` o `agent_id` |

### Detección

`routine_detector.py` — corre en background cada 6h (configurable con `ROUTINE_DETECT_INTERVAL`).

1. Carga los mensajes del usuario (role=`user`) del historial de todos los agentes
2. Si hay menos de 6 mensajes, no intenta detectar
3. Llama a qwen2.5:7b con los últimos 40 mensajes y un prompt que pide JSON array de rutinas
4. Por cada rutina identificada:
   - Si existe una rutina con título similar (Jaccard ≥ 0.5): `record_occurrence()` → actualiza confianza y puede promover a `active`
   - Si no existe: `create_routine()` → nueva `candidate`

### Integración con agentes

Cada agente recibe las rutinas `active` del usuario en su prefijo de contexto:

```
Rutinas del usuario:
- [RUTINA] Encender luces al despertar (confianza: 85%): Lunes a viernes antes de las 8am
- [RUTINA] Consultar clima los domingos (confianza: 91%): Los domingos a la mañana
```

Los agentes pueden devolver `routine_updates` en su tuple de retorno para:
- Crear una rutina candidata nueva: `{title, description?, trigger_type?, confidence?, ...}`
- Transicionar una rutina existente: `{routine_id, status?, note?}`

#### Detección orgánica durante process()

`proactive_mixin.suggest_routine_candidate(agent_id, user_id, text, *, title, ...)` es una
función standalone que cualquier agente puede importar y llamar al final de su `process()`.
Analiza `agent_history` del par (agent_id, user_id) y retorna un dict de rutina candidata
si el texto actual tiene ≥ `min_occurrences` turnos similares previos (similitud por palabras
de contenido con longitud ≥ 4 para ignorar stopwords del español).

```python
# Ejemplo en ClimaAgent.process():
from proactive_mixin import suggest_routine_candidate

routine = suggest_routine_candidate(
    self.agent_id, user_id, text,
    title="Consulta de clima frecuente",
    description="El usuario consulta el tiempo regularmente",
)
if routine:
    return resp, action, {"routine_updates": [routine]}
return resp, action
```

Esto complementa la detección periódica de `routine_detector.py` (cada 6h, LLM completo)
con detección inmediata y liviana durante la conversación.

### Persistencia

`routine_store.py` — almacena en `~/.local/share/capitan/routines/{user_id}.json`. — físicamente en SQLite (`capitan.db`, FASE 32).

---

## Historial de agentes

`agent_history.py` — almacena los últimos 40 turnos por par (agent_id, user_id) en `~/.local/share/capitan/history_{agent_id}_{user_id}.json`. — físicamente en SQLite (`capitan.db`, FASE 32).

El historial se escribe desde `server.py` (`_record_history()`) después de cada `agent.process()` exitoso, tanto en path single-step como multi-step. Las revisiones de goals (source `goal_review`) no se registran.

---

## Contexto de usuario por agente

`user_context.py` — cada agente puede almacenar y leer un dict arbitrario por usuario. Persiste en `~/.local/share/capitan/context_{user_id}.json`. — físicamente en SQLite (`capitan.db`, FASE 32).

Ejemplo: `clima_agent` almacena `preferred_location: "Montevideo"`. En cada `proactive_check()` y `process()` recibe este contexto y resuelve coordenadas vía `geocoding.py`.

**Fuentes de escritura:**
- `agent.process()` vía `context_updates` en el dict de updates
- Automática desde la captura de un request intent con `context_key` (`_maybe_persist_context_from_reply()`)
- Directa vía `POST /users/{id}/context` (API)

---

## Shared state

`shared_state.py` — memoria compartida entre agentes con TTL. Clave-valor en memoria (no persiste entre reinicios).

Ejemplo: `clima_agent` escribe `weather.is_raining: True` (TTL 1h), y `haos_agent` puede leerlo para decidir si cerrar persianas automáticamente.

---

## Coordinator

`coordinator.py` — planificador multi-agente.

### fast_classifier

Clasificador de keywords entrenado en los ejemplos de cada agente. Si la confianza supera el umbral, despacha sin llamar al LLM (< 10ms).

Entrenado con `POST /coordinator/train`. El modelo se guarda en `~/.local/share/capitan/fast_classifier.pkl`.

### LLM planner (qwen2.5:7b)

Para requests ambiguos o multi-agente, genera:

```json
{
  "steps": [
    {"step_id": "s1", "agent_id": "clima", "query": "¿va a llover mañana?"},
    {"step_id": "s2", "agent_id": "haos", "query": "cierra las persianas", "depends_on": ["s1"]}
  ]
}
```

Los steps con `depends_on` se ejecutan en secuencia. Los independientes pueden ejecutarse en paralelo.

---

## Canal WhatsApp

`wa_audio.py` — descarga OGG de WhatsApp Business, convierte a WAV 16kHz vía ffmpeg, corre faster-whisper STT.

`wa_notifier.py` — envía mensajes de texto o notas de voz al WhatsApp del usuario (usando `wa_phone` del perfil). Usado para alertas proactivas y respuestas.

`wa_formatter.py` — formatea respuestas para WhatsApp (Markdown simplificado, sin HTML).

Números autorizados: definidos en `users.json` por `wa_phone`. Solo usuarios registrados pueden interactuar.

---

## RBAC

`rbac.py` — roles: `admin`, `familiar`, `adolescente`, `niño`, `invitado`.

Cada rol tiene permisos sobre endpoints (lectura, escritura, administración). El rol se resuelve desde el usuario identificado via `wa_phone` o speaker ID.

---

## OAuth (MercadoLibre)

`marketplace_oauth.py` + `ml_auth.py` — flujo completo OAuth 2.0.

1. `GET /auth/ml/url` → genera URL de autorización
2. Usuario completa el flow en el navegador
3. `POST /auth/ml/callback` → intercambia code por access_token + refresh_token
4. Tokens almacenados en `core/.env` o en el perfil del usuario

---

## Backoffice

FastAPI + Jinja2 en `:8080`. Interfaz web de administración.

### Funcionalidades

- **Conversaciones** — historial completo, filtros por usuario/agente/fecha
- **Traces de conversación** — árbol visual por request: coordinador, pasos LLM, llamadas HAOS/API
- **Traces proactivos** — página unificada `/traces` con dos solapas:
  - `proactive_check` — runs periódicos por agente, ordenados por fecha, paginados. Cada row incluye badges por `intent_type` detectado (advise/request/goal con conteo)
  - `goal_review` — ciclos de revisión de goals abiertos, ordenados por fecha, paginados
- **Gestión de agentes** — activar/desactivar, editar metadatos, toggle proactivo por agente. La página `/agents` renderiza inmediatamente desde `/agents-meta` (sin connectivity checks); la columna "Accesible" se carga en paralelo por fila vía HTMX a `/api/agents/{id}/reachable`.
- **Intents y goals** — por usuario, con estados y ciclo de vida
- **Rutinas** — rutinas inferidas por usuario
- **Shared State** — estado compartido entre agentes con TTL
- **Plan** — visualización de `estado.md` con progreso de fases

### Tipos de trace

| Tipo | `trace_kind` | Archivo JSONL | Clave |
|------|-------------|---------------|-------|
| Conversación | `request` | `traces/{conv_id}.jsonl` | `RequestTrace` |
| Proactive check | `proactive_check` | `traces/proactive-{agent_id}.jsonl` | `ProactiveRunTrace` |
| Goal review | `goal_review` | `traces/goal-review-{goal_id[:8]}.jsonl` | `GoalReviewTrace` |

Un `ProactiveRunTrace` agrega resultados por usuario: cada `ProactiveUserResult` tiene `raw_result` (items devueltos por el LLM) con `intent_type` por item (`advise`, `request`, `goal`). El endpoint `/proactive/traces/{agent_id}` incluye `intent_type_counts` agregado para mostrar en el listado sin leer el detalle.

---

## Observabilidad — métricas (FASE 35)

`core/metrics_store.py` centraliza en SQLite (vía `db.py`) las métricas que antes vivían sólo
en memoria, separadas de los traces (que guardan el detalle de cada request; las métricas
guardan la serie temporal agregable).

**Lado voz (FASE 35.1, implementado).** Dos tablas:

| Tabla | Contenido |
|-------|-----------|
| `voice_metrics` | Un evento por disparo de wake word: `kind` (`tp`/`fp`), `reason` del fp (`noise`/`guest`/`core_unknown`), voice-id (`speaker`, `speaker_conf`), latencias (`stt_ms`/`core_ms`/`tts_ms`/`total_ms`), `node_id`, `room`, `ts` |
| `retrain_events` | Un evento por reentrenamiento del wake word: `n_positive`/`n_negative`, `val_accuracy`, `fp_rate`, `duration_s`, `trigger`, `version`, `status` |

Flujo de ingesta: el `audio_server` (ear) emite cada evento al core con
`POST /metrics/voice/event` — fire-and-forget en thread daemon, nunca bloquea el pipeline de
audio (gateado por `METRICS_PUSH`). El reentrenamiento (`/wakeword/train`) registra su evento
directamente en el core. Complementa la vista live en memoria (`_bump_metric` → `/nodes`).

**Lado LLM (FASE 35.2, implementado).** `metrics_store.record_request_metrics` deriva, al
cerrar cada request, filas compactas y agregables desde el `RequestTrace` (FASE 24) — NO
duplica el trace. Tres tablas:

| Tabla | Grano | Contenido |
|-------|-------|-----------|
| `llm_calls` | una por llamada al LLM | `source`, `model`, `agent_id`, `latency_ms`, `prompt_tokens`, `completion_tokens` |
| `agent_steps` | una por step de agente | `agent_id`, `success`, `latency_ms`, `n_tool_calls`, `n_api_calls` |
| `request_metrics` | una por request | `total_latency_ms`, `coordinator_ms`, `fast_classifier_used` (fallback), `all_success`, `unknown` |

Los tokens se capturan de la respuesta de Ollama (`prompt_eval_count`/`eval_count`) en
`LLMCall` y en los sitios principales (coordinator, `agent._ask_llm`, `agent_loop`,
`generic_agent`, `backend_router`); donde no se capturan quedan `NULL` y el agregador
reporta `calls_with_tokens`. `server` hookea `record_request_metrics` en el mismo thread
daemon que persiste el trace.

**API de métricas (FASE 35.3).** Endpoints GET en `core`:

| Endpoint | Devuelve |
|----------|----------|
| `/metrics/voice/summary` | `voice_aggregates` |
| `/metrics/voice/series` | serie voz `{labels, series}` |
| `/metrics/voice/retrains` | `retrain_history` |
| `/metrics/llm/summary` | `request_aggregates` + `llm_aggregates` |
| `/metrics/llm/by-model` | latencia y tokens por modelo |
| `/metrics/llm/by-agent` | steps, tasa de aciertos, tool calls por agente |
| `/metrics/llm/series` | serie de requests `{labels, series}` |

Rango temporal por `since`/`until`/`hours`; filtros por `model`/`agent_id`/`node_id`. Las
series devuelven shape graficable `{labels, series:[{name, data}]}`. Retención configurable
con `METRICS_RETENTION_DAYS` (default 90, poda oportunista que cubre las 5 tablas).

**Dashboards (FASE 35.4/35.6).** El backoffice local sirve `/metrics` (Chart.js, tabs
Voz/LLM, filtros de rango/nodo/agente, auto-refresh); un proxy `/api/metrics/{path}` reenvía
a la API del core (mismo origen, autenticado). El backoffice cloud muestra una sección de
métricas equivalente en su dashboard, leyendo `GET /api/metrics` con RBAC (`filter_metrics`:
sin `view_full` → sólo resúmenes y series, sin detalle por modelo/agente ni reentrenamientos).

**Push al cloud (FASE 35.5, egress-only).** El bridge del Brain (FASE 33) arma agregados con
`metrics_snapshot.build_metrics_snapshot` (desde la API del core) y los empuja a
`POST /ingest/metrics` cada `METRICS_PUSH_INTERVAL` (300s), con la misma auth OIDC de la SA
y rate limiting que el resto del bridge. La nube los guarda en Firestore (`metrics/current`
+ `metrics_history` con TTL). Cero inbound a la casa.

---

## Deploy y versionado (FASE 34)

Un **motor único** (`cloud/bridge/deploy_engine.py`) corre en el Brain y concentra TODA la
lógica de deploy. Dos frontends lo invocan sin reimplementar nada: el **executor** del bridge
(remoto, comando emitido desde el cloud-bo y poleado por el Brain — egress-only, opera desde
fuera de la LAN) y `scripts/deploy.sh` (local, en la LAN).

**Modelo en tres capas.** *Repo* = unidad de versión (core, ear, umbrella; pin independiente
con `git checkout`, sin `git submodule update`). *Service* = unidad de restart/health
(core, audio_server, backoffice, wa, bridge). *Target* = unidad de operación que ve el usuario:
una lista plana (core, audio_server, backoffice, cloud-bo, un satélite por panel) en la matriz
de versiones de ambos backoffices, cada uno con la versión que corre, la última disponible
(origin/main + tag), flag `behind`, link al release de GitHub, y el comando que lo despliega.

**Flujo de release** (por repo, atómico — D7): snapshot de la versión actual → pin del ref
pedido (default origin/main) → `pip install` si cambió requirements → restart del service →
**health-gate** (`/health` con reintentos). Si el health falla, **rollback** automático: re-pin
al snapshot previo + restart; los repos sanos quedan desplegados. Tras un release sano se crea
un **tag semver** por repo (gate `DEPLOY_TAG_RELEASES`). El estado (versión por repo/service,
último release, rollback) se persiste en `~/.local/share/capitan/deploy_state.json` y un
subconjunto viaja en el snapshot a la nube.

**Targets especiales.** *cloud-bo* (Cloud Run): `gcloud run deploy --source` desde el Brain
(egress a Google) + `--to-latest`; health por curl a la URL pública; rollback a la revisión
previa (`update-traffic --to-revisions`); registra el sha de umbrella que corre en GCP.
*Satélites* (NSPanel): auto-pull cada `MODEL_SYNC_SECS` (md5 de `satellite.py`/`satellite_ui.py`
que sirve el audio_server desde su checkout de `ear`); `deploy.satellites` fuerza el pull ya,
marcando el nodo → su próximo heartbeat devuelve `update:true` → `_check_code_update()`.

Comandos tipados (validados en nube y bridge): `deploy.release`, `deploy.cloud`,
`deploy.satellites`. RBAC: sólo rol admin emite; el cloud-bo oculta la acción al resto y el
backoffice local es read-only (el deploy se opera desde la nube por el modelo egress-only).

---

## Persistencia en disco

Todos los datos del usuario se almacenan en `~/.local/share/capitan/`:

| Archivo | Contenido |
|---------|-----------|
| `users.json` | Registro de usuarios |
| `history_{agent_id}_{user_id}.json` | Historial conversacional (últimos 40 turnos) |
| `context_{user_id}.json` | Contexto por agente por usuario |
| `intents_{user_id}.json` | Intents por usuario |
| `goals/{user_id}.json` | Goals por usuario |
| `routines/{user_id}.json` | Rutinas inferidas por usuario |
| `routine_last_detect.json` | Timestamp de última detección por usuario |
| `conversations/*.json` | Conversaciones con todos sus turnos |
| `traces/{conv_id}.jsonl` | Trazas de conversación (max 100 por conv) |
| `traces/proactive-{agent_id}.jsonl` | Trazas de proactive_check por agente (max 50) |
| `traces/goal-review-{goal_id[:8]}.jsonl` | Trazas de revisión de goal (max 50) |
| `fast_classifier.pkl` | Modelo del fast-classifier del coordinator |
| `portfolio_{user_id}.json` | Portfolio de inversiones |
| `documents_{user_id}.json` | Documentos de viaje/identidad |

---

## Dashboard zellij (ear)

Paneles Rich en terminal, lanzados con `bash ear/dashboard.sh`. Leen de `/tmp/capitan/*.json` escritos por `listen.py`.

| Panel | Archivo | Contenido |
|-------|---------|-----------|
| Score | `panel_score.py` | Wake word score animado + estado del pipeline |
| Historial | `panel_history.py` | Últimos comandos con acción, respuesta y latencias |
| Latencias | `panel_latency.py` | STT/LLM/HAOS promedio y por sesión |
| Agentes | `panel_agents.py` | Agentes disponibles, agente activo, fuente del request |

---

## Hardware y modelos

| Componente | Modelo/Config |
|------------|---------------|
| CPU | AMD Ryzen 9 5900HX (znver3, 8c/16t) |
| RAM | 64GB DDR4 |
| LLM | qwen2.5:7b via Ollama (int8, CPU, ~3.5s warm) |
| STT | faster-whisper `small` (int8, CPU, ~4.6s para 5s audio) |
| TTS | Piper v1.2.0, `es_AR-daniela-high.onnx`, 22050Hz |
| Wake word | openWakeWord custom, `capitan.onnx`, threshold 0.8 + `FRAMES_REQ=2` (2 frames consecutivos, anti-transitorios) |
| Voice-id | resemblyzer (GE2E), `SPEAKER_THRESHOLD=0.65`, gate `REQUIRE_KNOWN_SPEAKER` (guest=TV se descarta) |
| Audio capture | PyAudio device_index=4 (ALC256 hw:1,0), 44100Hz |
| Resampling | scipy.signal.resample_poly up=160 down=441 |

**Loop de mejora continua del wake word:** captura automática de hard-negatives en el audio_server
(FP de TV/charla → `guest`/204 se guardan) → **retrain automático** (timer systemd en el LXC, cada 4h,
condicional a ≥20 negativos nuevos) → los nodos bajan el modelo nuevo solo cada ≤10 min (16.17).

---

## Decisiones arquitectónicas clave

| Decisión | Razón |
|----------|-------|
| CPU-only | Radeon Vega 8 comparte RAM, no útil para ML |
| ear ↔ core via HTTP | Permite múltiples ears (mic, WhatsApp) en un solo core |
| qwen2.5:7b | phi3:mini demasiado lento (24.8s), phi3-ha inventa entity_ids |
| faster-whisper sobre openai-whisper | Más rápido, mismo modelo |
| ffplay sobre aplay | aplay requiere parámetros explícitos en ALC256 |
| scipy.resample_poly sobre librosa | Más rápido, sin overhead |
| openWakeWord propio | Porcupine descartado (cloud dependency) |
| Datos en ~/.local/share/capitan/ | Fuera del repo, privados, persistentes entre reinicios |
| goal_review source type | Excluido de agent_history para no contaminar el historial de conversación |
