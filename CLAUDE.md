# CLAUDE.md — home-agents

Red de agentes de IA local-first para domótica, clima, agenda, inversiones y viajes.
Todo corre en la laptop. Nada sale de la red local.

## Dashboard — política de actualización

Al implementar cualquier tarea del plan que introduzca datos o estados nuevos
(conversaciones, agentes, fuentes, latencias, entidades, etc.), evaluar si tiene
sentido reflejarlo en el dashboard zellij (`ear/dashboard.kdl`).

Paneles existentes y su rol:
- `panel_score.py`   — wake word score animado + estado del agente (listening/recording/etc.)
- `panel_history.py` — historial de comandos con acción, respuesta y latencias
- `panel_latency.py` — latencias STT/LLM/HAOS promedio y por comando
- `panel_agents.py`  — panel flotante: agentes disponibles, agente activo, fuente del pedido

Los paneles leen métricas de `/tmp/capitan/*.json` escritos por `listen.py`.
Si la feature genera datos nuevos, agregar la escritura a `listen.py` y
actualizar el panel correspondiente (o crear uno nuevo si no aplica a ninguno).

---

## Flujo de trabajo por tarea

Al implementar **cada ítem del plan** (`- [ ] N.M ...`), seguir este flujo obligatorio:

1. **Crear branch** en cada submodule afectado (`core`, `ear`, o ambos):
   ```zsh
   git -C ~/workspace/home-agents/core checkout -b fase-N-M-descripcion-corta
   ```
2. **Implementar** los cambios en el branch.
3. **Commitear** con mensaje claro que referencie la tarea:
   ```zsh
   git -C ~/workspace/home-agents/core add -p
   git -C ~/workspace/home-agents/core commit -m "feat: fase N.M — descripcion"
   ```
4. **Hacer PR a main** usando `gh pr create`.
5. **Mergear** el PR (`gh pr merge --merge`).
6. **Actualizar el submodule pointer** en el repo umbrella y commitear:
   ```zsh
   git -C ~/workspace/home-agents add core   # o ear
   git -C ~/workspace/home-agents commit -m "chore: update core submodule — fase N.M"
   ```

Si la tarea afecta solo el repo umbrella (`masterplan/`, `scripts/`), el branch y PR van en `home-agents` directamente.

### Sincronización obligatoria al terminar cada tarea

Al completar cualquier ítem del plan, **siempre** hacer estas dos cosas antes de avanzar a la siguiente:

1. **Marcar `[x]` en `estado.md`** — la tarea debe quedar marcada como completada.

2. **Actualizar el `Estado:` de la FASE** — al marcar el último `[ ]` de una fase,
   cambiar `Estado: Pendiente` / `Estado: EN CURSO (...)` a `Estado: COMPLETA`.
   Si quedan ítems pendientes, actualizar el conteo (ej: `EN CURSO (6/7 — solo queda 3.4)`).
   **No usar sub-headers `#### Completado` / `#### Pendiente`** — los marcadores `[x]`/`[ ]`
   son suficientes y los sub-headers quedan desincronizados. Si existen, eliminarlos.

3. **Correr el lint de estado.md**:
   ```zsh
   python scripts/lint_estado.py
   ```
   Detecta tareas `[x]` bajo `#### Pendiente` y otras inconsistencias. Debe pasar sin errores
   antes de continuar. Si falla, corregir antes del sync de issues.

4. **Correr el sync de issues**:
   ```zsh
   source ~/home-agents-env/bin/activate
   python scripts/sync_issues.py
   ```
   Esto cierra el issue de GitHub correspondiente. Sin este paso, el proyecto de GH
   queda desincronizado con el plan.

Si se completaron varias tareas en la sesión sin sincronizar, correr el sync al final
de la sesión como mínimo. Hacer siempre `--dry-run` primero para verificar.

---

## Tests — política obligatoria

Los tests viven en `core/tests/`. Se ejecutan con:
```zsh
source ~/home-agents-env/bin/activate
cd ~/workspace/home-agents/core
python -m pytest tests/ -q
```

**Regla estricta: cualquier modificación o corrección de funcionalidad en `core/` requiere actualizar o generar los tests correspondientes antes de commitear.**

Criterios:
- **Nueva función o clase** → agregar tests unitarios que cubran el comportamiento documentado.
- **Modificación de lógica** → actualizar los tests existentes que dependen de esa lógica.
- **Corrección de bug** → agregar un test que reproduzca el bug antes del fix y pase después.
- **Nueva dependencia externa** (HTTP, filesystem) → mockear con `unittest.mock.patch` o `monkeypatch`.

Archivos de test existentes:
- `test_ha_client.py` — `_load_env`, `_load_haos_config`, `get_state`, `call_service`, `ENTITIES`
- `test_agent_parse.py` — `_parse_all`, `_compose_response`, `_haos_error_message`
- `test_agent_mocked.py` — `HaosAgent.process`, `_ask_and_parse`, overrides del registry
- `test_agent_registry.py` — `dispatch`, `get_registry`, `get_fancy_display`, `write_active_agent`
- `test_conversations.py` — `ConversationManager`, `is_close_phrase`, `is_acknowledgment`
- `test_users.py` — CRUD de usuarios, documentos, `expiring_documents`
- `test_rbac.py` — `allowed`, `set_role_agents`, permisos por rol
- `test_intent_state.py` — ciclo de vida de intents, `get_pending_request`, `get_needs_reminder`

Convenciones:
- Usar `monkeypatch` o `patch.dict(sys.modules, ...)` para aislar filesystem y HTTP.
- No parchear `ha_client.requests.post` y `agent.requests.post` en simultáneo — apuntan al mismo módulo `requests`; parchear `ha_client.call_service` directamente en su lugar.
- Módulos con `import X as _x` local (dentro de una función) requieren `patch.dict(sys.modules, {"X": mock})`.
- Los tests no deben hacer llamadas reales a Ollama, HAOS ni al filesystem del usuario.

---

## Documentación obligatoria

Cada vez que se agregue o corrija funcionalidad, **antes de cerrar la sesión**:

1. **`masterplan/estado.md`** — reflejar la tarea completa con `[x]` y actualizar el estado de fase.

2. **`README.md` (raíz y submodules afectados)** — mantener consistente con el estado real del sistema:
   - Agentes activos vs. planificados
   - Endpoints disponibles
   - Arquitectura actualizada

3. **`masterplan/arquitectura_funcional.md`** — documento funcional detallado del sistema. Actualizar la sección correspondiente cuando cambie:
   - Un agente (nuevo, modificado, activado)
   - El ciclo de vida de intents o goals
   - El sistema proactivo
   - Endpoints de la API
   - El backoffice

**Regla:** si se modificó código, se debe actualizar documentación. No es opcional.
Un hook de Stop en `.claude/settings.local.json` recuerda esto automáticamente.

---

## Plan y estado

El plan vive en `masterplan/estado.md`. Al iniciar sesión, leerlo para saber en qué fase
estamos y cuál es el próximo paso. Las tareas completadas tienen issues cerrados en GitHub;
las pendientes tienen issues abiertos en https://github.com/mblasi/home-agents.

Para sincronizar estado del plan con los issues de GitHub:
```
python scripts/sync_issues.py           # aplica cambios
python scripts/sync_issues.py --dry-run # solo muestra qué haría
```

**Fuente de verdad: `estado.md` → GitHub, nunca al revés.**
El script lee el plan y ajusta GitHub para que coincida: `- [x]` cierra el issue,
`- [ ]` lo reabre. Nunca leer el estado de GitHub para modificar el plan.
Agregar tareas nuevas: primero en `estado.md`, luego crear el issue en GH con
`gh issue create`, y finalmente registrar el número en `masterplan/issues.yaml`.

## Hardware

```
CPU:  AMD Ryzen 9 5900HX — 8 cores / 16 threads — znver3
GPU:  Radeon Vega 8 integrada — comparte RAM — NO útil para ML
RAM:  64GB DDR4
OS:   Gentoo Linux — GCC 15.2.1 znver3 — kernel x86_64
```

Toda la inferencia corre en CPU con cuantización int8. No intentar usar la GPU.

## Entorno Python

```zsh
source ~/home-agents-env/bin/activate   # siempre activar antes de correr cualquier script
```

- Python 3.13.12, pip 26.0.1, uv 0.11.8
- El venv está en `~/home-agents-env`, NO en el repo
- `pyyaml` está instalado en el venv

## Audio — restricciones críticas

La placa ALC256 **no soporta 16kHz**. Solo acepta 44100Hz y 48000Hz.

```
Captura:    pyaudio, device_index=4 (HD-Audio Generic: ALC256 Analog hw:1,0)
Frecuencia: 44100Hz → resamplear a 16000Hz con scipy.signal.resample_poly
Ratio:      up=160, down=441
```

Reproducción de WAV: usar **ffplay**, no aplay.
```zsh
ffplay -autoexit -nodisp archivo.wav
```
`aplay` falla sin parámetros explícitos de formato con este hardware.

## Stack de inferencia

### Ollama
```
Servicio:   localhost:11434
Versión:    0.20.3 (vulkan + AVX2 + FMA3 + F16C)
Modelo:     qwen2.5:7b  ← MODELO PRINCIPAL (3.5s warm, formato ACTION correcto)
Descartados: phi3:mini (24.8s), phi3-ha (inventa entity_ids)
```

### faster-whisper
```
Modelo:  small (cache HuggingFace)
Device:  cpu, compute_type=int8, language=es
Latencia: ~4.6s para 5s de audio
```

### Piper TTS
```
Binario: ~/.local/bin/piper/piper  (v1.2.0)
Voces:   ~/.local/share/piper/
  es_AR-daniela-high.onnx    ← voz del agente (wake word + respuestas)
  es_MX-claude-high.onnx     ← descartada
  es_ES-davefx-medium.onnx   ← descartada
  es_ES-sharvard-medium.onnx ← diversidad en training
Sample rate: 22050Hz
```

### openWakeWord
```
Repo:   ~/workspace/home-agents/ear/wakeword/openWakeWord/
Data:   ~/workspace/home-agents/ear/wakeword/data/capitán/positive/  (90 samples WAV, voz daniela)
        ~/workspace/home-agents/ear/wakeword/data/capitán/negative/
Wake word objetivo: "Capitán"
```

Parche aplicado (no revertir):
`acoustics/directivity.py` — `sph_harm` → `sph_harm_y` (scipy 1.17.1 / Python 3.13)

## Home Assistant OS (HAOS)

```
Acceso:    http://192.168.68.101:8123
Estrategia: HAOS solo recibe órdenes via REST API
            Todo el procesamiento (STT/LLM/TTS) corre en la laptop
Token:     en core/.env (excluido del repo)
Cliente:   core/ha_client.py — get_state / call_service / ENTITIES map
```

## Estructura del repo

```
home-agents/              ← repo umbrella (este repo)
├── ear/                  ← submodule: github.com/mblasi/home-agents-ear
│   ├── listen.py         loop principal: wake word → STT → HTTP/core → TTS
│   ├── tts.py            Piper TTS → ffplay (voz daniela)
│   ├── panel_*.py        paneles Rich para zellij dashboard
│   ├── dashboard.sh/kdl  lanzador del dashboard interactivo
│   ├── run.sh            wrapper para systemd
│   ├── capitan.service   unit file (instalar en ~/.config/systemd/user/)
│   └── wakeword/         datos de training y submodule openWakeWord
│
├── core/                 ← submodule: github.com/mblasi/home-agents-core
│   ├── server.py         FastAPI en :8765 — POST /process, GET /agents, GET /health
│   ├── agent.py          texto → qwen2.5:7b → parse ACTION → ha_client
│   ├── agent_registry.py dispatcher + REGISTRY de agentes
│   ├── ha_client.py      cliente REST HAOS + mapa de entidades
│   └── capitan-core.service  unit file para el servidor
│
├── masterplan/
│   ├── estado.md         plan completo con estado, latencias y decisiones
│   └── issues.yaml       mapeo task_id → GitHub issue number
│
├── scripts/
│   └── sync_issues.py    sincroniza estado.md con GitHub issues
│
└── interagent/           concepto del producto Interagent (red de redes de agentes)
```

## Configuración (.env)

Cada submodule tiene su propio `.env` (gitignored):

**`core/.env`**:
```
HAOS_URL=http://192.168.68.101:8123
HAOS_TOKEN=eyJ...
OLLAMA_URL=http://localhost:11434
CORE_PORT=8765
```

**`ear/.env`**:
```
CORE_URL=http://localhost:8765
CORE_TIMEOUT=30
```

## Comandos frecuentes

```zsh
# Activar entorno
source ~/home-agents-env/bin/activate

# Correr el core (debe estar antes que ear)
cd ~/workspace/home-agents/core
uvicorn server:app --host 127.0.0.1 --port 8765

# Correr el agente (pipeline completo)
bash ~/workspace/home-agents/ear/dashboard.sh          # dashboard interactivo
systemctl --user start capitan-core     # core como servicio
systemctl --user start capitan          # ear como servicio
systemctl --user stop capitan-core
systemctl --user stop capitan
journalctl --user -u capitan -f         # logs ear
journalctl --user -u capitan-core -f    # logs core

# Test del core
curl http://localhost:8765/health
curl -X POST http://localhost:8765/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"prende la luz"}'

# Debug wake word scores en tiempo real
python ~/workspace/home-agents/ear/wakeword/debug_scores.py

# Test TTS
python ~/workspace/home-agents/ear/tts.py

# Test parser LLM + HA (directo, sin servidor)
python ~/workspace/home-agents/core/agent.py

# Sync issues con GitHub
python scripts/sync_issues.py

# Actualizar submodules
git submodule update --remote
```

## Pipeline actual

```
[MIC hw:1,0 44100Hz]          ← ear/listen.py
    ↓ scipy resample_poly up=160 down=441
[16000Hz]
    ↓ faster-whisper small int8 cpu          ~4.6s
[texto]
    ↓ HTTP POST :8765/process              ~10ms overhead
[core/server.py]
    ↓ qwen2.5:7b Ollama :11434               ~3.5s
[ACTION: domain.service | entity_id: X]
    ↓ parser
[HAOS REST API :8123]
    ↓ HTTP response
[ear/listen.py]
    ↓ Piper TTS respuesta → ffplay

Latencia warm: ~8s | Latencia cold: ~15.7s
```

## Decisiones tomadas (no reabrir)

- LLM: qwen2.5:7b (phi3 descartado)
- STT: faster-whisper sobre openai-whisper
- Wake word: training propio con openWakeWord (Porcupine descartado)
- Reproducción: ffplay (aplay descartado)
- Arquitectura: todo en laptop, HAOS solo recibe REST
- Resampling: scipy.signal.resample_poly (no librosa, más rápido)
- Voz TTS: es_AR-daniela-high (claude y davefx descartadas)
- Comunicación ear↔core: HTTP REST en localhost:8765 (no IPC — permite múltiples ears)
