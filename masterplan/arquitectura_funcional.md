# Arquitectura Funcional — home-agents

Documento de referencia funcional del sistema. Se actualiza con cada cambio de funcionalidad.

_Última actualización: 2026-05-10_

---

## Visión general

home-agents es una red de agentes de IA que corre completamente en una laptop (Gentoo Linux, Ryzen 9 5900HX, 64GB RAM). No hay dependencias de servicios externos de pago ni telemetría. El único perímetro de red es la LAN local con Home Assistant OS.

El sistema combina tres capacidades:

1. **Reactiva** — responde a comandos de voz o WhatsApp en tiempo real
2. **Proactiva** — cada agente monitorea su historial y detecta patrones autónomamente
3. **Orientada a objetivos** — los goals de largo plazo se revisan periódicamente y se avanza sobre ellos

---

## Componentes del sistema

### ear (home-agents-ear) — capa de audio

| Archivo | Función |
|---------|---------|
| `listen.py` | Loop principal: captura mic → wake word → STT → POST /process → TTS |
| `tts.py` | Piper TTS + ffplay (voz `es_AR-daniela-high`) |
| `panel_score.py` | Dashboard: wake word score animado + estado |
| `panel_history.py` | Dashboard: historial de comandos |
| `panel_latency.py` | Dashboard: latencias STT/LLM/HAOS |
| `panel_agents.py` | Dashboard: agente activo y fuente |
| `wakeword/` | Training data + openWakeWord modelo "Capitán" (ONNX, 848KB) |

**Pipeline de audio:**
```
Mic hw:1,0 → pyaudio (44100Hz) → scipy.resample_poly(up=160, down=441) → 16000Hz
→ openWakeWord (threshold 0.8) → faster-whisper small int8 (~4.6s)
→ POST /process → respuesta texto → Piper TTS → ffplay
```

**Latencia warm:** ~8s | **Latencia cold:** ~15.7s

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

---

## Agentes

### haos — Domótica

- **Archivo:** `agent.py`
- **LLM prompt:** genera `ACTION: domain.service | entity_id: X [| param: value]`
- **Entidades mapeadas:** 13 entity IDs (luces WiZ, aire Midea, persiana, zonas de riego Rachio, TV Samsung, Echo, llaves de agua/patio/garaje)
- **Proactivo:** detecta patrones de uso (olvidó apagar, horario habitual, etc.)

### clima — Clima

- **Archivo:** `clima_agent.py`
- **Fuente:** Open-Meteo API (sin API key)
- **Funciones:** temperatura, lluvia, viento, forecast, alertas meteorológicas
- **Proactivo:** detecta si va a llover y recomienda cerrar persianas o llevar paraguas
- **Contexto de usuario:** `preferred_location` → resuelve coordenadas vía `geocoding.py`

### calendar — Agenda

- **Archivo:** `calendar_agent.py`
- **Fuente:** CalDAV local (Radicale)
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
- **Templates de planes:** `portfolio.py` mantiene un CRUD de templates persistentes (`finance_templates.json`). Cada template tiene `name`, `positions` (ticker:pct) y `review_threshold`. Al primer `proactive_check` sin planes, `create_plans_from_templates()` crea uno por template faltante (silencioso, sin intents). CRUD en backoffice `/finance/templates`. REST: `GET/POST /finance/templates`, `DELETE /finance/templates/{name}`.
- **RAG de noticias:** `finance_news.py` — scraping RSS Yahoo Finance por ticker, embeddings con `nomic-embed-text` (Ollama), búsqueda semántica cosine (numpy), fallback keyword si Ollama no responde. Índice persistido en `~/.local/share/capitan/finance_news_index.json` (TTL 30min). Las noticias más relevantes a la query del usuario se inyectan al system prompt del LLM. El refresh corre en background thread tanto en `process()` como en `alerts()`, por lo que el índice se mantiene fresco independientemente de la interacción del usuario.
- **Companion:** `finance_alerts.py` para alertas reactivas de precio, `portfolio.py` para portfolio + templates, `finance_news.py` para RAG de noticias

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

`intent_state.py` — almacena en `~/.local/share/capitan/intents_{user_id}.json`.

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

`goal_store.py` — almacena en `~/.local/share/capitan/goals/{user_id}.json`.

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

`routine_store.py` — almacena en `~/.local/share/capitan/routines/{user_id}.json`.

---

## Historial de agentes

`agent_history.py` — almacena los últimos 40 turnos por par (agent_id, user_id) en `~/.local/share/capitan/history_{agent_id}_{user_id}.json`.

El historial se escribe desde `server.py` (`_record_history()`) después de cada `agent.process()` exitoso, tanto en path single-step como multi-step. Las revisiones de goals (source `goal_review`) no se registran.

---

## Contexto de usuario por agente

`user_context.py` — cada agente puede almacenar y leer un dict arbitrario por usuario. Persiste en `~/.local/share/capitan/context_{user_id}.json`.

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
| Wake word | openWakeWord custom, `capitan.onnx` (848KB), threshold 0.8 |
| Audio capture | PyAudio device_index=4 (ALC256 hw:1,0), 44100Hz |
| Resampling | scipy.signal.resample_poly up=160 down=441 |

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
