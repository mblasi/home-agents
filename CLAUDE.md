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

### Métricas persistidas y dashboards web (FASE 35)

Además del dashboard zellij (vista live efímera), hay observabilidad **persistida**:
- `core/metrics_store.py` — SQLite con métricas de voz (`voice_metrics`, `retrain_events`)
  y de LLM/agentes (`llm_calls`, `agent_steps`, `request_metrics`). Las de LLM se derivan
  de `trace_store` al cerrar cada request; las de voz las empuja el `audio_server` a
  `POST /metrics/voice/event`. API de consulta: `GET /metrics/{voice,llm}/*`.
- Dashboard web de métricas: `/metrics` en el **backoffice local** (`backoffice/templates/metrics.html`,
  Chart.js) y la sección equivalente en el **backoffice cloud** (`cloud/app/templates/dashboard.html`),
  alimentada por el push egress-only del bridge (`POST /ingest/metrics`).

Política: si una feature introduce una **métrica nueva** (latencia, tasa, contador, evento),
evaluar persistirla en `metrics_store` (no sólo en `/tmp/capitan/*.json`) y reflejarla en el
dashboard web `/metrics`, además del panel zellij que corresponda.

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
   Detecta: (a) tareas `[x]` bajo `#### Pendiente` y viceversa; (b) **el `Estado:` de cada FASE
   desincronizado con sus checkboxes** — todo `[x]` pero no COMPLETA, o avance parcial pero
   `Estado: Pendiente` (debería ser EN CURSO). COMPLETA con algún `[ ]` se permite (convención
   "COMPLETA (X postergada)"). Debe pasar sin errores antes de continuar. Si falla, corregir
   antes del sync de issues. Esto evita la deriva de marcar tareas sin actualizar el Estado de fase.

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

### Laptop (desarrollo puro — sin servicios)
```
CPU:  AMD Ryzen 9 5900HX — 8 cores / 16 threads — znver3
GPU:  Radeon Vega 8 integrada — comparte RAM — NO útil para ML
RAM:  64GB DDR4
OS:   Gentoo Linux — GCC 15.2.1 znver3 — kernel x86_64
```

La laptop NO corre servicios en producción. Solo git, editor, deploy vía SSH.

### Servidor central — Brain (Beelink SER9 Pro)
```
CPU:  AMD Ryzen AI 7 HX 255, 32GB DDR5
GPU:  Radeon 780M (RDNA 3 / gfx1103) — ROCm con HSA_OVERRIDE_GFX_VERSION=11.0.0
OS:   Proxmox VE — IP 192.168.68.99
```

Stack en Proxmox:
- VM 100: HAOS — IP 192.168.68.101 (reserva DHCP por MAC)
- LXC 101 (capitan-lxc): Ubuntu 24.04 — IP 192.168.68.132
  - core (FastAPI :8765, `0.0.0.0`)
  - backoffice (FastAPI :8080)
  - wa (Node.js whatsapp-web.js)
  - ear (servidor de audio — FASE 16, pendiente)
  - Ollama (:11434) con ROCm — 13.3s warm (vs 27.5s CPU-only)

SSH: `ssh capitan` → host PVE | `ssh capitan-lxc` → LXC Ubuntu

### Nodos distribuidos — NSPanel Pro (Sonoff)
```
SoC:      Rockchip PX30 (quad-core ARM Cortex-A35)
Android:  8.1.0 AOSP — firmware eWeLink 3.7.0
Audio:    codec RK809 — pcmC0D0c (mic) + pcmC0D0p (parlante) — sounddevice/PortAudio OK
ADB:      over WiFi puerto 5555 — root disponible
Termux:   instalado — Python 3.13, sounddevice, portaudio
SSH:      Termux sshd en puerto 8022
Dashboard: HA Companion App (minimal) — usuario HA por panel → default dashboard por ambiente
IP actual: 192.168.68.113 (comedor)
```

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
# Activar entorno (laptop)
source ~/home-agents-env/bin/activate

# Deploy al Brain (desde laptop, tras mergear PR a main)
bash scripts/deploy.sh           # actualiza core + backoffice
bash scripts/deploy.sh --restart-wa  # incluye WA

# Logs en Brain
ssh capitan-lxc "journalctl --user -u capitan-core -f"
ssh capitan-lxc "journalctl --user -u capitan-backoffice -f"
ssh capitan-lxc "journalctl --user -u capitan-wa -f"

# Test del core en Brain
curl http://192.168.68.132:8765/health
curl -X POST http://192.168.68.132:8765/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"prende la luz"}'

# Servicios en Brain
ssh capitan-lxc "systemctl --user status capitan-core capitan-backoffice capitan-wa"
ssh capitan-lxc "systemctl --user restart capitan-core"

# NSPanel Pro
bash scripts/nspanel.sh connect       # conectar ADB
bash scripts/nspanel.sh ssh           # abrir shell Termux
bash scripts/nspanel.sh status        # ver estado

# Sync issues con GitHub
python scripts/sync_issues.py

# Actualizar submodules
git submodule update --remote
```

## Deploy (FASE 34 — motor único + matriz de targets)

Existe UN motor de deploy (`cloud/bridge/deploy_engine.py`) que corre en el Brain y es el
único backend: snapshot → pin de ref → install → restart → health-gate → rollback → tag.
Lo invocan dos frontends sin reimplementar nada:
- **Remoto** — el backoffice **cloud** emite un comando, el bridge del Brain lo polea y lo
  ejecuta (egress-only; sirve desde fuera de la LAN). Es la vía principal.
- **Local** — `scripts/deploy.sh` (mismo motor por SSH) cuando se opera desde la LAN.

**Matriz de targets** (operatoria, 34.15): ambos backoffices (`/dashboard` cloud, `/deploy`
local) muestran UNA fila por cosa que corre — core, audio_server, backoffice, cloud-bo, y un
satélite por panel — con la versión que corre, la última disponible, link al release de GitHub
y (en el cloud, rol admin) un botón "Actualizar" que elige el comando solo. `wa`/`bridge` en
"avanzado". El cloud-bo opera el deploy; el backoffice local es read-only (egress-only).

Comandos: `deploy.release {services?, *_ref?}` (services del Brain), `deploy.cloud` (cloud-bo
en GCP, build `gcloud run deploy --source` desde el Brain), `deploy.satellites {node_id?}`
(fuerza el pull de un panel o todos vía la respuesta del heartbeat). Detalle en
`cloud/bridge/README.md`. Tag semver por repo gateado por `DEPLOY_TAG_RELEASES`.

> El Brain es el rol del servidor central (LXC capitan-lxc). "SER9" es sólo el modelo de
> hardware actual (Beelink SER9 Pro) — no usarlo como nombre del rol.

## Pipeline actual (objetivo FASE 16)

```
[NSPanel Pro — mic]
    ↓ wake word detectado (Python/Termux)
    ↓ WebSocket/HTTP → Brain LXC ear (servidor de audio)
        ↓ faster-whisper small int8 + ROCm       ~4.6s STT
        ↓ HTTP POST :8765/process
        [core/server.py — Brain LXC]
            ↓ qwen2.5:7b Ollama + ROCm            ~13.3s warm
        [ACTION → HAOS REST API :8123 → VM HAOS Brain]
        ↓ Piper TTS → WAV
    ↓ WAV de respuesta → NSPanel Pro speaker

Latencia warm objetivo: ~18s (STT+LLM+TTS) | mejoras en FASE 31
```

Pipeline anterior (hasta FASE 21): laptop con mic/speaker local. Ya reemplazado.

## Decisiones tomadas (no reabrir)

- LLM: qwen2.5:7b (phi3 descartado)
- STT: faster-whisper sobre openai-whisper
- Wake word: training propio con openWakeWord (Porcupine descartado)
- Reproducción: ffplay (aplay descartado)
- Arquitectura: Brain es el servidor central, laptop es desarrollo puro
- Resampling: scipy.signal.resample_poly (no librosa, más rápido)
- Voz TTS: es_AR-daniela-high (claude y davefx descartadas)
- Comunicación ear↔core: HTTP REST en localhost:8765 (no IPC — permite múltiples ears)
- Hardware nodos distribuidos: NSPanel Pro (Sonoff) — Android 8.1/PX30, mic+parlante
  accesibles via sounddevice/PortAudio, ADB over WiFi, root, Termux. Función dual:
  dashboard HA (Companion App, usuario por panel) + nodo de voz home-agents (Python/Termux).
  Raspberry Pi Zero 2W era la alternativa original pero NSPanel Pro ya está en la casa.
- Ollama GPU iGPU (Radeon 780M): requiere `OLLAMA_IGPU_ENABLE=1` en Ollama 0.30+.
  Sin esa var, Ollama 0.30+ descarta GPUs integradas silenciosamente → fallback a CPU.
  Config en `/etc/systemd/system/ollama.service.d/keepalive.conf`.
  Latencia warm con GPU: ~3-5s | sin GPU: ~74s.
- Wake word retrain en Brain (`/wakeword/train`): el venv necesita `torch` (CPU),
  `torchaudio` (variante +cpu, matchear versión de torch), training deps de openWakeWord
  (audiomentations, speechbrain, librosa, acoustics, pronouncing...) y `onnxscript` para el
  export ONNX. Parches del venv: openwakeword `__init__.py` (scipy import opcional) y
  `acoustics/__init__.py` (agregar `import acoustics.standards` arriba — circular import).
  `wakeword_trainer.py` deriva el path de openwakeword dinámicamente (no hardcodear python3.13).
- Voice-ID en nodos (server-side, audio_server): `speaker_id.identify()` sobre el comando.
  CRÍTICO: el embedding debe enrolarse con el MISMO mic que se usa en runtime. El embedding
  del laptop da ~0.45 sobre audio del NSPanel (= guest, indistinguible del TV); re-enrolado
  desde el NSPanel da ~0.77. Gate `REQUIRE_KNOWN_SPEAKER=true` + `SPEAKER_THRESHOLD=0.6` en
  ear/.env → el TV (guest) se descarta, el usuario conocido pasa. Re-enrolar: `/nspanel-enroll-voice`.
- Mic del NSPanel: capta muy bajo (RMS voz ~1000, ruido ~25) sin AGC. audio_server normaliza
  por RMS antes del STT + vad_filter sobre el audio normalizado. Falsos positivos del wake
  word con TV/radio se resuelven con: retrain (negativos del TV capturados orgánicamente en
  204) + voice-id gate (el TV no matchea ningún perfil enrolado).
- Deps Python del satélite en Termux (NSPanel) — `pip install` NO sirve para todo:
  `numpy` → `pkg install python-numpy`; `onnxruntime` (módulo Python) → `pkg install tur-repo`
  + `python-onnxruntime` (el pkg base `onnxruntime` es solo la lib C, no el binding). `scipy`
  se evita con el patch scipy-opcional en `openwakeword/__init__.py` (el path se deriva con
  `sysconfig.get_path("purelib")`, no importando openwakeword que justo falla por ese import).
  Antes de compilar nada por pip (cffi→sounddevice) correr `pkg upgrade` para alinear
  libicu/clang — un `pkg update` sin upgrade deja `clang` roto (`libicuuc.so.78 not found`).
  La instalación se corre DETACHED con `termux-wake-lock` (una sesión SSH directa la mata a
  mitad porque Android suspende el proceso) y se verifica importando cada módulo, no por rc.
  El boot script lanza `~/voice-node.sh` (supervisor: sostiene `termux-wake-lock` y reinicia
  satellite en loop si crashea — audio HAL puede no estar listo justo tras boot). El supervisor
  vive en un script aparte A PROPÓSITO: su cmdline no contiene `satellite.py`, así
  `pkill -f satellite.py` mata solo el python y el supervisor lo relanza. FOOTGUN: `pkill -f
  satellite.py` también mata cualquier shell (incl. el comando SSH remoto) cuya cmdline
  contenga ese string — al reiniciar por SSH, no metas `satellite.py` en el comando lanzador
  ni uses esa palabra en el one-liner. Para frenar todo: `pkill -f voice-node.sh` y luego el
  python. Para arrancar el supervisor por SSH (sobrevive al cierre de sesión):
  `termux-wake-lock; setsid nohup bash ~/voice-node.sh >/dev/null 2>&1 </dev/null & disown`.
  `nspanel.sh reboot` necesita `su -c reboot` (el firmware eWeLink ignora el reboot sin root).
  Todo esto ya está en `scripts/nspanel.sh`.
