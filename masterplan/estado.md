# Master Plan - Red de Agentes Locales
# Matías Blasi | matias@blasi.ar
# Última actualización: 2026-04-30

---

## CONTEXTO DEL SISTEMA

### Hardware
```
Laptop:     AMD Ryzen 9 5900HX (Zen 3, 8 cores / 16 threads, hasta 4.6GHz)
GPU:        Radeon Vega 8 integrada (comparte RAM, no útil para ML)
RAM:        64GB DDR4
Storage:    (pendiente documentar)
Red:        LAN local con HAOS
```

### Software base
```
OS:         Gentoo Linux
Kernel:     x86_64
Shell:      zsh
Python:     3.13.12
Node:       v18.14.1 (presente en sistema)
Compiler:   GCC 15.2.1 (znver3 optimizado)
Audio:      ALSA puro (sin PulseAudio ni PipeWire)
Micrófono:  ALC256 Analog (hw:1,0) - soporta 44100Hz y 48000Hz
```

### Python Environment
```
Ubicación:  ~/home-agents-env (venv, activar con: source ~/home-agents-env/bin/activate)
Gestor:     pip 26.0.1 + uv 0.11.8 (instalado en root, pendiente en matias)

Paquetes instalados:
  faster-whisper      STT local
  openai-whisper      STT (backup, modelo en ~/.cache/whisper/)
  openwakeword 0.4.0  Wake word inferencia
  pyaudio 0.2.14      Captura de audio
  sounddevice         Audio alternativo
  soundfile           Lectura/escritura de audio
  numpy 2.4.4         Cómputo numérico
  scipy 1.17.1        Procesamiento de señales (resampleo)
  torch               PyTorch CPU only
  torchaudio          Audio con PyTorch
  torchinfo           Info de modelos
  torchmetrics        Métricas de training
  pytorch-lightning   Training framework
  audiomentations     Augmentación de audio
  torch-audiomentations  Augmentación GPU/CPU
  speechbrain         Procesamiento de voz
  onnxruntime 1.24.4  Inferencia ONNX
  scikit-learn 1.8.0  ML clásico
  huggingface_hub     Descarga de modelos HF
  requests            HTTP client
  fastapi             API server
  uvicorn             ASGI server
  pydantic            Validación de datos
  rich                Terminal UI
  tqdm                Progress bars
  pronouncing         Pronunciación (dep. openWakeWord)
  mutagen             Metadata de audio
  acoustics           Acústica (parcheado: sph_harm → sph_harm_y)
  librosa             Análisis de audio
  pandas              DataFrames
  matplotlib          Visualización
  pyyaml              YAML parser
```

### Ollama
```
Versión:    0.20.3 (compilado con vulkan + AVX2 + FMA3 + F16C)
USE flags:  vulkan, avx, avx2, f16c, fma3, sse4_2
Servicio:   systemd/openrc en localhost:11434

Modelos instalados:
  qwen2.5:7b      MODELO PRINCIPAL - 3.5s latencia, formato correcto
  phi3-ha:latest  Customizado para HA (más lento, entity_ids inventados)
  phi3:mini       Descartado (24.8s, formato incorrecto)
  llama3:8b       Disponible, no testeado para domótica
```

### Piper TTS
```
Binario:    ~/.local/bin/piper/piper (v1.2.0)
Voces:      ~/.local/share/piper/

Voces instaladas:
  es_AR-daniela-high.onnx    Femenina argentina  ← usada para training
  es_MX-claude-high.onnx     Masculina mexicana  ← candidata TTS respuesta
  es_ES-davefx-medium.onnx   Masculina española  ← candidata TTS respuesta
  es_ES-sharvard-medium.onnx Femenina española   ← para diversidad training

Reproducción: ffplay -autoexit -nodisp archivo.wav
              (aplay NO funciona sin parámetros explícitos)
```

### faster-whisper
```
Modelo:     small (descargado desde HuggingFace, en cache de HF)
Device:     CPU
Compute:    int8
Idioma:     es (español, 100% confianza en tests)
Latencia:   ~4.6s para 5s de audio
```

### Audio Pipeline
```
Problema:   ALC256 no soporta 16000Hz (necesario para STT/WakeWord)
Solución:   Grabar a 44100Hz → resamplear con scipy.signal.resample_poly
Ratio:      up=160, down=441 (44100 → 16000)
Device idx: 4 (HD-Audio Generic: ALC256 Analog hw:1,0)
```

### Home Assistant OS (HAOS)
```
Hardware:   PC vieja dedicada en la red local
Acceso:     http://192.168.68.101:8123
Token:      en .env (Long-Lived Access Token, excluido del repo)
Estrategia: HAOS solo recibe órdenes via REST API
            Todo el procesamiento (STT/LLM/TTS) corre en laptop

Entity IDs relevantes:
  light.wiz_rgbw_tunable_1fdbc2          → luz principal (WiZ RGBW)
  climate.midea_ac_150633093419021        → aire acondicionado (Midea)
  cover.tze200_nhyj64w2_ts0601           → persiana / toldo
  switch.garaje_light                    → luz del garaje
  switch.patio_light                     → luz del patio
  switch.puerta_principal_light          → luz de la puerta principal
  switch.mi_smart_kettle_pro             → pava / hervidor
  switch.mi_smart_air_fryer_3_5l         → freidora
  switch.agua_principal_valvula_de_cierre → válvula agua principal
  switch.zone_1 … switch.zone_8          → zonas de riego (Rachio)
  media_player.samsung_q8_65_tv          → TV principal (65")
  media_player.samsung_7_series_50       → TV del cuarto (50")
  media_player.echo_de_matias            → Echo de Matías
```

### openWakeWord Training
```
Repo:       ~/workspace/home-agents/ear/wakeword/openWakeWord/
Scripts:    ~/workspace/home-agents/ear/wakeword/generate_samples.py
            ~/workspace/home-agents/ear/wakeword/generate_samples_multi.py
Data:       ~/workspace/home-agents/ear/wakeword/data/capitán/positive/  (90 samples, 1 voz)
            ~/workspace/home-agents/ear/wakeword/data/capitán/negative/  (pendiente)
Parche:     acoustics/directivity.py: sph_harm → sph_harm_y (scipy compat)
```

### Estructura de directorios
```
~/workspace/home-agents/                         ← home-agents (repo umbrella)
├── ear/                          ← submodule: home-agents-ear
│   ├── listen.py                 wake word → STT → HTTP/core → TTS
│   ├── tts.py                    Piper TTS → ffplay
│   ├── panel_*.py                paneles Rich para zellij dashboard
│   ├── dashboard.sh/kdl          lanzador del dashboard
│   ├── run.sh / capitan.service  systemd service
│   └── wakeword/
│       ├── openWakeWord/         submodule del repo externo
│       ├── data/capitán/positive/ (90 samples WAV)
│       └── data/capitán/negative/
├── core/                         ← submodule: home-agents-core
│   ├── server.py                 FastAPI en :8765
│   ├── agent.py                  texto → LLM → ACTION → HAOS
│   ├── agent_registry.py         dispatcher + registry de agentes
│   ├── ha_client.py              cliente REST HAOS + mapa de entidades
│   └── capitan-core.service      systemd service
├── masterplan/
│   └── estado.md                 ← este archivo
├── scripts/
│   └── sync_issues.py
└── interagent/                   concepto del producto (no ejecutable)

~/.cache/
└── whisper/                ← modelos de faster-whisper (HuggingFace cache)

~/.local/
├── bin/piper/piper
└── share/piper/            ← modelos de voz .onnx
```

---

## MASTERPLAN

### FASE 1 - Fundación del Agente de Domótica
```
Objetivo: Agente de voz funcionando end-to-end con HAOS
Estado:   COMPLETA
```
- [x] 1.1  Stack base instalado (Ollama, Whisper, Piper, PyAudio)
- [x] 1.2  Audio pipeline: captura 44100Hz → resampleo 16000Hz
- [x] 1.3  STT validado: faster-whisper español, 100% confianza
- [x] 1.4  LLM validado: qwen2.5:7b, 3.5s, formato ACTION correcto
- [x] 1.5  Pipeline completo voz→STT→LLM validado (15.7s total)
- [x] 1.6  openWakeWord: repo clonado, dependencias OK, train.py importa
- [x] 1.7  Piper: 4 voces españolas descargadas
- [x] 1.8  Samples positivos "Capitán" generados (90 samples, voz daniela)
- [x] 1.9  Elegir voz TTS para respuestas → es_AR-daniela-high.onnx
- [x] 1.10 Regenerar samples con 4 voces → 360 samples (daniela, claude, davefx, sharvard)
- [x] 1.11 Generar samples negativos con Piper → 1320 samples (45 frases × 6 vel × 4 voces, incl. hard negatives)
- [x] 1.12 Extracción de features con embedding_model.onnx → pos=(360,16,96), neg=(1320,16,96)
- [x] 1.13 Training del clasificador → 10k steps, DNN 128-dim, ~20s en CPU
- [x] 1.14 Exportar modelo a ONNX → ~/.local/share/wakeword/capitan.onnx (848KB)
- [x] 1.15 Integrar wake word al pipeline completo → listen.py, score=0.96, STT funcional
- [x] 1.16 Conectar con HAOS real → ha_client.py, IP documentada, 13 entity_ids mapeados
- [x] 1.17 Parser de acciones robusto + ejecución via REST API → agent.py, qwen2.5:7b, 5/5 comandos correctos
- [x] 1.18 Feedback por voz → tts.py, voz daniela, integrado en listen.py
- [x] 1.19 Test end-to-end: "Capitán" → acción ejecutada en HAOS → confirmación por voz ✓
- [x] 1.20 Servicio systemd para el agente → capitan.service (user), start/stop manual con systemctl --user
- [x] 1.21 Dashboard zellij para el agente → dashboard.sh, 4 paneles: score animado, historial, latencias, logs
- [x] 1.22 Modularización en submodules → ear (audio/UI) + core (FastAPI :8765, LLM, HAOS); comunicación via HTTP POST /process

#### Decisiones
- [x] Voz TTS respuesta: es_AR-daniela-high.onnx (única voz argentina disponible en Piper)
- [x] Latencia aceptable: 15.7s actual → avanzar con FASE 2, optimizar en FASE 8 con hardware dedicado

---

### FASE 2 - Agente Domótica Completo
```
Objetivo: Sistema robusto, contextual y con memoria del hogar
Estado:   COMPLETA
```
- [x] 2.1  RAG con estado dinámico de HAOS (FAISS + embeddings)
- [x] 2.2  Context window inteligente (solo entidades relevantes)
- [x] 2.3  Parser de acciones v2 (manejo de errores, validación)
- [x] 2.4  Manejo de ambigüedad ("las luces" → ¿cuáles?)
- [x] 2.10 Gestión de conversaciones: identidad, contexto multi-turno y ciclo de vida

#### Postergadas (movidas a otras fases)
- ~~2.5  Historial de conversación en sesión~~ → implementado como parte de 2.10
- ~~2.6  Automatizaciones por voz~~ → FASE 9.10 (requests condicionales en el coordinador LLM)
- ~~2.7  Satellite en habitaciones~~ → Anexo A.2 (red de nodos de audio multi-ambiente)
- ~~2.8  Fine-tuning con entity_ids~~ → FASE 8.24 (fine-tuning con LoRA en servidor con GPU)
- ~~2.9  Wake word multi-persona~~ → FASE 2.5 tasks 2.5.6 + 2.5.7 (enrollment + speaker ID).
         Prerequisito de FASE 11.7 (amigo/asesor personalizado por usuario).

#### Estado
```
FASE 2 COMPLETA
```

---

### FASE 2.5 - Gestión de Usuarios
```
Objetivo: Sistema de identidad que permite reconocer quién habla, definir su rol y
          parentesco, y personalizar la experiencia.
Estado:   COMPLETA (2.5.10 incluida — ProfileAgent)
Stack:    resemblyzer (GE2E 256-dim), JSON + .npy local, RBAC por rol
```
- [x] 2.5.1  Modelo de usuario: roles (admin/familiar/niño/invitado), relaciones de parentesco,
             preferencias y agentes propios por usuario — users.py
- [x] 2.5.2  Persistencia: ~/.local/share/capitan/users.json + embeddings/*.npy (biométrico, local)
- [x] 2.5.3  API REST en core: GET/POST/PATCH/DELETE /users + POST /users/reload
- [x] 2.5.4  Bootstrap admin: al arrancar sin usuarios, listen.py avisa por voz para registrarse
- [x] 2.5.5  Comando de voz "Capitán, registrarme" — enrollment guiado iniciado desde listen.py
- [x] 2.5.6  Enrollment por voz: 5 frases predefinidas, tono inicio/fin, media L2-normalizada
             guardada como perfil — enrollment.py
- [x] 2.5.7  Identificación en tiempo real: resemblyzer embed + cosine similarity en el audio
             post-wake-word, speaker_id + confidence en source del POST /process — speaker_id.py
- [x] 2.5.8  RBAC: tabla de permisos por rol en rbac.py, allowed() + deny_message(),
             aplicado en /process antes de delegar al agente
- [x] 2.5.9  Panel de usuarios: panel_users.py con Rich, lista de usuarios + speaker activo
             con confidence, lee /tmp/capitan/speaker.json y GET /users
- [x] 2.5.10 Gestión de información personal por voz: comandos para actualizar campos del
- [x] 2.5.11  Nombre de usuario se revierte a 'Nombre' (set_name pisado por ejemplo few-shot) — ejemplo realista input→output en el prompt + guard que rechaza placeholders antes de update_user; idem create_user en user_mgmt. PR core #205
             propio perfil sin tocar el backoffice.
             Ej: "mi pasaporte vence el 15 de marzo de 2027", "mi nombre es Matías",
             "tengo 38 años", "prefiero respuestas cortas".
             El agente extrae el campo y el valor, valida, y hace PATCH /users/{id}.
             Prerequisito natural: cualquier agente que necesite datos personales del usuario
             (fase 7 usa documentos de viaje, fase 11 usa preferencias del usuario).

---

### FASE 2.6 - Onboarding de Usuario y Wake Word Personalizado
```
Objetivo: Unificar la creación de usuario y el perfeccionamiento del reconocimiento en
          un único flujo coherente accesible por dos canales: comando de voz y dashboard web.
          En ambos casos el flujo cubre: datos básicos → speaker ID (resemblyzer) → muestras
          de wake word. Resuelve falsos positivos y baja detección reemplazando el modelo
          TTS-only por uno entrenado con muestras reales de cada usuario.
          Métricas de precisión visibles en el perfil + sugerencias de mejora continua.
Estado:   COMPLETA
Deps:     FASE 2.5 (users.py, enrollment.py, speaker_id.py), FASE 12.13 (sección Usuarios)
Stack:    openwakeword (ya existe), resemblyzer (ya existe), SSE backoffice, HTMX wizard
```

#### Fix inmediato (sin reentrenamiento)
- [x] 2.6.1  Gate post-wake-word: si speaker_id == "unknown" y confidence < umbral
             configurable (`WAKEWORD_REQUIRE_KNOWN_SPEAKER=true` en .env), descarta el comando
             y emite tono "no reconocido". Usa resemblyzer existente de 2.5.7.
             Reduce falsos positivos de terceros al instante, sin tocar el modelo ONNX.

#### Flujo de onboarding unificado
- [x] 2.6.2  `core/onboarding.py` — máquina de estados del flujo de onboarding: pasos
             (datos_basicos → frases_speaker_id → muestras_wake_word → completo).
             Estado persistido en users.json por usuario (onboarding_step, onboarding_complete).
             Mismo flujo consumido por voz y por web.
- [x] 2.6.3  Onboarding por voz: comando "Capitán, agregar usuario" inicia el flujo guiado
             desde `ear/listen.py`. TTS pregunta nombre, rol y relación de parentesco;
             usuario responde por voz. Luego guía las frases de speaker ID (ya existentes en
             enrollment.py de 2.5.6) y las muestras de wake word (2.6.5). Al completar,
             POST /users crea el usuario y POST /users/{id}/wakeword/enroll cierra el flujo.
- [x] 2.6.4  Onboarding por web: wizard multi-paso en backoffice `/users/new`:
             Paso 1: nombre, rol, parentesco (form HTMX).
             Paso 2: frases de speaker ID — botón "Iniciar grabación" activa el mic del
             dispositivo ear vía SSE, progress bar en tiempo real.
             Paso 3: muestras de wake word — igual que paso 2 pero con instrucciones "di Capitán".
             Admin puede lanzar el flujo para cualquier usuario desde la lista de usuarios.

#### Almacenamiento y reentrenamiento
- [x] 2.6.5  `core/wakeword_samples.py` — almacena WAVs de muestras reales por usuario en
             `~/.local/share/capitan/wakeword_samples/{user_id}/` (máx 200 samples),
             metadata en JSON: fecha, duración, aceptado/rechazado, canal (voz/web).
             Endpoint `POST /users/{id}/wakeword/enroll` acepta inicio del flujo guiado;
             SSE stream de progreso para el cliente (sample N/30 ok/rechazado).
- [x] 2.6.6  `POST /wakeword/train` (global) — retrain con muestras reales de todos los
             usuarios enrolled + TTS base; exporta nuevo ONNX a ~/.local/share/wakeword/;
             recarga modelo en listen.py sin reiniciar. BackgroundTask en core/server.py.

#### Métricas y sugerencias
- [x] 2.6.7  Métricas de precisión en operación — `listen.py` registra por usuario:
             detecciones (TP), falsos positivos (wake word + speaker desconocido), rechazos RBAC.
             Persiste en `~/.local/share/capitan/wakeword_metrics.json`.
             API: `GET /users/{id}/wakeword/metrics`.
- [x] 2.6.8  Backoffice perfil de usuario — sección "Reconocimiento de voz":
             estado del onboarding (completo / incompleto / en progreso), precisión (TP/(TP+FP)),
             samples grabados, fecha último enrollment y último reentrenamiento.
             Sugerencias automáticas renderizadas como alertas:
             "menos de 20 muestras — completá el enrollment",
             "FP > 15% — grabá muestras en condiciones de ruido",
             "modelo no incluye tu voz — entrená el modelo",
             "muestras de hace más de 90 días — considera re-enrollarte".

---

### FASE 2.7 - Agentes de Administración
```
Objetivo: Agentes de voz exclusivos para el rol admin que exponen por voz las mismas
          capacidades que el backoffice web: gestión de usuarios y gestión del sistema.
          Siguen el mismo patrón que ProfileAgent: LLM extrae acción estructurada → se aplica.
Estado:   COMPLETA
Deps:     FASE 2.5 (users.py, RBAC), FASE 3 (orquestador, RBAC en /process)
RBAC:     Solo el rol admin tiene acceso (* en PERMISSIONS). El resto recibe deny_message.
```
- [x] 2.7.1  UserMgmtAgent (user_mgmt_agent.py): gestión de usuarios por voz.
             Acciones: listar usuarios, ver perfil de usuario, crear usuario (name+role+relationship),
             borrar usuario, cambiar rol, otorgar/revocar acceso a agentes.
             Al crear: crea el registro y guía al nuevo usuario a decir "Capitán, registrarme"
             para completar el enrollment de speaker ID.
             availability_url → GET /users del core.
- [x] 2.7.2  SystemAgent (system_agent.py): gestión del sistema por voz.
             Acciones: estado del sistema (core/HAOS/Ollama/ear), reiniciar servicios
             (systemctl --user restart capitan-core/capitan), listar modelos Ollama,
             uso de memoria RAM, agentes activos.
             availability_url → GET /health del core.

---

### FASE 3 - Infraestructura Multi-Agente
```
Objetivo: Patrón de extensión para agentes de dominio + estado compartido cross-agente
Estado:   COMPLETA
```

- [x] 3.1  Contrato de interfaz para agentes de dominio: BaseAgent protocol en código,
           patrón de registro en agent_registry, guía para agregar FASE 4-7
- [x] 3.2  Orquestador central → server.py (FastAPI :8765, POST /process)
- [x] 3.3  Router de intención → agent_registry.dispatch() (keywords + LLM fallback)
- [x] 3.4  Estado compartido cross-agente: slot de contexto legible/escribible por cualquier
           agente activo (ej: clima sabe que llueve → haos puede ajustar persianas)
- [x] 3.5  Logging y observabilidad → /tmp/capitan/*.json + dashboard zellij
- [x] 3.6  API unificada → POST /process, GET /agents, GET /health, GET /conversations
- [x] 3.7  Dashboard de estado → panel_agents.py (agente activo, fuente, conversación)

---

### FASE 3.5 - Integración WhatsApp
```
Objetivo: Canal de texto y audio hacia el orquestador vía WhatsApp
Estado:   COMPLETA
Deps:     FASE 3.2 ✓ (orquestador implementado), FASE 1.3 ✓ (STT), FASE 1 TTS ✓
Privacidad: solo números autorizados, todo corre local
Stack:    whatsapp-web.js (Node 18), LocalAuth, POST /wa/inbound (FastAPI)
```

#### Etapa A - Canal de texto
- [x] 3.5.1  Elegir cliente WA: whatsapp-web.js (Node 18) — sesión LocalAuth en disco
- [x] 3.5.2  Setup del cliente: sesión persistente con QR scan, reconexión automática (wa/index.js)
- [x] 3.5.3  Webhook receiver en el orquestador (FastAPI endpoint POST /wa/inbound en server.py)
- [x] 3.5.4  Control de acceso por usuario: User.wa_phone resuelve número → speaker_id + RBAC por rol
- [x] 3.5.5  Routing texto → orquestador → agente → respuesta de vuelta por WA
- [x] 3.5.6  Manejo de contexto por número: source={channel:whatsapp, phone:...} → source_key único en conversations.py

#### Etapa B - Canal de audio (PTT)
- [x] 3.5.7  Recibir mensajes de voz (PTT) de WhatsApp → descargar OGG/Opus (wa/index.js handleAudio)
- [x] 3.5.8  Convertir OGG → WAV 16000Hz (ffmpeg en wa_audio.transcribe)
- [x] 3.5.9  Pasar por faster-whisper → texto → orquestador (POST /wa/inbound/audio)
- [x] 3.5.10 Respuesta: espejo de entrada — PTT → nota de voz OGG/Opus (Piper + libopus); fallback a texto

#### Decisiones tomadas
- [x] Cliente WA: whatsapp-web.js (Node 18) — más simple, sin Docker
- [x] Respuesta: espejo de entrada (texto → texto, PTT → nota de voz)
- [x] Persistencia de sesión WA: LocalAuth en ~/.local/share/capitan/wa-session/

#### Correcciones
- [x] 3.5.11 **Fix formato @lid** — `msg.from` puede llegar como `205432...@lid` en vez de `5491...@c.us`
             (formato "linked identity" de WA moderno). Usar `msg.getContact()` para resolver el número
             real en todos los casos, en lugar de un simple `replace("@c.us", "")`.
- [x] 3.5.12 **Match por wa_lid** — `contact.number` en modo `@lid` devuelve el LID, no el teléfono.
             Solución: campo `wa_lid` en User (además de `wa_phone`). Para mensajes `@c.us` se usa
             `from_number`; para `@lid` se pasa `from_lid` al core. El core intenta match por
             `wa_phone` primero, luego por `wa_lid`. El backoffice muestra y permite editar `wa_lid`
             en el perfil de usuario.

---

### FASE 4 - Agente Clima
```
Objetivo: Consultas de clima por voz + integración con domótica
Estado:   COMPLETA
```

## Completado

- [x] 4.1  Integración Open-Meteo API (libre, sin key, precisa)
- [x] 4.2  Datos históricos y pronóstico extendido local (7 días + hourly 12h)
- [x] 4.3  Integración con domótica via shared_state:
           publica weather.is_raining, temp_outside, wind_speed, conditions
           HaosAgent puede leer estas entradas para acciones condicionales
- [x] 4.4  Alertas proactivas por voz (mecanismo genérico):
           alert_queue.py (FIFO thread-safe), server.py poller cada 15min via agent.alerts(),
           GET /alerts consume-once, ear/_alert_thread daemon (60s, solo en state=listening)
           Cualquier agente futuro puede implementar alerts() → list[str] sin registro extra
- [x] 4.5  Contexto geográfico desde .env: LATITUDE, LONGITUDE, LOCATION_NAME

---

### FASE 5 - Agente Agenda
```
Objetivo: Gestión de agenda por voz, privada y local
Estado:   COMPLETA (5.2 postergada, google-free; alarma luces → HAOS nativo)
```
- [x] 5.1  CalDAV local (Radicale en HAOS o servidor dedicado)
- [ ] 5.2  Sincronización opcional con Google Calendar
- [x] 5.3  Consultas por voz:
           "¿qué tengo mañana?"
           "agendá reunión el viernes a las 10"
           "¿cuándo es el próximo feriado?" — feriados UY via Nager.Date API
- [x] 5.4  Integración con domótica:
           alarma de agenda → encender luces gradualmente [postergado → HAOS nativo]
           reunión en 15min → recordatorio por voz ✓ (thread 1min, reminder_minutes configurable)
- [x] 5.5  Recordatorios proactivos sin trigger de voz (briefing matutino + resumen vespertino, hora configurable)
- [x] 5.6  Vista de agenda en panel de HAOS
           Radicale expuesto en LAN (0.0.0.0:5232); integración CalDAV en HA via config flow API;
           entidades: calendar.personal + calendar.feriados; tarjeta Calendar en el dashboard de HA
- [x] 5.7  Eliminar de raíz los warnings de `caldav` — el warning salía de `.principal()`, que
           sondea `current-user-principal` (que el CalDAV de Google no expone). Fix: apuntar
           DIRECTO a la URL conocida del calendario primario (`caldav.Calendar(client, url=...)`)
           en vez de `principal().calendars()` → sin sondeo, sin warning, sin parche de logging.
           App Password requiere CalDAV (la API REST de Google exige OAuth2), así que se mantiene
           CalDAV; Google Calendar es el único backend. Validado contra Google real (lee eventos,
           0 warnings). Nota: ahora se trabaja con el calendario primario (feriados ya en JSON).

---

### FASE 6 - Agente Inversiones
```
Objetivo: Consultas financieras por voz, datos privados locales
Estado:   COMPLETA
Nota:     Modo dummy (recomendaciones + P&L hipotética). Portfolio por usuario (FASE 2.5).
          Fuentes: yfinance (acciones/crypto/FX) + dolarapi.com (dólar oficial/blue/MEP/CCL).
```
- [x] 6.1  Definir fuentes de datos:
           yfinance (acciones internacionales, crypto, pares FX)
           dolarapi.com (dólar oficial/blue/MEP/CCL/tarjeta)
           yfinance UYU=X (peso uruguayo)
- [x] 6.2  Cliente de cotizaciones con cache (finance_client.py):
           get_quote(), get_history(), get_price_at_date(), get_dollar_rates(), get_uyu_rate()
           Cache 10min por símbolo, 15min para dólar
- [x] 6.3  Portfolio por usuario en modo dummy (portfolio.py):
           Watchlist por usuario, registro de recomendaciones (buy/sell/hold/watch),
           P&L hipotética calculada con precio actual, persistencia ~/.local/share/capitan/
- [x] 6.4  Consultas por voz (finance_agent.py):
           "¿cómo está el dólar?" "¿cuánto vale GGAL?" "¿qué me recomendás?"
           "¿cómo fueron tus recomendaciones?" — etiqueta [REC:accion:TICKER] registra automáticamente
- [x] 6.5  Alertas configurables (finance_alerts.py):
           Brecha blue/oficial > 10%, BTC ±5%, watchlist ±5%. Umbrales via .env.
- [x] 6.6  RAG sobre noticias financieras (scraping + embeddings):
           finance_news.py — RSS Yahoo Finance por ticker, embeddings nomic-embed-text (Ollama),
           búsqueda cosine numpy, fallback keyword, índice JSON persistido, refresh async
- [x] 6.7  Resumen diario automático (en finance_alerts.check()):
           Dólar oficial/blue, UYU, movimientos de watchlist. Emite a FINANCE_BRIEFING_HOUR (8am).
- [x] 6.8  Planes de inversión diversificados (portfolio.py + finance_agent.py):
           El LLM puede emitir [PORTFOLIO:nombre|TICKER:pct,...] para crear/guardar planes
           con snapshot de precios al momento. save_plan(), list_plans(), delete_plan(),
           calculate_plan_pnl(). Soporte multi-plan por usuario, reemplazo por nombre.
           El agente inyecta los planes existentes como contexto al LLM.
- [x] 6.9  Reporte comparativo diario de planes con formato WA (finance_alerts.py):
           Al momento del briefing matutino, por cada usuario con planes guardados:
           1. Alerta TTS corta: "tu mejor plan es X con +Y%"
           2. Reporte WA rico enviado directo vía wa_notifier: tabla por plan con
              P&L por posición, ponderada total, medallas 🥇🥈🥉, mejor plan 🏆.
           Cooldown 20h por usuario. Configurable via FINANCE_BRIEFING_HOUR.
- [x] 6.10 Perfiles de riesgo por usuario + ciclo proactivo estratégico (portfolio.py + finance_agent.py):
           RISK_PROFILE_TEMPLATES (conservador/moderado/agresivo) con posiciones y umbrales de revisión.
           Tag [PROFILE:...] en system prompt: el LLM detecta el perfil en conversación y lo persiste
           via context_updates (3-tuple). _ask_llm() inyecta perfil como contexto activo.
           proactive_check() split en dos capas:
           — _strategic_checks(): hardcodeado — intent si falta perfil, plan, o P&L bajo umbral
           — proactive_check(): llama _strategic_checks() + super().proactive_check() (LLM sobre historial);
             omite LLM si no hay perfil. proactive_system_prompt específico para finanzas.
           Las alertas reactivas de precios siguen en finance_alerts.check() sin duplicación.
- [x] 6.11 Templates de planes automáticos: crear planes desde templates sin necesidad de conversación.
           Auto-crear un plan por template disponible al primer proactive_check sin planes.
           list_templates(), save_template(), delete_template() en portfolio.py — CRUD persistente
           en finance_templates.json con seed desde RISK_PROFILE_TEMPLATES. Cada template tiene
           review_threshold propio. create_plans_from_templates(user_id) crea solo los faltantes.
           _strategic_checks() reemplaza Intent 0 + Intent 1 por auto-creación silenciosa.
           CRUD en backoffice /finance/templates con formulario inline.
           REST: GET/POST /finance/templates, DELETE /finance/templates/{name}.
- [x] 6.12 Backoffice sección planes de inversión por usuario:
           Sección "Planes de inversión" en /users/{id}: tabla con posiciones, P&L actual por plan,
           botón eliminar por fila. REST: GET /finance/plans/{uid}, DELETE /finance/plans/{uid}/{name}.
- [x] 6.13 Reporte P&L horario por WA (intraday + total):
           finance_alerts._send_portfolio_pnl_hourly_wa() — por cada usuario con planes y wa_phone,
           envía WA con P&L del día ("hoy") y acumulada desde creación ("total") de cada plan.
           portfolio.calculate_plan_pnl() incluye intraday_pct (change_pct del día) en cada row.
           Cooldown configurable por usuario. Emojis bidireccionales: 🚀 arriba del umbral, ⚠️ abajo.
           Se omite si toda la P&L es < 0.05% (ruido de mercado cerrado). Llamada desde check().
- [x] 6.14 Config P&L por usuario editable desde backoffice:
           Tres campos nuevos en user_context_schema de FinanceAgent: plan_pnl_up_pct, plan_pnl_down_pct,
           plan_pnl_hours. finance_alerts._get_user_pnl_config() los lee via user_context.get_context(),
           con fallback a defaults globales (.env). Globales: FINANCE_PLAN_PNL_UP_PCT=5.0,
           FINANCE_PLAN_PNL_DOWN_PCT=-5.0, FINANCE_PLAN_PNL_HOURS=1. Clamp mínimo de 1h.
           Valores inválidos hacen fallback silencioso al global.
- [x] 6.15 Todas las alertas de finanzas configurables por usuario:
           _get_user_pnl_config reemplazado por _get_user_alert_config que cubre los 7 umbrales:
           dollar_gap_pct, btc_move_pct, stock_move_pct, briefing_hour, plan_pnl_up_pct,
           plan_pnl_down_pct, plan_pnl_hours. check() itera por usuario en todas las reglas,
           cooldown keys incluyen uid. user_context_schema extendido con 4 campos nuevos.
- [x] 6.17 Templates de inversión per-user:
           Eliminados los templates globales (/finance/templates). Cada usuario tiene
           su propio archivo finance_templates_{uid}.json con defaults hardcodeados
           (conservador/moderado/agresivo) si nunca personalizó. Nuevos endpoints
           GET/POST/DELETE /finance/plans/{uid}/templates en core. Backoffice: sección
           "Templates de inversión" bajo el agente finance en user_detail, separada
           visualmente de los campos del LLM context. Formulario inline con HTMX.
           Sidebar pierde ítem global "Templates inv."
- [x] 6.18 Ticker autocomplete en formulario de templates:
           GET /finance/tickers/popular — lista curada (22 instrumentos: CEDEARs, ETFs, cripto,
           commodities, FX) con cache 5min. GET /finance/tickers/search?q= — proxy Yahoo Finance
           search con debounce 280ms y cache 5min. Formulario de nuevo template rediseñado: filas
           dinámicas ticker+%, dropdown con curada agrupada por categoría al hacer focus, búsqueda
           en tiempo real al tipear. Validación suma=100% antes de guardar. Fix autocomplete:
           hideTimer compartido con clearTimeout, position:fixed sin scrollY, tmplAddRow() retorna
           input, foco con setTimeout(0).
- [x] 6.19 Ventana temporal configurable + desglose por ticker en P&L history:
           BACKEND: get_plan_pnl_history(plan, interval, start, end) con start/end opcionales
           clampeados a created_at. Retorna 3-tupla (series, trend, ticker_series) donde
           ticker_series mapea cada ticker a [{date, pnl_pct, contribution}]. Core server pasa
           ?start=&end= al portfolio. Backoffice proxy reenvía ambos params.
           FRONTEND: date range picker (desde/hasta, min=creación plan más antiguo). Drag-to-select
           en el gráfico via chartjs-plugin-zoom: arrastrar actualiza inputs de fecha automáticamente.
           Botón Restablecer vuelve al rango completo. Toggle "Desglose tickers": líneas por ticker
           con contribución ponderada, sin fetch (re-render desde cache). Métricas incluyen tabla
           de P&L propio + contribución por ticker. Timezone fix (forward-fill) para planes con
           mezcla de equity/cripto/commodity.
- [ ] 6.20 Ciclo proactivo de mejora de planes:
           `_proactive_json_extra_schema` + `_on_proactive_llm_data` + `handle_captured_reply`
           en FinanceAgent. El LLM proactivo recibe contexto de planes+P&L+perfil+noticias y
           puede sugerir modificaciones via campo "plan_proposals" en el JSON de respuesta.
           El usuario acepta/rechaza via request intent (WA o web). Se registra en plan_events.py.
           HOOKS en ProactiveMixin: _proactive_json_extra_schema (extiende JSON schema al LLM),
           _on_proactive_llm_data (procesa campos extra de la respuesta). _is_affirmative() parsea
           respuestas del usuario (sí/dale/ok/...). Auto-dedup contra intents activos por título.

- [ ] 6.21 Milestones en histograma P&L:
           plan_events.py — log de eventos de plan (suggestion/applied/rejected/manual_edit),
           almacenado en ~/.local/share/capitan/plan_events/{user_id}.json.
           Endpoint GET /finance/plan-events/{user_id} con filtros plan_name y since (ts Unix).
           Backoffice finance_pnl_history.html: chartjs-plugin-annotation@3, función loadMilestones()
           carga eventos y renderiza líneas verticales: amarillo=sugerencia, verde=aplicado,
           rojo=rechazado. Nearest-label matching para eje category.

- [x] 6.16 Histograma de P&L de planes a lo largo del tiempo (backoffice):
           Vista en backoffice que muestra evolución histórica del P&L de cada plan.
           FUENTE DE DATOS: precios históricos vía fc.get_price_at_date() / yfinance.history()
           desde created_at hasta hoy, frecuencia diaria.
           BACKEND:
             - portfolio.get_plan_pnl_history(plan, freq="1d") → list[{date, pnl_pct, per_position}]
               Calcula P&L ponderada para cada fecha entre created_at y hoy.
               Cachea hasta 1h (yfinance devuelve datos estáticos intradía).
             - GET /finance/plans/{uid}/history?plan=NAME — devuelve JSON con serie temporal.
               Soporta múltiples planes: ?plan=A&plan=B (o todos si se omite).
             - Tendencia: regresión lineal sobre la serie. Devuelta como pendiente (pct/día) + proyección 30d.
           FRONTEND (backoffice Jinja2 + Chart.js CDN):
             - Nueva sección en /users/{id} bajo "Planes de inversión".
             - Línea por plan (Chart.js line chart), escala % en Y, fechas en X.
             - Toggle para mostrar/ocultar planes individuales.
             - Línea punteada de tendencia (regresión + proyección).
             - Tooltip con valor exacto por fecha.
           TESTS:
             - get_plan_pnl_history: precio estático → P&L constante en cada punto.
             - get_plan_pnl_history: dos tickers con pesos distintos → ponderación correcta.
             - endpoint /history: retorna JSON con campo "series" + "trend".
             - tendencia: serie ascendente → pendiente positiva.

---

### FASE 7 - Agente Viajes
```
Objetivo: Asistente de planificación activa de viajes futuros
Estado:   COMPLETA (7.2 postergada por falta de docs centralizados)
Foco:     Planificación activa (itinerarios, qué llevar, visa, clima en destino).
          Grupo viajero variable por conversación (individual, pareja, familia).
          Documentos de viaje en modelo de usuario (ver 2.5.10 para gestión por voz).
```
- [x] 7.1  Casos de uso definidos: planificación activa de viajes futuros, grupo familiar
           variable, documentos en user model, clima en destino via geocoding
- [ ] 7.2  RAG sobre documentos de viaje (pasaportes, reservas, PDFs)
           Postergada: no hay documentos centralizados aún. Retomar cuando el usuario
           empiece a digitalizar reservas (emails, PDFs de hoteles/vuelos).
- [x] 7.3  Geocoding (geocoding.py): nombre de ciudad → lat/lon via Open-Meteo Geocoding API
           (gratuito, sin key, cache 24h). format_location() para contexto LLM.
- [x] 7.4  Documentos de viaje en User: campo documents [{type,country,expires,number,notes}],
           upsert_document(), remove_document(), expiring_documents(). API REST nueva.
- [x] 7.5  TravelAgent (travel_agent.py): geocoding → clima → documentos grupo → LLM.
           _extract_destination(): micro-LLM para extraer ciudad del texto.
           Grupo viajero resuelto por texto o todos los usuarios registrados.
- [x] 7.6  Alertas de documentos (travel_alerts.py): 3 tiers (30/90/180 días),
           cooldowns por (user, tipo, país, tier) via shared_state.

---

### FASE 8 - Migración a Servidor Dedicado
```
Objetivo: Mover toda la inferencia a hardware dedicado y escalar a modelos más potentes
Estado:   EN CURSO — la MIGRACIÓN de servicios (home-agents + Ollama) de la laptop al Brain
          está DONE (vía FASE 21: Proxmox + LXC, Ollama con GPU ROCm, laptop como dev/cliente).
          PENDIENTE: un servidor REALMENTE dedicado (GPU NVIDIA potente) para correr un modelo
          grande (qwen 14b/32b/72b, Whisper large-v3 GPU) que reemplace al qwen2.5:7b actual.
Laptop:   Ya es cliente/satélite + entorno de desarrollo.
Nota:     El Brain (Beelink, iGPU 780M/ROCm) alcanza para los servicios y el 7b, pero NO para
          modelos grandes — por eso la Etapa D (escalado de modelos) sigue abierta.
```

#### Etapa A - Definición de hardware objetivo
- [ ] 8.1  Definir presupuesto y timeline de compra
- [ ] 8.2  CPU objetivo: AMD Ryzen 9 7900X / 7950X o Intel i9-13900K
           (muchos cores para inferencia paralela multi-agente)
- [ ] 8.3  RAM objetivo: 128GB DDR5 mínimo (correr 2-3 modelos grandes simultáneos)
- [ ] 8.4  GPU objetivo para inferencia:
           RTX 4070 Ti 12GB  → buena relación precio/VRAM
           RTX 3090 24GB     → VRAM ideal para modelos 20B+
           RTX 4090 24GB     → techo actual para un solo agente grande
- [ ] 8.5  GPU objetivo para fine-tuning (puede ser la misma o segunda):
           RTX 3060 12GB     → mínimo para LoRA
           RTX 3090 24GB     → cómodo para modelos hasta 13B
- [ ] 8.6  Storage: SSD NVMe ~2TB para modelos + HDD para datos y backups
- [ ] 8.7  Red: ethernet gigabit al switch (no WiFi para el servidor)

#### Etapa B - Setup del servidor
- [ ] 8.8  OS: Debian stable o Ubuntu Server LTS (priorizar estabilidad sobre cutting-edge)
- [ ] 8.9  Drivers CUDA + cuDNN para GPU NVIDIA
- [x] 8.10 Ollama con soporte GPU (inferencia ~10-30x más rápida que CPU)
- [ ] 8.11 Recompilar faster-whisper con soporte CUDA
- [ ] 8.12 Docker Compose para todos los servicios (orquestador, agentes, bases de datos)
- [x] 8.13 IP estática en LAN, hostname fijo (ej: `agentes.local`)
- [x] 8.14 Acceso SSH seguro desde laptop y otros dispositivos de la red

#### Etapa C - Migración de servicios
- [x] 8.15 Migrar Ollama + modelos al servidor (servidor nuevo como :11434)
- [x] 8.16 Migrar orquestador FastAPI (FASE 3) al servidor
- [x] 8.17 Migrar todos los agentes al servidor
- [x] 8.18 Laptop queda como: cliente de voz (mic/speaker) + entorno de desarrollo
- [x] 8.19 Período de operación paralela: laptop + servidor corriendo juntos para validar
- [x] 8.20 Cutover: redirigir laptop al servidor, apagar servicios locales

#### Etapa D - Escalado de modelos
- [ ] 8.21 Modelos de inferencia con GPU:
           qwen2.5:14b   → mejor razonamiento, cabe en 12GB VRAM
           qwen2.5:32b   → contexto largo, requiere 24GB VRAM o CPU offload
           qwen2.5:72b   → máxima capacidad, requiere multi-GPU o CPU offload con 128GB RAM
- [ ] 8.22 Whisper large-v3 en GPU (~0.5s latencia vs 4.6s actual en CPU)
- [ ] 8.23 Modelos especializados por agente (ej: modelo financiero para agente inversiones)
- [ ] 8.24 Fine-tuning con LoRA para dominio hogar (entity_ids reales, patrones propios)

#### Etapa E - Operaciones y confiabilidad
- [ ] 8.25 UPS para el servidor (evitar cortes abruptos con modelos en memoria)
- [x] 8.26 Systemd units para auto-restart de todos los servicios
- [ ] 8.27 Monitoreo de recursos: temperatura GPU/CPU, uso de VRAM, latencias por agente
- [x] 8.28 Alertas si un servicio cae (notificación por WhatsApp vía FASE 3.5).
           Implementado para HAOS: watchdog externo en el SER9 (`ha-watchdog.timer`, 60s)
           detecta/recupera (3 fallos→`ha core restart`, 6→`qm reset 100`) y su hook postea
           a `POST /alerts/haos` en core → notifica a los admins por WhatsApp (+`HAOS_ALERT_PHONE`)
           y persiste el evento (`metrics_store.haos_health_events`). `ha_client.ping()` +
           `GET /health/haos`. PR core #212.
- [ ] 8.29 Backup automático de modelos fine-tuneados y configuraciones
- [ ] 8.30 Wake-on-LAN desde laptop (servidor puede estar en suspend fuera de horario)
- [ ] 8.31 Auto power-on del Brain tras corte de luz: setear en BIOS "Restore AC Power Loss"
- [ ] 8.32  Investigar por qué sin internet no se accede a HAOS en la LAN
           = Power On (no Last State) para que Proxmox levante solo. Verificar que VM 100
           (HAOS) y LXC 101 (capitan-lxc) tengan onboot=1. Complementa 8.25 (UPS): sin BIOS,
           un corte largo deja todo caído hasta volver físicamente.

#### Latencias objetivo post-migración (con GPU)
```
STT (Whisper large-v3 GPU):   ~0.3-0.5s   (vs 4.6s actual)
LLM qwen2.5:14b GPU:          ~1-2s        (vs 3.5s actual con 7b CPU)
TTS Piper (sin cambio):       ~0.5s
Total estimado:               ~2-3s        (vs 8s actual warm)
```

---

### FASE 9 - Coordinador Basado en Modelo
```
Objetivo: Reemplazar el router de reglas por un LLM coordinador capaz de descomponer
          requests complejos, rutear a múltiples agentes y agregar respuestas.
Estado:   COMPLETA
Deps:     FASE 3.2 (orquestador), FASE 3.3 (router de reglas como baseline),
          FASE 2.10 (contexto multi-turno), ≥2 agentes de dominio estables.
Cuándo empezar: cuando el router de reglas muestre limitaciones reales en uso diario
                (requests ambiguos, cross-domain, multi-paso). Puede superponerse con
                las últimas fases de dominio (FASE 6-7) una vez FASE 4-5 estén estables.
```

#### Por qué un modelo y no solo reglas

El router de reglas (FASE 3.3) funciona bien para intenciones simples y bien definidas.
Falla o requiere complejidad creciente ante:
- Ambigüedad: "prepará todo para salir" (¿persianas? ¿luces? ¿agenda?)
- Cross-domain: "¿debería llevar paraguas y tengo algo en la agenda mañana?"
- Multi-paso: "cuando llegue a casa, revisá el clima y si hace frío, encendé la calefacción"
- Contexto implícito: "¿y mañana?" (depende del turno anterior — requiere FASE 2.10)

Un LLM coordinador resuelve esto de forma natural, sin enumerar cada caso en código.
El beneficio escala con la cantidad de agentes: con 2 agentes, las reglas alcanzan;
con 5+, se vuelven un cuello de botella de mantenimiento.

#### Diseño del coordinador

El coordinador es un LLM que recibe:
```
[contexto de conversación]   ← últimos N turnos (FASE 2.10)
[utterance del usuario]
[catálogo de agentes]        ← nombre, descripción, ejemplos de queries válidas
```

Y produce un plan de ejecución estructurado:
```json
{
  "steps": [
    {"agent": "clima",  "query": "pronóstico mañana Buenos Aires", "depends_on": []},
    {"agent": "agenda", "query": "eventos de mañana",              "depends_on": []}
  ],
  "aggregation": "combinar pronóstico y agenda en una recomendación"
}
```

El orquestador (FASE 3.2) ejecuta los pasos (en paralelo cuando no hay dependencias),
recolecta los resultados y los devuelve al coordinador, que genera la respuesta final.

#### Opciones de modelo para el coordinador

| Opción | Modelo               | Latencia extra | Tradeoff                                      |
|--------|----------------------|---------------|-----------------------------------------------|
| A      | qwen2.5:7b (ya instalado) | +3-4s    | cero setup; puede sobrepensar en casos simples |
| B      | qwen2.5:3b (instalar)| +1-2s          | más rápido; validar calidad de routing         |
| C      | clasificador sklearn | <100ms         | limitado a intenciones vistas, no generaliza   |
| D      | híbrido C+B          | <100ms / +1-2s | mejor tradeoff; clasificador para casos simples, LLM para el resto |

Recomendación de arranque: **opción A** (reusa lo instalado, latencia conocida).
Objetivo de largo plazo: **opción D** — el clasificador absorbe el 80% de requests
simples en <100ms y el LLM entra solo cuando hay ambigüedad real.

#### Etapa A — Coordinador como router
- [x] 9.1  Definir formato del catálogo de agentes: nombre, descripción, 3-5 ejemplos de queries válidas
           Campo `examples` (5 queries por agente) en REGISTRY de agent_registry.py.
- [x] 9.2  Prompt del coordinador v1: utterance + catálogo → elige un agente + reformula query para ese agente
           coordinator.py (nuevo): `coordinate(text, conv_context)` → (agent_id, reformulated_query, latency_s)
           El contexto de conversación se inyecta para routing multi-turno correcto.
           El texto original sigue llegando al agente de dominio (Etapa B usará la query reformulada).
- [x] 9.3  Reemplazar router de reglas (FASE 3.3) con llamada al coordinador LLM
           server.py /process: conv se obtiene antes del coordinador para pasarle contexto;
           ProcessResponse agrega coordinator_query y coordinator_latency_ms para observabilidad.
           Impacto transversal: listen.py registra lat_coordinator en history.json;
           panel_latency.py muestra fila "Coordinador" dinámicamente.
- [x] 9.4  A/B test: precisión de routing coordinador vs. reglas sobre queries del historial real
           Benchmark 20 queries (2026-05-02):
           Keywords: 18/20 (90%) — falla en "mi pasaporte vence..." → travel (correcto: profile)
                                   y "debería llevar paraguas?" → haos (correcto: weather)
           Coordinador: 17/17 correctas en calls sin timeout (100%) — 3 timeouts por carga de Ollama
           Wins del coordinador: desambigua queries sin keywords claras; reformulación visible en logs.
- [x] 9.5  Medir overhead de latencia del coordinador; objetivo: que no supere 4s extra en warm
           Latencia warm del coordinador: ~3.5s (consistente con la llamada LLM del agente)
           Total warm estimado: ~11.5s (era ~8s). Overhead: +3.5s. ✓ Dentro del objetivo de 4s.
           Timeout aumentado a 20s para evitar falsos timeouts bajo carga concurrente.

#### Etapa B — Queries multi-agente
- [x] 9.6  Extender el plan de ejecución a N pasos con dependencias opcionales entre pasos
- [x] 9.7  Orquestador ejecuta pasos sin dependencias en paralelo (asyncio / ThreadPool)
- [x] 9.8  Coordinador recibe resultados de todos los agentes y genera respuesta unificada
- [x] 9.9  Prompt de agregación: sintetizar respuestas parciales en texto coherente, sin repetir cada una

#### Etapa C — Descomposición y corrección
- [x] 9.10 Detección de requests condicionales ("cuando X, hacé Y"): el coordinador genera un plan con condición explícita
- [x] 9.11 Manejo de falla de agente: el coordinador detecta error en resultado y reintenta o responde con degradación elegante
- [x] 9.12 Ciclo de clarificación: si el coordinador detecta ambigüedad irresoluble, genera una pregunta al usuario en vez de asumir

#### Etapa D — Optimización de latencia
- [x] 9.13 Evaluar qwen2.5:3b como coordinador: instalar, benchmark de routing vs. 7b
- [x] 9.14 Clasificador rápido para intenciones simples: entrenar con historial de requests reales (sklearn o reglas con score de confianza)
- [x] 9.15 Híbrido: usar clasificador cuando confianza > umbral configurable, coordinador LLM para el resto

#### Etapa E — Contexto por usuario por agente
```
Cada agente puede mantener un perfil de datos por usuario: preferencias aprendidas,
patrones de uso, información contextual persistente. El administrador define qué campos
recolecta cada agente y por cuánto tiempo. Cada usuario puede ver y gestionar la
información que cada agente guarda sobre él.
```
- [x] 9.16 `core/user_context.py` — almacena contexto estructurado en
           `~/.local/share/capitan/user_context/{user_id}/{agent_id}.json`.
           Cada campo: `{value, updated_at, ttl_days}`. Auto-expira campos en lectura.
           API interna: get_context(user_id, agent_id) / set_field(field, value) /
           delete_field(field) / get_all_for_user(user_id).
- [x] 9.17 Extensión de `agent_config.py` — campo `user_context_schema` por agente:
           lista de `{field, desc, type, ttl_days}` que define qué datos puede registrar
           el agente sobre cada usuario y por cuánto tiempo. Configurable en backoffice.
           Los tipos soportados: string, number, boolean, enum (con options).
- [x] 9.18 Inyección de contexto en dispatch: antes de llamar al agente, `server.py`
           carga el contexto vigente (campos no expirados) del usuario para ese agente
           y lo prepende al prompt como bloque estructurado. Sin contexto = sin overhead.
- [x] 9.19 Actualización de contexto post-interacción: el agente puede incluir
           `context_updates: [{field, value}]` en su respuesta estructurada.
           `server.py` persiste esas actualizaciones vía `user_context.py`.
           Cada agente decide qué aprende de la interacción (ej: clima aprende
           la ubicación preferida, inversiones aprende el perfil de riesgo).
- [x] 9.20 API REST para contexto de usuario:
           `GET /users/{id}/context` — contexto de todos los agentes (para backoffice),
           `GET/PATCH /users/{id}/context/{agent_id}` — contexto de un agente específico,
           `DELETE /users/{id}/context/{agent_id}/{field}` — eliminar un campo puntual.
- [x] 9.21 Backoffice `/agents/{id}/edit` — sección "Esquema de contexto de usuario":
           tabla editable de campos (nombre, descripción, tipo, TTL en días),
           botones agregar/eliminar campo, guardado vía PATCH al core.
           Un campo eliminado del schema no borra datos existentes (solo deja de inyectarse).
- [x] 9.22 Backoffice perfil de usuario `/users/{id}` — sección "Contexto en agentes":
           acordeón por agente, muestra campos vigentes con valor / última actualización /
           TTL restante en días. Botón editar valor (PATCH) y botón eliminar campo (DELETE).
           El propio usuario puede ver y controlar exactamente qué recuerda cada agente de él.

#### Etapa F — Intenciones persistentes y continuación proactiva

```
Las intenciones son una entidad de primer nivel (separada del user_context): representan
acciones que el usuario quiere hacer, monitoreadas por un agente entre sesiones.
Tienen ciclo de vida (pending → in_progress → done/cancelled), pueden disparar alertas
proactivas y son visibles en el backoffice como página propia (/intents).
Storage: ~/.local/share/capitan/intents/{user_id}.json
```
- [x] 9.23 `core/intent_state.py` — módulo propio (no anidado en user_context):
           `{intent_id, agent_id, user_id, title, description, status, context: dict,
           created_at, updated_at, expires_at, last_reminded_at, remind_after_days}`.
           API: `upsert()`, `get()`, `get_active()`, `get_active_for_agent()`,
           `update_status()`, `update_context()`, `delete()`, `get_all_needing_reminder()`,
           `get_all_active_across_users()` (vista admin).
- [x] 9.24 Detección de intenciones en agentes — agentes pueden devolver
           `(resp, action, {"context_updates": [...], "intent_updates": [...]})`.
           `_apply_agent_updates()` en `server.py` persiste ambos tipos.
           Backwards compatible: 3-tuple con lista directa sigue siendo context_updates.
- [x] 9.25 Retoma proactiva al inicio de sesión — `_build_agent_prefix()` en `server.py`
           inyecta contexto + intenciones activas como system message antes de cada llamada
           al agente (single-step y multi-step). El LLM las ve y las retoma naturalmente.
- [x] 9.26 Alertas proactivas de intenciones — `_alert_poller()` verifica
           `get_all_needing_reminder()` en cada ciclo; genera alerta y actualiza
           `last_reminded_at` para evitar spam.
- [x] 9.27 Backoffice: `/intents` como página de primer nivel con vista de todas las
           intenciones activas de todos los usuarios; widget en dashboard; acordeón en
           `/users/{id}` con intenciones activas por agente. Acciones: completar / eliminar
           vía HTMX. Nav link "🎯 Intenciones" en la barra lateral.

#### Etapa G — Proactividad de Agentes

```
Los agentes pueden generar intenciones sin esperar un comando del usuario.
Un scheduler asyncio en el core ejecuta proactive_check() por agente a intervalos
configurables. Por cada usuario registrado, el agente recibe su contexto vigente y
decide qué intenciones crear (lluvia prevista, evento próximo, precio en umbral, etc.).
El resultado se persiste vía intent_state.py; la inyección y entrega ya están resueltas
por Etapas E y F. No requiere infraestructura nueva: solo el scheduler y la implementación
en cada agente.

Triggers soportados en esta etapa: intervalo fijo en segundos.
Extensiones futuras: cron expressions, triggers por evento HAOS.
```
- [x] 9.28 `core/proactive.py` — `ProactiveScheduler`: registra agentes que declaren
           `proactive_schedule: int` (segundos de intervalo) y
           `async proactive_check(user_id: str, user_ctx: dict) → list[dict]`.
           Corre un loop asyncio independiente por agente: `sleep(interval)` → itera todos
           los usuarios registrados → llama `proactive_check` por usuario → persiste los
           intent_updates retornados via `intent_state.upsert()`.
           Anti-spam: si ya existe un intent activo con el mismo `title` para ese user+agent,
           no crea uno nuevo (el agente puede forzar actualización pasando `intent_id` explícito).
           Mantiene metadata `{last_run_at, next_run_at, last_intents_created, total_created}`
           por agente; expuesta vía `scheduler.status()`.
- [x] 9.29 `core/server.py` — wiring del scheduler en `lifespan()`: instanciar `ProactiveScheduler`,
           registrar agentes de `AGENTS` que cumplan el protocolo, lanzar
           `asyncio.create_task(scheduler.run_all())` al startup.
           `GET /proactive/status` → retorna `scheduler.status()` (dict por agent_id).
           `POST /proactive/{agent_id}/run` → trigger manual inmediato para ese agente,
           retorna `{agent_id, users_checked, intents_created}`.
- [x] 9.30 `core/clima_agent.py` — implementar proactividad:
           `proactive_schedule = 21600` (cada 6h).
           `proactive_check`: consulta Open-Meteo para hoy y mañana usando la ubicación del
           user_ctx (`preferred_location`) o la config default del agente.
           Genera intents según umbrales: precipitación diaria > 5mm o prob > 60% →
           `"⛈ Lluvia prevista — llevá paraguas"`; temperatura máxima > 35°C →
           `"🥵 Calor extremo (X°C) — hidratate"`;
           temperatura mínima < 3°C → `"🧊 Noche fría (X°C) — cerrá ventanas"`;
           viento > 50km/h → `"💨 Viento fuerte previsto"`.
           Un intent por tipo de alerta; no genera si ya existe uno activo con el mismo título.
- [x] 9.31 `core/agenda_agent.py` — implementar proactividad:
           `proactive_schedule = 3600` (cada 1h).
           `proactive_check`: consulta CalDAV del usuario (si está configurado); por cada
           evento que comience en las próximas 2h genera intent
           `"📅 <nombre evento> en X min (<hora>)"`.
           Deduplicación: guarda el `event_uid` de CalDAV en el `context` del intent;
           si ya existe un intent activo con ese `event_uid`, lo omite.
           No corre para usuarios sin CalDAV configurado (retorna `[]`).
- [x] 9.32 Backoffice `templates/agent_detail.html` — sección "Proactividad":
           Badge `🔄 proactivo` junto al nombre del agente si `agent.proactive_schedule` existe.
           Sección nueva con: intervalo declarado (ej: "cada 6h"), timestamp del último run,
           cantidad de intents creados en el último run, próximo run estimado.
           Botón "Ejecutar ahora" → `hx-post` → muestra resultado inline sin recargar.
- [x] 9.33 Backoffice `server.py` — proxy `GET /proactive/status` y
           `POST /proactive/{agent_id}/run` (retorna fragmento HTML con el resultado).
           `agent_detail_page()` llama `/proactive/status` y pasa `proactive_info[agent_id]`
           al template.
- [x] 9.34 `core/proactive.py` — filtro RBAC + control `proactive_enabled` por usuario:
           `_run_agent()` comprueba RBAC antes de llamar `proactive_check` para cada usuario.
           Lee campo `proactive_enabled` del contexto del usuario para ese agente (default True);
           si es `False`, omite al usuario silenciosamente.
- [x] 9.35 Backoffice `user_detail.html` + `server.py` — control total del usuario sobre
           proactividad: sección "Proactividad" con toggle opt-in/opt-out por agente (HTMX).
           "Contexto aprendido": botón eliminar por campo individual (HTMX, proxy ya existe).
           "Intenciones activas": agrupadas por agente, botones "Hecha" y "Cancelar" por intent
           (HTMX PATCH al proxy ya existente, la fila desaparece al confirmar).
           `user_detail_page()` recibe `proactive_status` del core.
- [x] 9.36 Backoffice `/agents` — lazy-load de columna "Accesible":
           `agents_page()` usa `/agents-meta` (5ms, sin connectivity checks) en lugar de `/agents` (28s).
           `/agents-meta` extendido con `desc`, `status`, `proactive_enabled`, `fancy_name`, `dynamic`.
           Columna "Accesible" muestra spinner en render inicial; HTMX GET a `/api/agents/{id}/reachable`
           carga el estado por fila en paralelo (~1-2s/fila).
           Nuevo endpoint `/agents/{id}/reachable` en core: chequea backends de un agente individual.
           Backoffice proxy `/api/agents/{id}/reachable` retorna fragmento HTML directamente.
- [x] 9.37 Backoffice `user_detail.html` — campos de `user_context_schema` siempre visibles y editables:
           Sección "Contexto por agente" usa `/agents-meta` para iterar schemas declarados.
           Agentes con schema: controles input/select pre-llenados (visibles aunque no haya valor).
           Agentes sin schema: read-only con botón eliminar (comportamiento original).
           `POST /users/{uid}/context/{agent_id}/{field}` persiste via PATCH al core.
- [x] 9.38 Fix: `proactive.py` — intent status del LLM no se persistía en `_persist_proactive_item()`.
           `_intent_state.upsert()` se llamaba sin el campo `status`, reseteando siempre a "active".
           El LLM marcaba intents como "done" con notify_message → WA se reenviaba cada hora.
           Fix: pasar `status=item.get("status")` en los casos advise y request. También: pasar
           `user_id` a `_send_wa_notification()` desde `_run_agent()` (inconsistencia con run_for_user_stream).
           Regresión cubierta en `tests/test_proactive_persist.py`.

---

### FASE 11 - Agente Amigo / Asesores Personales
```
Objetivo: Agente conversacional con quien charlar libremente, pedir consejos o consultar
          a un asesor especializado. Sin intención de acción — respuestas en lenguaje
          natural, tono informal, memoria entre sesiones.
Estado:   EN CURSO (1/8 — arrancada; faltan asesores personales)
Deps:     FASE 1 (stack base) — puede implementarse en cualquier momento.
          FASE 2.5 (usuarios) deseable para asociar perfiles por persona.
          FASE 3 (orquestador) necesario para coexistir con múltiples agentes.
Nota:     El agente base (11.1–11.3) puede arrancar hoy: solo requiere un nuevo
          system prompt y lógica de dispatch. Los perfiles múltiples y la memoria
          persistente escalan naturalmente sobre esa base.
```

#### Por qué un "amigo" y no solo el LLM en modo libre

El LLM ya está disponible, pero sin contexto ni personalidad producirá respuestas
genéricas y frías. El valor del agente-amigo está en:
- **Personalidad consistente**: nombre, forma de hablar, valores propios
- **Memoria entre sesiones**: recuerda lo que hablaron la semana pasada
- **Perfiles múltiples**: podés charlar con "el amigo de siempre" o consultar
  al "asesor financiero" o al "coach de vida", cada uno con su expertise y tono
- **Contexto del usuario** (FASE 2.5): sabe quién habla y adapta la respuesta

#### Diseño de perfiles

Cada perfil es un YAML con:
```yaml
id: coach
nombre: Marcos
tono: directo y motivador, no da vueltas
expertise: [coaching de vida, productividad, hábitos]
prompt_extra: |
  Hacés preguntas concretas antes de dar consejos. No te quedás en lo abstracto.
  Usás ejemplos reales. Si el usuario no sabe qué quiere, lo ayudás a clarificarlo.
```

El agente carga el perfil y lo inyecta como system prompt enriquecido.
La selección de perfil puede ser explícita ("che, hablo con el coach") o
automática según el contexto del pedido.

#### Tareas
- [ ] 11.1  Agente conversacional base: system prompt de "amigo" en lenguaje natural,
            sin formato ACTION, respuestas libres. Dispatch activado cuando no hay
            intención domótica clara y el usuario quiere charlar.
- [ ] 11.2  Perfil del amigo: YAML configurable (nombre, tono, expertise, prompt_extra).
            Un perfil por defecto "amigo general" cargado al arrancar.
- [ ] 11.3  Detección de intención conversacional en el dispatcher: distinguir
            "prende la luz" (haos) de "che, cómo estás" o "necesito un consejo" (amigo).
- [ ] 11.4  Perfiles múltiples: registro de perfiles en YAML, selección por nombre
            explícito ("hablo con el coach") o por detección de tema.
- [x] 11.5  Memoria persistente entre sesiones: historial de conversaciones por
            (agent_id, user_id) en ~/.local/share/capitan/history_*.json, max 40 turnos,
            escritura atómica. GenericAgent inyecta historial al primer turno de cada sesión.
            Los datos nunca salen de la red local.
- [ ] 11.6  Asesores especializados: perfiles con expertise marcado y prompt enriquecido
            con contexto del área (finanzas, nutrición, coach de vida, etc.).
            El asesor puede combinar conocimiento propio del usuario (FASE 2.5)
            con su expertise: "sabiendo que invertís en acciones, te diría que..."
- [ ] 11.7  Integración con FASE 2.5: cada usuario registrado puede configurar
            su perfil de amigo/asesor preferido, persistido en su perfil de usuario.
- [ ] 11.8  Dashboard: panel o indicador en panel_agents mostrando el amigo activo
            y el perfil en uso cuando la conversación es con el agente-amigo.

---

### FASE 10 - Infraestructura de Inferencia Distribuida
```
Objetivo: Romper la asunción de que todos los modelos corren en un único Ollama local.
          Abstraer el cliente de inferencia para soportar múltiples nodos/backends dentro
          de la red, cada uno con hardware y modelos optimizados para distintos agentes.
Estado:   Pendiente
Deps:     FASE 8 (servidor dedicado operativo), FASE 3 (orquestador con agentes múltiples)
Cuándo empezar: cuando el primer servidor dedicado esté funcionando y aparezca la primera
                necesidad de hardware diferenciado por agente (ej: modelo 32b que no cabe
                en el mismo nodo que los modelos generales).
```

#### Por qué un único Ollama es una limitante

Un solo servidor Ollama comparte VRAM/RAM entre todos los modelos. Esto implica:
- Techo físico: no podés correr simultáneamente un modelo 32b y varios 7b en la misma GPU
- Acoplamiento de hardware: modelos con necesidades distintas (VRAM alta, CPU offload,
  quantización diferente) compiten por el mismo recurso
- Sin escala horizontal: si un agente está saturado, no podés agregar capacidad sin
  replicar todo el nodo
- Lock-in de framework: Ollama no es el único runtime; vLLM, llama.cpp server y TGI
  ofrecen mejor throughput o soporte para modelos específicos

#### Diseño: mesh de inferencia

```
core/inference_client.py     ← cliente agnóstico, API compatible OpenAI
core/node_registry.py        ← catálogo de nodos con health check

Nodos posibles en la red:
  ollama-principal  (RTX 4090, 24GB VRAM)  → modelos generales 7b-14b
  ollama-secundario (RTX 3060, 12GB VRAM)  → coordinator 3b, fallback
  vllm-node         (multi-GPU futuro)      → modelos 32b-72b
  cpu-node          (NAS / RPi)             → modelos livianos, emergencia
```

Config por agente (YAML o env), reemplaza el hardcoding actual:
```yaml
agents:
  finance:   {endpoint: "http://gpu-2:11434", model: "qwen2.5:32b"}
  coordinator: {endpoint: "http://gpu-1:8000", model: "qwen2.5:3b"}  # vLLM
  climate:   {endpoint: "http://gpu-1:11434", model: "qwen2.5:7b"}
  fallback:  {endpoint: "http://cpu-node:11434", model: "qwen2.5:7b"}
```

Todos los backends exponen API compatible OpenAI — el cliente es el mismo,
solo cambia la URL y el modelo.

#### Etapa A — Abstracción del cliente de inferencia
- [ ] 10.1  inference_client.py: cliente HTTP compatible OpenAI (Ollama, vLLM, llama.cpp server, TGI)
- [ ] 10.2  Config por agente en YAML: endpoint + model (reemplaza OLLAMA_URL hardcodeado en agent_registry.py)
- [ ] 10.3  Migrar todos los agentes existentes a inference_client.py sin cambios de lógica

#### Etapa B — Mesh de nodos
- [ ] 10.4  node_registry.py: catálogo de nodos con URL, modelos disponibles, tipo de hardware y estado
- [ ] 10.5  Health check periódico por nodo: disponibilidad, latencia media, modelos cargados en memoria
- [ ] 10.6  Routing agente → nodo: el orquestador consulta node_registry y elige el nodo óptimo disponible

#### Etapa C — Resiliencia
- [ ] 10.7  Fallback automático: si el nodo primario no responde, redirigir al nodo alternativo configurado
- [ ] 10.8  Circuit breaker por nodo: marcar como no disponible tras N fallos, recuperación automática con backoff
- [ ] 10.9  Cola de requests: encolar si todos los nodos del agente están saturados en lugar de devolver error

#### Etapa D — Observabilidad
- [ ] 10.10 Métricas por nodo: latencia p50/p95, tokens/s, requests en vuelo, errores
- [ ] 10.11 Panel en dashboard: estado del mesh, nodos activos, modelos cargados, latencia en tiempo real
- [ ] 10.12 Alerta si un nodo cae: notificación por WhatsApp (vía FASE 3.5) o TTS en el agente de voz

---

### FASE 12 - Backoffice Web
```
Objetivo: Panel web local para explorar y configurar toda la red de agentes sin tocar archivos
          ni endpoints crudos. Reemplaza el acceso directo a .env, logs y shared_state.
          Accesible desde cualquier dispositivo de la LAN (tablet, teléfono, laptop).
Estado:   COMPLETA
Deps:     FASE 3 (core API — ya completa). No requiere agentes futuros para arrancar.
          Cobra más valor cuando hay ≥3 agentes activos (FASE 5-6).
Cuándo:   Puede empezarse en cualquier momento. Recomendado después de FASE 5.
```

Stack elegido:
- Servicio FastAPI separado en :8080 (no acoplar admin al core de agentes)
- Jinja2 + Tailwind CDN + HTMX (sin build step, coherente con "todo Python, todo local")
- Server-Sent Events (SSE) para dashboard y log viewer en tiempo real
- Token de autenticación en .env, cookie de sesión httponly

#### Infraestructura base
- [x] 12.1  Nuevo servicio `backoffice/server.py` en :8080:
            FastAPI + Jinja2 templates + Tailwind CDN, layout base con sidebar de navegación
            y header con indicadores de estado (Ollama/HAOS/core up/down)
- [x] 12.2  Autenticación básica: `BACKOFFICE_TOKEN` en .env, cookie de sesión httponly.
            Sin auth no se expone .env ni shared_state al resto de la LAN
- [x] 12.3  Heartbeat de "ears": `listen.py` registra en /tmp/capitan/devices.json al arrancar
            y cada 60s (hostname, PID, estado, última actividad). Base para la sección Dispositivos.
- [x] 12.4  Systemd unit `capitan-backoffice.service` (user), arranca junto con core

#### Secciones del panel
- [x] 12.5  **Dashboard**: servicios activos (Ollama / HAOS / core / backoffice), última actividad
            (polling de `/tmp/capitan/history.json` + `/health`), latencias promedio de la sesión,
            alertas pendientes en cola. Vista principal al entrar.
- [x] 12.6  **Agentes**: tabla completa del registry (nombre, estado, keywords, descripción),
            toggle active ↔ planned sin reiniciar el core, enlace a docs/fuente de cada agente
- [x] 12.7  **Shared State**: tabla en tiempo real de todas las claves (vía `GET /shared-state`),
            TTL restante, valor, botón eliminar entrada. Auto-refresco via HTMX polling
- [x] 12.8  **Conversaciones**: listado paginado (vía `GET /conversations`), filtro por estado
            (active/closed/expired), ver turns completos de una conversación, cerrar manualmente
- [x] 12.9  **Estadísticas**: latencias p50/p95 por agente (STT/LLM/total), comandos por hora
            (gráfico temporal), agentes más usados, errores frecuentes. Fuente: history.json acumulado
- [x] 12.10 **Alertas**: reglas activas de cada agente con cooldown restante (desde shared_state),
            historial de últimas N alertas emitidas, botón "emitir alerta de prueba" para debug
- [x] 12.11 **Configuración**: editor de `.env` del core estructurado por sección
            (HAOS, Ollama, Clima, Alertas, Ubicación), validación de campos, guardar y recargar
            el provider/cliente sin reiniciar el proceso completo
- [x] 12.12 **Dispositivos**: lista de "ears" activos (desde devices.json heartbeat),
            hostname, estado, mic en uso, última actividad. Útil cuando hay múltiples instancias
            (laptop + tablet + RPi, etc.)
- [x] 12.13 **Usuarios**: stub integrado con FASE 2.5 — lista de usuarios registrados, rol,
            si tiene modelo de speaker entrenado, fecha de enrollment. Operativo cuando FASE 2.5 esté activa
- [x] 12.14 **Log viewer**: SSE con `journalctl --user -u capitan* -f` en tiempo real,
            filtro por servicio (core / ear / backoffice), color por nivel (INFO/WARN/ERROR)
- [x] 12.15 **Integraciones**: test de conexión on-demand a HAOS / Ollama / proveedores de clima,
            lista de entity_ids mapeados en ha_client.py, estado de modelos cargados en Ollama

- [x] 12.16 **Página global de wake word** — mover la acción de entrenamiento fuera del
            contexto por-usuario (hoy el botón "Entrenar wake word" vive en user_form/user_detail,
            pero el retrain es TRANSVERSAL: combina las muestras de todos los usuarios en un único
            modelo compartido — la UX engaña). Nueva sección "Wake word" en system settings que
            muestre la salud real del modelo: total de positivos (TTS base + reales por usuario,
            con desglose), total de negativos (genéricos + capturados de nodos), métricas del
            último training (val_accuracy, fp_rate, fecha), un solo botón "Entrenar" + estado en
            vivo, y aviso si el dataset está desbalanceado. La página por-usuario mantiene solo
            su contador de muestras + "Agregar muestras" (su contribución al modelo compartido),
            sin botón de entrenar. Dispara el mismo POST /wakeword/train; los nodos bajan el
            modelo nuevo solos (16.17).

- [x] 12.17 **Backoffice mobile-friendly** — el backoffice se usa desde el celular; hoy el
            layout (sidebar fijo, tablas anchas, grids de 3 columnas) no es responsive. Hacer
            el layout adaptable: sidebar colapsable/hamburguesa en pantallas chicas, tablas con
            scroll o cards en mobile, grids que bajen a 1 columna, tamaños táctiles. Verificar
            las vistas principales (usuarios, wake word, agentes, chat, logs).

---

### FASE 13 - Agente NotebookLM
```
Objetivo: Wrapper sobre NotebookLM — consultar notebooks, agregar fuentes y recibir respuestas
          desde voz o WA, sin salir de la red de agentes.
Estado:   Pendiente
Deps:     FASE 3.2 (orquestador), FASE 3.5 (WA — canal ideal para queries largas y URLs)
API:      No hay API oficial pública. Opciones en orden de preferencia:
          1. Cliente HTTP no oficial (reverse-engineered): más liviano, sin browser
          2. Playwright browser automation: más robusto ante cambios de API
          Elegir en 13.1 según estado actual de librerías disponibles.
Auth:     Google OAuth2 — device flow para el primer login, token refresh automático,
          credenciales persistidas en ~/.local/share/capitan/ (fuera del repo)
```
- [ ] 13.1  Evaluar stack de acceso: testear cliente HTTP no oficial (PyPI/GitHub) vs Playwright.
            Criterios: funciona con cuenta personal, soporta query + add_source, se mantiene activo.
            Documentar decisión y dependencias necesarias.
- [ ] 13.2  Autenticación Google OAuth2: device flow para primer login, refresh automático del token,
            credenciales en ~/.local/share/capitan/notebooklm_token.json (gitignored)
- [ ] 13.3  notebooklm_client.py: listar notebooks (id, título, nro de fuentes), obtener notebook por nombre/id
- [ ] 13.4  Query: preguntar a un notebook específico → respuesta con citas de fuentes
- [ ] 13.5  Gestión de fuentes: agregar URL, PDF local o texto plano a un notebook específico
- [ ] 13.6  Notebook activo en shared_state: configurar cuál se usa cuando no se especifica nombre,
            persistido cross-session en shared_state["notebooklm.active_notebook"]
- [ ] 13.7  NotebookLMAgent: implementar BaseAgent, keywords de dispatch, manejo de intención
            ("preguntá", "consultá", "qué dice", "agregá fuente", "notebook de X")
- [ ] 13.8  Comandos de voz: "preguntale al notebook de inversiones si GGAL vale la pena",
            "agregá esta URL al notebook de viajes", "qué dice el notebook sobre el ayuno"
- [ ] 13.9  Canal WA: soporte para queries largas (sin límite de audio), pegar URLs en el chat
            para agregarlas como fuente al notebook activo o a uno nombrado
- [ ] 13.10 Dashboard: panel en backoffice con lista de notebooks, notebook activo, última consulta
            y estado del token OAuth (válido / expirado / no configurado)

---

### FASE 14 - Gestión dinámica de agentes desde el backoffice
```
Objetivo: Hacer que status, keywords y configuración específica de cada agente sean editables
          desde el backoffice sin tocar código. Persiste en ~/.local/share/capitan/agents.json.
          Nuevos agentes aparecen automáticamente al declarar su config_schema.
Estado:   COMPLETA
Stack:    core/agent_config.py (nuevo) + backoffice/templates/agent_edit.html (nuevo)
Nota:     Cambios de config/keywords aplican en el próximo reinicio del core.
          Toggle de status aplica en runtime (el dispatcher lee el registry en cada llamada).
```
- [x] 14.1  `core/agent_config.py` — persistencia de config de agentes en JSON
            (singleton + atomic write, mismo patrón que users.py); migrate_from_env()
            migra valores de clima del .env al JSON on first run
- [x] 14.2  `core/agent_registry.py` — `get_registry()` que fusiona REGISTRY estático + overrides
            del JSON; dispatcher y agent_status() usan keywords/status efectivos
- [x] 14.3  `core/server.py` — 4 endpoints nuevos: GET /agents/{id},
            PATCH /agents/{id}/status, /agents/{id}/keywords, /agents/{id}/config;
            GET /agents enriquecido con config_schema, config y reachable (availability_url check)
- [x] 14.4  `core/agent.py` (HaosAgent) — config_schema (model, top_k_entities, max_retries),
            __init__ lee agent_config, availability_url → HAOS_URL/api/
- [x] 14.5  `core/clima_agent.py` (ClimaAgent) — config_schema (model, provider, lat, lon,
            location_name), __init__ con cadena agent_config > .env > default,
            availability_url → Open-Meteo; weather_providers.load_provider acepta name opcional
- [x] 14.6  `backoffice/templates/agents.html` — toggle HTMX real por fila, columna Accesible
            (●/—), columna Editar con link a /agents/{id}/edit
- [x] 14.7  `backoffice/templates/agent_edit.html` (nuevo) — form con status radio + indicador
            de conectividad, textarea de keywords, campos dinámicos según config_schema
- [x] 14.8  `backoffice/server.py` — toggle real (alterna active ↔ planned via PATCH al core),
            GET/POST /agents/{id}/edit con conversión de tipos para config

- [x] 14.9  `core/agent_config.py` — soporte para agentes dinámicos: `create_dynamic_agent()`,
            `delete_dynamic_agent()`, `is_dynamic()`; flag `dynamic: true` en agents.json
- [x] 14.10 `core/agent_registry.py` — `get_registry()` incluye agentes dinámicos del JSON;
            `is_static_agent()` protege de eliminación a los del REGISTRY hardcodeado
- [x] 14.11 `core/server.py` — POST /agents (crear dinámico), DELETE /agents/{id} (solo dinámicos);
            fix PATCH endpoints para usar get_registry() en lugar de REGISTRY estático
- [x] 14.12 `backoffice/templates/agent_edit.html` — sección RBAC: checkboxes de roles que tienen
            acceso al agente; aplica a estáticos y dinámicos; POST actualiza /rbac/roles/{role}
- [x] 14.13 `backoffice/templates/agent_new.html` — form de creación: id, nombre, icono, desc,
            status, keywords, roles por defecto
- [x] 14.14 `backoffice/server.py` — GET/POST /agents/new, DELETE /agents/{id} (HTMX),
            + RBAC aplicado al guardar edición y al crear; badge 'dinámico' en agents.html
- [x] 14.15 `core/generic_agent.py` (nuevo) — GenericAgent(agent_id): relay LLM puro con
            system_prompt y model configurables via agents.json; process() usa conv.context()
            y devuelve respuesta del LLM directamente, sin parseo ni llamadas a APIs externas
- [x] 14.16 `core/server.py` — carga GenericAgent para todos los agentes dinámicos al arrancar;
            POST /agents instancia y agrega a AGENTS; DELETE elimina de AGENTS;
            PATCH /config re-instancia GenericAgent para aplicar cambios sin reiniciar;
            agent_config.create_dynamic_agent acepta agent_type y system_prompt
- [x] 14.17 `backoffice/templates/agent_new.html` — sección System prompt (textarea required);
            agent_edit.html: type='text' en config_schema renderiza como textarea;
            backoffice/server.py: system_prompt en payload de POST /agents
- [x] 14.18 `core/generic_agent.py` — campo backend (select:[ollama]) en config_schema;
            model pasa a type='select' con options='ollama_models';
            process() despacha según backend; agent_config y server.py aceptan y persisten
            backend y model como config explícita en agents.json
- [x] 14.19 `backoffice`: sección Backend y modelo en agent_new.html (select Ollama + dropdown
            de modelos desde API); agent_edit.html: type='select' renderiza <select> con
            opciones estáticas o dinámicas (ollama_models); /devices redirige a /ear;
            ear.html: card Dispositivos integrada; base.html: quita nav link Dispositivos

---

### FASE 15 - Agente Multimedia
```
Objetivo: Control de música y video por voz en cualquier dispositivo del hogar.
          Fuente principal: YouTube Music (ytmusicapi + yt-dlp).
          Dispositivos: Smart TV y parlantes WiFi vía HAOS media_player;
          parlantes Bluetooth conectados a la laptop vía mpv + PipeWire.
Estado:   Pendiente
Deps:     FASE 3 (agent_registry), FASE 12 (backoffice)
Stack:    ytmusicapi (OAuth), yt-dlp (stream resolver), HAOS media_player service,
          mpv (local), PipeWire/pactl (BT sink routing)
```
- [ ] 15.1  `core/music_search.py` — integración ytmusicapi con OAuth persistente en
            `~/.local/share/capitan/ytmusic_oauth.json`. Funciones: search_tracks(query),
            search_albums(query), get_playlist(id). One-time OAuth flow documentado.
            Config en .env: `YTMUSIC_OAUTH_PATH`.
- [ ] 15.2  `core/stream_resolver.py` — dado un YouTube Music URL o video ID, usa yt-dlp
            en modo programático para obtener la mejor URL de stream de audio (para parlantes)
            o video+audio (para TV). Cachea el resultado 30min para evitar re-resolución.
- [ ] 15.3  Registro de dispositivos multimedia: `~/.local/share/capitan/media_devices.json`.
            Cada entrada: `{id, name, aliases, type: "haos"|"local", entity_id?, sink?}`.
            Ejemplos: tv del living (haos, media_player.samsung_tv), parlante cocina (local, sink BT).
            API CRUD: `GET/POST/PATCH/DELETE /media/devices`.
- [ ] 15.4  `core/multimedia_agent.py` — agente con intents: play(query, device),
            pause(device), resume(device), stop(device), volume(level, device), next_track(device),
            what_playing(device). Para tipo "haos": HAOS media_player service. Para tipo "local":
            mpv subprocess con `--audio-device=pipewire/<sink>` y control via IPC socket.
            Alias "todos" / "todo" → broadcast a todos los dispositivos activos.
- [ ] 15.5  Parsing de lenguaje natural: extraer intent + búsqueda + dispositivo destino de
            frases como "poné cumbia en el living", "subí el volumen de la tele", "qué está
            sonando", "pausá todo", "siguiente canción", "poné el playlist de los sábados".
            Dispositivo opcional: si falta, usar el último activo o el primero disponible.
- [ ] 15.6  Backoffice `/media`: estado actual por dispositivo (qué suena, volumen, progreso),
            controles rápidos por tarjeta (play/pause/vol/next), lista de dispositivos con
            estado online/offline. Actualización vía HTMX polling.
- [ ] 15.7  Backoffice configuración YouTube Music: sección en `/config` o `/integrations`
            con estado del token OAuth (válido / expirado / no configurado), botón para
            iniciar/renovar el flujo OAuth, instrucciones step-by-step.

---

### FASE 16 - Red de Nodos de Audio Multi-Ambiente

```
Objetivo: Distribuir la interfaz de voz por toda la casa. Los NSPanel Pro (Android, Termux)
          son los únicos puntos de captura y reproducción de audio. El ear corre en el Brain
          como servidor de audio puro (sin hardware local): recibe audio de los NSPanels,
          corre STT+TTS, delega al core, devuelve el WAV de respuesta.
          La laptop queda 100% desarrollo sin servicios.
Estado:   EN CURSO (22/30 — pipeline nodo+voice-id+enrollment+paneles+observabilidad operativo.
          Pendientes: 16.6/16.7/16.9-16.12 (multi-nodo/room routing, diferibles hasta tener más
          paneles) y 16.13/16.14 (RPi — ⏸ POSTERGADAS hasta comprar el hardware).)
Deps:     FASE 1 (STT, TTS, Piper), FASE 3 (core/server.py, /process),
          FASE 21 (Brain operativo — COMPLETA), FASE 2.5 (speaker_id), FASE 12 (backoffice)
Hardware: NSPanel Pro — Android 8.1, sounddevice/PortAudio, mic (pcmC0D0c) + speaker (pcmC0D0p).
          Termux + Python instalados. HA Companion como dashboard. ADB over WiFi.
          Brain LXC — ear como servidor HTTP/WebSocket, STT+TTS sin /dev/snd local.
Nota:     Completa también 21.21 (decisión ear). Ver Anexo A.2 (origen).
```

#### Etapa A — Protocolo y nodo satélite básico
- [x] 16.1  Protocolo nodo↔servidor: especificación de mensajes WebSocket para streaming
            de audio en chunks. Estructura de chunk: `{node_id, room, chunk_b64, sample_rate}`.
            El nodo envía chunks post-wake-word; el core responde con texto de respuesta.
            Fallback: POST HTTP con el audio completo si WebSocket no disponible.
            Nota de diseño multi-nodo: el mensaje de handshake inicial (al conectar) debe
            incluir un campo `capabilities: {tts_local, mic_channels, hw_type}` para que el
            servidor adapte el formato de respuesta sin asumir el tipo de hardware. La respuesta
            TTS del servidor debe ser tipada: `{type: "tts_wav", wav_b64}` si el nodo no puede
            sintetizar, o `{type: "tts_text", text}` si puede (ej: RPi 5 con Piper local).
            NSPanel Pro declara `tts_local: false`; RPi 5 declara `tts_local: true`.
- [x] 16.2  `ear/satellite.py` — cliente ligero para el nodo satélite: detecta wake word
            con openWakeWord (modelo capitan.onnx), captura el comando, envía chunks al
            core vía WebSocket, recibe texto de respuesta y sintetiza TTS local con Piper.
            Sin STT ni LLM locales — toda la inferencia pesada queda en la laptop central.
            Configurable: CORE_WS_URL, ROOM, DEVICE_INDEX_MIC, DEVICE_INDEX_SPK.
- [x] 16.3  Registro de nodos en `ear/audio_server.py` + `GET /nodes` — registro en memoria:
            `{node_id, room, ip, last_seen, state: active|offline}`. Auto-registro en cada
            `POST /process-audio`; estado `offline` tras NODE_TTL (120s) sin actividad.
            Implementado en el audio_server (no en core/audio_nodes.py — ver nota de
            implementación). `capabilities` queda pendiente para Etapa D (16.11).
            Nota de diseño: este registry debe ser extensible para FASE 10 (inferencia
            distribuida tiene su propio node_registry.py). Considerar base común o
            interfaz unificada para evitar dos sistemas de health-check paralelos.
- [x] 16.4  `core/ws_audio.py` — servidor WebSocket `/ws/audio` en el core: recibe chunks
            del nodo, acumula y pasa al STT local (faster-whisper), llama internamente a
            `process()` con `source.room` del nodo, devuelve el texto de respuesta al nodo.
- [x] 16.5  Propagación de `source.room` en el pipeline completo: historial,
            backoffice y dashboard muestran el ambiente de origen de cada comando.
            El campo ya existe en `source`; esta tarea lo hace obligatorio para nodos.
            Progreso: `audio_server.py` ya envía `source={room, channel:"ear"}` al core en
            cada comando. Falta verificar que historial/backoffice lo muestren.

#### Nota de implementación (Etapa A — MVP funcionando)

```
La Etapa A se implementó con HTTP (el fallback de 16.1), no WebSocket — más simple
y robusto para el MVP. Arquitectura real en producción:

NSPanel Pro (Termux)                      Brain LXC
  ear/satellite.py                          ear/audio_server.py (:8766)
  - openWakeWord (capitan.onnx)             - faster-whisper STT
  - graba comando post-wake-word            - strip wake word prefix
  - POST /process-audio (WAV)        ──→    - POST core /process
  - reproduce WAV respuesta          ←──    - Piper TTS → WAV

audio_server.py vive en ear/ (no core/) porque reusa tts.py y el modelo de STT
del ear. El registry de nodos (16.3) está embebido en audio_server.py.
Latencia end-to-end: ~5s warm.

Dependencias NSPanel (Termux): python, portaudio, onnxruntime (pkg), openwakeword
(pip --no-deps + tqdm), Termux:API (APK GitHub, da permiso RECORD_AUDIO).
Ver docs/nspanel-setup.md para el bootstrap completo.

Pendiente Etapa A: feedback sonoro tras wake word (FASE 18) — sin él, el usuario no
sabe cuándo hablar y el STT captura ruido. Es el bloqueante de UX principal.
```

#### Etapa B — Output via Echo (sin hardware nuevo)

> **DECISIÓN PENDIENTE — mapeo ambiente→Echo vs. output por panel.** El CRUD del
> mapeo Echo-por-área ya existe (16.7), pero su único consumidor (16.6
> `response_router`) no está implementado, así que hoy asignar un Echo a un ambiente
> **no produce ningún efecto**. Antes de implementar 16.6 hay que decidir el modelo de
> salida de audio:
>   (a) **Echo por ambiente** — la respuesta TTS sale por el Echo del área de origen
>       vía `media_player.play_media`. Pro: aprovecha parlantes ya instalados. Contra:
>       depende de hardware cerrado de Amazon, latencia extra (subir WAV a HAOS), y
>       el mapeo área→Echo es config manual a mantener.
>   (b) **Output por el propio panel/nodo** — la respuesta vuelve por el speaker del
>       NSPanel/nodo que originó el comando (mismo dispositivo que ya capturó el audio).
>       Pro: cero config de routing, el origen ya se conoce (`source.node_id`), sin
>       dependencia de Amazon. Contra: calidad de parlante del NSPanel.
> Si se elige (b), el mapeo ambiente→Echo y la tabla de `/rooms` quedan obsoletos para
> output (podrían seguir sirviendo a los Echo solo como entidad-objetivo de comandos).
> Resolver esto define si 16.6 se hace, se reescribe o se descarta.

- [ ] 16.6  `core/response_router.py` — routear la respuesta al speaker correcto según
            `source.room`. Si el room tiene un Echo asignado: sintetizar TTS a WAV y
            reproducir via HAOS `media_player.play_media`. Si no: TTS local como ahora.
            Tabla de routing: `room → entity_id` configurable en `.env` o agents.json.
            Nota de diseño multi-nodo: si el nodo origen tiene `capabilities.tts_local: true`
            (RPi 5), enviar `{type: "tts_text"}` en lugar de WAV — el nodo sintetiza con
            Piper local, menor latencia y sin saturar el WebSocket con audio. El path Echo
            es ortogonal: aplica cuando el room tiene Echo asignado, independiente del nodo.
- [x] 16.7  Backoffice `/rooms` — CRUD de ambientes. Fuente de verdad = áreas de HAOS
            (ha_client.get_areas vía /api/template). Tabla edita el media_player/Echo por área
            y muestra paneles bindeados; alta de panel elige el área de HA (dropdown). Binding
            panel→area_id. Backend PR core #200 (+ fix config HAOS doc store), frontend #555.

#### Etapa C — Observabilidad y robustez
- [x] 16.8  Health check periódico por nodo de audio: ping cada 30s desde el core,
            marcar offline si no responde en 3 intentos. Backoffice muestra estado en tiempo real.
- [ ] 16.9  Panel en dashboard zellij (`panel_nodes.py`): nodos de audio activos, ambiente
            del último comando, latencia STT+LLM por nodo, estado online/offline.
- [ ] 16.10 Guía de instalación del nodo satélite en nodo Linux genérico (referencia:
            Raspberry Pi OS): dependencias (Python, openWakeWord, Piper, pyaudio/sounddevice),
            configuración de audio (ALSA), systemd service con auto-reconexión, verificación
            end-to-end. Aplica a cualquier SBC Linux — RPi Zero 2W, RPi 5, etc.

#### Etapa D — Nodo potenciado: RPi 5 + pantalla oficial + ReSpeaker hat

```
Objetivo: Soportar un segundo tipo de nodo con más capacidades que el NSPanel Pro:
          mic array (4 canales, beamforming), TTS local con Piper, pantalla Linux (Chromium
          kiosk) y pleno control de ALSA. El protocolo de Etapa A es idéntico — la
          diferencia está en las capabilities declaradas en el handshake y en cómo el
          servidor y el nodo adaptan el pipeline de respuesta.
          NSPanel Pro sigue funcionando sin cambios.
Hardware: Raspberry Pi 5 (4GB+) + pantalla oficial 7" o 10" + ReSpeaker 4-mic hat (seeed).
          Alimentación directa (USB-C) o PoE hat para montaje en pared sin cables visibles.
```

- [ ] 16.11 Schema de capabilities para el handshake de registro. Definir el objeto canónico:
            `{hw_type: "nspanel"|"rpi5"|"generic", tts_local: bool, mic_channels: int,
            stt_local: bool, has_display: bool, display_type: "none"|"ha_companion"|"browser"}`.
            NSPanel Pro: `{hw_type:"nspanel", tts_local:false, mic_channels:1, stt_local:false,
            has_display:true, display_type:"ha_companion"}`.
            RPi 5: `{hw_type:"rpi5", tts_local:true, mic_channels:4, stt_local:false,
            has_display:true, display_type:"browser"}`.
            El servidor nunca bifurca por `hw_type` — solo por las capabilities booleanas.
            Retrocompatible: nodos que no envíen capabilities asumen el perfil NSPanel (defaults).
- [ ] 16.12 TTS bifurcado por capability en `ws_audio.py`: si `node.capabilities.tts_local`
            → enviar `{type:"tts_text", text:"..."}` al nodo (sintetiza con Piper local).
            Si no → enviar `{type:"tts_wav", wav_b64:"..."}` como hace hoy con NSPanel.
            El nodo NSPanel existente ignora mensajes de tipo desconocido — no se rompe.
- [ ] 16.13 ⏸ POSTERGADA (hasta comprar hardware RPi) — `ear/satellite_rpi.py` — cliente satélite nativo Linux para RPi 5:
            mismo protocolo WS que `satellite.py`, declara capabilities RPi 5.
            Audio: ALSA / sounddevice apuntando al ReSpeaker (plughw:seeed4micvoicec,0),
            captura en 16kHz (ReSpeaker lo soporta nativamente — sin resampleo).
            TTS: Piper local con voz daniela, ffplay, igual que el ear actual.
            Configurable: CORE_WS_URL, ROOM, DISPLAY_URL (URL del dashboard HA para Chromium).
- [ ] 16.14 ⏸ POSTERGADA (hasta comprar hardware RPi) — Setup guide RPi 5 + pantalla oficial + ReSpeaker hat:
            Raspberry Pi OS Lite (64-bit), seeed-voicecard driver, Piper TTS, Chromium en
            kiosk mode (`/etc/xdg/autostart/kiosk.desktop` apuntando a DISPLAY_URL),
            rotación de pantalla si montaje vertical, systemd service `capitan-satellite.service`
            con auto-reconexión al Brain. Verificación end-to-end: wake word → STT → LLM →
            TTS local → respuesta audible + dashboard HA visible.

#### Etapa E — Mejora continua de wake word en nodos (coherencia con flujo existente)

```
Objetivo: Integrar los nodos de audio al flujo de mejora de wake word que ya existe
          (muestras → métricas TP/FP → retrain supervisado desde backoffice).
          El uso diario alimenta el dataset orgánicamente; el retrain sigue siendo manual.
          Cierra el loop: nodo detecta → alimenta dataset → retrain → modelo vuelve al nodo.
Flujo existente: core/wakeword_trainer.py (positivos TTS+reales, negativos estáticos),
          /wakeword/train (supervisado), /users/{uid}/wakeword/samples, wakeword_metrics.json.
```

- [x] 16.15 Métricas TP/FP orgánicas desde nodos: `audio_server.py` registra TP cuando el STT
            produce texto válido y FP cuando devuelve vacío/ruido tras un comando de nodo.
            Escribe en el mismo `wakeword_metrics.json` que lee el backoffice (audio_server
            corre en el Brain, co-ubicado con el core). Coherente con `_update_wakeword_metrics`
            de listen.py. El backoffice muestra las métricas de nodos sin cambios.
- [x] 16.16 Captura orgánica de muestras (gated): el nodo envía junto al comando el audio
            de la wake word que disparó la detección (el buffer pre-comando). `audio_server`:
            - FP (STT vacío) → guarda como hard negative en `wakeword/data/capitán/negative/`.
              Estos son ruido ambiente real — atacan directamente los falsos positivos.
            - TP (comando válido + speaker conocido) → sube como positivo real vía
              `/users/{uid}/wakeword/samples`. Gate anti-veneno: solo si STT no-vacío y speaker≠guest.
            El retrain (`/wakeword/train`) ya consume ambos directorios — sin cambios en el trainer.
- [x] 16.17 Propagación del modelo reentrenado a los nodos (pull): core expone
            `GET /wakeword/model` (devuelve capitan.onnx) y `GET /wakeword/model/version`
            (hash/mtime). `satellite.py` chequea la versión al arrancar y cada N minutos;
            si cambió, baja el modelo nuevo y recarga sin reiniciar. Cierra el loop de mejora
            continua: retrain en backoffice → nodos actualizados automáticamente.
- [x] 16.30 **Cap de negativos capturados (no crecer al infinito)**: hoy `_save_negative`
            guarda un hard negative por cada falso positivo del nodo, sin límite → el directorio
            `negative/` tiende a infinito (disco + dataset desbalanceado). Acotar la colección:
            límite por nodo (FIFO/rotación: al superar N, borrar los más viejos), o muestreo
            probabilístico decreciente a medida que se acumulan. Idealmente, frenar la captura
            cuando el voice-id ya suprime los FP (si el gate descarta el TV, ya no hace falta
            seguir juntando). Exponer el conteo y un "limpiar negativos viejos" en la página
            global de wake word (12.16).

#### Etapa F — Voice-ID resuelto server-side (nodo agnóstico al usuario)

```
Principio de diseño: el NODO es agnóstico al usuario — solo captura y emite audio crudo.
          Toda la inteligencia (STT, voice-id, LLM, TTS) vive en el SERVER (audio_server),
          que ya recibe el audio crudo del comando. El voice-id se resuelve ahí: el server
          identifica quién habló y el core devuelve la respuesta personalizada.
          El nodo no necesita cambios — solo el audio_server agrega el paso de identificación.
Objetivo: que los comandos de los nodos se personalicen por usuario (hoy van como 'guest').
Infra existente: ear/speaker_id.py (resemblyzer/GE2E, threshold 0.75), embeddings por
          usuario en ~/.local/share/capitan/embeddings/<uid>.npy (ya migrados al Brain),
          onboarding paso 'frases_speaker_id' que genera el embedding.
```

- [x] 16.18 Voice-ID en `audio_server.py` (server-side): tras el STT, correr
            `speaker_id.identify(audio)` sobre el comando crudo recibido del nodo y propagar
            el `speaker_id` real al core (hoy va None → 'guest'). Reusa ear/speaker_id.py +
            los embeddings migrados. El core ya consume `source.speaker_id` para personalizar
            (users, RBAC, contexto por usuario). Cargar perfiles al iniciar; recargar al
            agregar usuarios. El nodo no cambia — sigue enviando solo audio crudo.
- [x] 16.19 Gate opcional por speaker conocido (server-side): si
            `WAKEWORD_REQUIRE_KNOWN_SPEAKER=true`, el audio_server rechaza comandos cuyo
            speaker_id sea 'guest' (voz no enrolada) → devuelve 204 o un aviso. Coherente con
            el flag homónimo de listen.py. El nodo solo reproduce lo que el server devuelva.
- [x] 16.20 Enrollment de voice-id con el mic del nodo: el nodo captura frases (audio crudo)
            y las envía al audio_server, que computa el embedding (resemblyzer) y lo guarda en
            embeddings/<uid>.npy. `satellite.py --enroll-voice <uid>` + endpoint
            `/enroll-voice` en audio_server. El nodo sigue agnóstico (solo graba y manda audio);
            el server hace todo el cómputo. Coherente con 'frases_speaker_id' del onboarding.
            CLAVE: resuelve el mismatch de mic — el embedding del laptop daba 0.45 (=guest);
            re-enrolado desde el NSPanel da 0.77 (=conocido), separable del TV. Gate activado
            con SPEAKER_THRESHOLD=0.6. Slash commands `/nspanel-enroll`, `/nspanel-enroll-voice`.

#### Etapa G — Formalizar enrollment desde el backoffice (operación sin SSH)

```
Hoy los enrollments se disparan con slash commands (SSH/ADB al nodo). Para operación
normal deberían iniciarse desde el backoffice, eligiendo un nodo. El nodo es el único
con mic, así que el backoffice manda un comando al nodo (vía audio_server) para que
inicie la sesión de captura; el nodo graba y sube como hoy. Server-side computa todo.
```

- [x] 16.21 Canal de comando backoffice→nodo para enrollment: el audio_server expone un
            "enrollment pendiente" por nodo (`POST /nodes/{id}/enroll` con tipo wakeword|voice,
            user_id, N). El satellite lo consulta en su loop (o por WebSocket) y al detectarlo
            entra en modo enrollment (beeps + captura + upload), luego vuelve a escuchar.
            Evita depender de SSH/ADB para operar.
- [x] 16.22 UI de enrollment en el backoffice (dos flujos):
            (a) **Wake word (cross-user)** — desde la página global de wake word (12.16):
                botón "Capturar muestras en nodo X" → dispara 16.21 tipo wakeword → suma
                positivos al dataset compartido → luego "Entrenar".
            (b) **Voice-ID (per-user)** — desde la página del usuario: botón "Mejorar mi
                voz en nodo X" → dispara 16.21 tipo voice → re-computa el embedding del
                usuario con el mic de ese nodo. Muestra la confianza resultante.
            Estado en vivo de la sesión (grabando frase i/N, subida ok).

#### Etapa H — Provisioning multi-panel (N nodos NSPanel)

```
Puede haber N paneles (comedor, dormitorio, cocina...). Hoy se referencian por IP cruda y
el alta es manual (docs/nspanel-setup.md). Falta formalizar: un registro de paneles como
fuente de verdad y un flujo de alta guiado, para que comandos y backoffice referencien
paneles por nombre/ambiente en vez de IP.
```

- [x] 16.23 Registro de paneles (`masterplan/panels.yaml` o config): por panel → {name,
            room, ip, mac, users, node_id}. Fuente de verdad del provisioning. `scripts/nspanel.sh`
            y los slash commands resuelven panel por nombre/ambiente → IP (ej: "comedor" → .113).
            Reserva DHCP por MAC documentada. Distinto del registry runtime (16.3, GET /nodes,
            que es estado en vivo): este es de provisioning/config.
- [x] 16.24 Flujo formal de alta de panel: `nspanel.sh provision <name> <room> [ip]` que
            automatiza el bootstrap (ADB, Termux, deps, modelos, satellite, boot script,
            Termux:GUI) y registra el panel en panels.yaml. Idempotente. CLAVE: bootstrappea el
            SSH key vía ADB (root del panel) — sin password manual. Prereq físico: habilitar ADB.
- [x] 16.25 Comandos y backoffice por panel: todos los comandos que afectan a un panel
            (`/nspanel*`, enroll, etc.) aceptan el panel por **nombre/ambiente** (resuelto vía
            16.23), no solo IP cruda. El backoffice lista los paneles del registro y permite
            elegir a cuál dirigir cada acción (enrollment, reboot, ver estado).

#### Etapa I — Onboarding 100% desde el backoffice (sin SSH/ADB manual)

```
Objetivo: que un operador pueda, SOLO desde el backoffice, (1) dar de alta un panel nuevo,
(2) crear usuarios, y (3) asegurar el voice-ID de cada uno — todo end-to-end, sin tocar
una terminal. Hoy crear usuario y enrolar voz ya andan desde la web (12.x / 16.22); falta
el alta de panel desde la UI y cerrar el flujo como un wizard cohesivo y validado.
```

- [x] 16.26 **Alta de panel desde el backoffice**: página `/panels` (lista + estado
            online/offline en vivo, alta en registro, quitar) + **"Provisionar panel nuevo"**
            que corre `nspanel.sh provision` en background y streamea el log paso a paso. adb +
            zsh instalados en el LXC; el SSH se bootstrappea solo vía ADB. Validado: wiring,
            streaming, detección de fin, manejo de error (ADB no disponible). NOTA: el bootstrap
            completo contra un panel NUEVO no se probó end-to-end (no hay segundo dispositivo);
            el mecanismo y los pasos (los mismos que funcionaron para el comedor) están validados
            por partes. Prereq físico: habilitar ADB + crear usuario HA del ambiente.
            Reboot por panel desde la UI: hecho.
- [x] 16.27 **Wizard de onboarding end-to-end**: flujo guiado en el backoffice que encadena
            crear usuario → enrolar su voz en un panel (16.22b) → **validar el voice-ID**
            (medir la confianza real del usuario contra su perfil y confirmar que supera el
            umbral; si queda justa, ofrecer reforzar con más frases). Cierra el lazo: al
            terminar, el usuario queda 100% operativo (reconocido por voz) sin haber tocado
            SSH. Asegurar que la creación de usuarios y el enrollment de voz estén pulidos y
            sin pasos manuales ocultos.
            Implementado: la página del usuario tiene por panel los botones **Enrolar voz** y
            **Verificar** (mide la confianza real y muestra ✓/⚠). Crear usuario ya existía
            (/users/new). Queda como polish opcional un wizard de una sola página que encadene
            los tres pasos secuencialmente (hoy están en la misma página pero no guiados).
- [x] 16.28 **Endpoint de validación de voice-ID**: `/users/{uid}/voice-id/verify` que toma
            una muestra del nodo y devuelve (speaker_id, confidence) contra el perfil del
            usuario — usado por el wizard (16.27) para confirmar el enrollment y por el
            backoffice para mostrar la salud del voice-ID por usuario.
- [x] 16.29 **Eliminar el stack legacy de enrollment laptop-ear** (reemplazado por el
- [x] 16.31  Overlay de estado del panel intercepta el touch (paneles inusables) — sizing por wm size (PR ear #35), passthrough probado fallido, fix final: overlay se encoge a 1x1 en idle y solo cubre en estados activos (PR ear #39). Touch verificado OK
- [ ] 16.32  Reducir falsos positivos de wake word (TV/charla)
- [x] 16.33  Contexto de area por panel: el HaosAgent resuelve area del panel (source→binding 16.7) y trae nombre+entidades del area (ha_client.get_area_info vía /api/template); inyecta ubicacion+entidades del ambiente al prompt para desambiguar comandos sin lugar explicito (PR core #201)
            enrollment por nodo 16.21/16.22). El satellite del NSPanel NO lo usa. Quitar,
            asegurando que nada se rompa (con tests):
            - backoffice: rutas `/users/{uid}/onboard`, `/users/{uid}/enroll/start`,
              `/users/{uid}/enroll/status/{sid}`; helpers `_enroll_fragment`, `_ENROLL_LABELS`,
              `_NEXT_STEP`; template `user_onboard.html`; links "Agregar muestras"/"Continuar
              onboarding" en user_detail/user_form; redirect post-creación de usuario.
            - core: `enrollment_session.py` + endpoints `/enrollment/sessions*`; `onboarding.py`;
              evaluar si `onboarding_step`/`onboarding_complete` en `users.py` quedan obsoletos
              (migración de datos si se quitan).
            - ear: manejo de enrollment/onboarding en `listen.py` (laptop ear deprecado).
            - El reemplazo es la página del usuario (voice-ID por panel) + página global wake
              word + el wizard 16.27. Actualizar tests que cubran lo removido.

---

### FASE 17 - Chat Visual con la Plataforma

```
Objetivo: Interfaz de chat web para conversar con los agentes escribiendo (sin voz),
          ver qué agente respondió y qué acción ejecutó, y gestionar el historial de
          conversaciones. Es la nueva landing del backoffice — el punto de entrada
          natural para el usuario antes de ir a las secciones de administración.
Estado:   COMPLETA
Deps:     FASE 12 (backoffice, COMPLETA), FASE 9 (coordinador, COMPLETA).
          Puede arrancarse ya. FASE 2.5 (usuarios) potencia el selector de usuario (17.6).
```

Stack: FastAPI + Jinja2 + Tailwind + JS nativo (sin HTMX en el chat — SSE requiere
fetch/ReadableStream). El core expone `/process/stream` (SSE); el backoffice hace relay
o el JS apunta directamente al core. Conversaciones persistidas en localStorage del browser.

#### Infraestructura de streaming
- [x] 17.1  **SSE en core** — `POST /process/stream`: misma lógica que `/process` pero
            llama a Ollama con `stream=True` y emite eventos SSE progresivos:
            `event: token` (fragmento de texto LLM), `event: action` (ACTION ejecutada +
            entity_id + resultado HAOS), `event: done` (fin + metadata: agente, latencias
            STT/LLM/total). El endpoint `/process` existente no se toca.
- [x] 17.2  **Relay en backoffice** — `POST /api/chat/send` recibe `{text, user_id}`,
            hace streaming del SSE del core y lo retransmite al browser como SSE.
            Maneja reconexión y errores de core (core caído → evento `error` al cliente).

#### UI de chat
- [x] 17.3  **Landing y layout** — `/` redirige a `/chat`. Template `chat.html` con layout
            pantalla completa (sin sidebar, sin max-w-6xl): columna de mensajes con scroll,
            input fijo al fondo, header mínimo con "⚓ Capitán" a la izquierda y link
            "Administración →" a la derecha que lleva a `/dashboard`.
- [x] 17.4  **Render en tiempo real** — burbuja del usuario aparece al instante al enviar.
            Burbuja del agente se construye token a token via SSE. Al recibir `event: action`,
            agregar chip de metadata debajo de la burbuja (agente, acción ejecutada, latencia);
            chip empieza colapsado, expandible al hacer click.
- [x] 17.5  **Persistencia local** — turnos guardados en `localStorage` del browser.
            Al cargar `/chat`, los últimos N turnos se restauran en pantalla. Botón
            "Nueva conversación" limpia el historial local y reinicia el contexto.

#### Gestión de conversaciones
- [x] 17.6  **Selector de usuario activo** — dropdown en el header del chat con los usuarios
            registrados (llamada a `/users` del backoffice). El `user_id` seleccionado se
            envía con cada mensaje al core. Selección persistida en `localStorage`.
- [x] 17.7  **Panel lateral de historial** — botón "Historial" colapsable en el chat.
            Lista las últimas conversaciones del core (`GET /conversations`), click en una
            muestra los turnos anteriores en modo lectura (no se puede continuar, solo leer).
- [x] 17.8  **Exportar conversación** — botón en el header. Genera un JSON con los turnos
            de la sesión actual y lo descarga via `Blob + URL.createObjectURL`. Alternativa:
            botón "Copiar como markdown" para pegar en notas.
- [x] 17.9  **Persistencia de conversaciones en disco** — `ConversationManager` guarda las
            conversaciones en `~/.local/share/capitan/conversations.json` al crear/actualizar/cerrar
            cada conversación. Al iniciar el core, carga el archivo y restaura el historial completo.
            Los turnos sobreviven reinicios del proceso.

---

## PIPELINE ACTUAL (para referencia rápida)

```
[ear/listen.py]
[MIC hw:1,0 44100Hz]
        ↓
[resampleo scipy: up=160, down=441 → 16000Hz]
        ↓
[faster-whisper small, int8, CPU]  ~4.6s
        ↓
[HTTP POST localhost:8765/process]  ~10ms overhead
        ↓
[core/server.py — FastAPI]
        ↓
[qwen2.5:7b via Ollama :11434]     ~3.5s
        ↓
[parser ACTION: domain.service | entity_id: X]
        ↓
[HAOS REST API :8123]
        ↓
[ear/listen.py]
        ↓
[Piper TTS respuesta → ffplay]
```

## LATENCIAS ACTUALES
```
STT (5s audio):     4.6s
LLM (warm):         3.5s
LLM (cold start):  11.2s
Total (warm):       ~8s
Total (cold):      ~15.7s
```

## COMANDOS DE USO FRECUENTE
```zsh
# Activar entorno
source ~/home-agents-env/bin/activate

# Iniciar sistema completo (recomendado)
systemctl --user start capitan-core   # 1. core primero
systemctl --user start capitan        # 2. ear después
curl http://localhost:8765/health     # verificar

# Dashboard interactivo (alternativa a systemd)
cd ~/workspace/home-agents/core && uvicorn server:app --host 127.0.0.1 --port 8765
bash ~/workspace/home-agents/ear/dashboard.sh

# Logs
journalctl --user -u capitan-core -f
journalctl --user -u capitan -f

# Test directo del core (sin ear)
curl -X POST http://localhost:8765/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"prende la luz"}'

# Test TTS
python ~/workspace/home-agents/ear/tts.py

# Test parser LLM + HA (sin servidor)
python ~/workspace/home-agents/core/agent.py

# Debug wake word scores en tiempo real
python ~/workspace/home-agents/ear/wakeword/debug_scores.py

# Generar samples de wake word
python ~/workspace/home-agents/ear/wakeword/generate_samples_multi.py

# Sync issues con GitHub
python ~/workspace/home-agents/scripts/sync_issues.py

# Actualizar submodules
git -C ~/workspace/home-agents submodule update --remote
```

---

## CÓMO RETOMAR ESTE PLAN

Al inicio de cada sesión escribir:
> "retomamos el master plan"

El asistente responderá con:
- Fase y paso actual
- Qué se completó en la sesión anterior  
- Próximo paso concreto
- Decisiones pendientes si las hay

---

### FASE 18 - Mejoras de UX de Audio

```
Objetivo: Mejorar la experiencia de interacción por voz: feedback sonoro y visual al
          detectar la wake word, distinguiendo cada estado del pipeline. Aplica a los
          nodos NSPanel (FASE 16). Duck de volumen para la laptop/legacy.
Estado:   COMPLETA (18.1 beep + 18.3 indicador visual + 18.2 duck de volumen reformulado para el nodo)
Deps:     FASE 1 (pipeline base, COMPLETA), FASE 16 (nodos de audio).
```

- [x] 18.1  **Sonido de confirmación en wake word** — beep/chime de éxito (campana
            ascendente C5→G5 con armónicos, ~420ms) en `ear/assets/wakeword_ack.wav`.
            En `satellite.py` se reproduce tras detectar la wake word, antes de grabar.
            En Android se para el input stream durante el playback (OpenSLES no permite
            input+output simultáneos) y se reanuda para grabar el comando.

- [x] 18.2  **Duck de volumen durante grabación** — al detectar wake word, bajar el
            volumen del sistema al mínimo posible (o mutear) antes de grabar el comando,
            y restaurarlo al nivel previo al terminar. Usar `pactl set-sink-volume` para
            control de PulseAudio/PipeWire. Debe detectar el nivel actual, bajar, grabar,
            y restaurar incluso si la grabación falla o el pipeline lanza excepción
            (try/finally). Implementar en `ear/listen.py` (laptop/legacy).

- [x] 18.3  **Indicador visual de estado en el nodo** — `ear/satellite_ui.py`: barra fina
- [x] 18.15  Saludo Hola <nombre> intrusivo en cada conversacion nueva (no era bug: el nombre en la DB era literal "Nombre"; el saludo era correcto. Refinamiento UX del saludo → épico 18.16 frente C)
- [x] 18.16  Epico: continuidad conversacional — REPLANTEADO y expandido como FASE 36
            (continuidad conversacional unificada: modelo de conversación channel-aware +
            ContinuationState + proactivos como turnos + saludo por sesión + contexto a agentes)
            overlay (Termux:GUI) full-width en el borde superior, sobre HA Companion, que
            cambia color/animación por estado: listening=shimmer azul lento, wake=verde,
            recording=ámbar, waiting=respiro cian rápido, speaking=azul. Da feedback de
            "qué está pasando" sin estorbar la UI de HA. Degradación elegante si no hay
            Termux:GUI. Nota: los overlays de Termux:GUI no renderizan layouts anidados,
            por eso es una barra única animada por color (no segmentos espaciales).

#### Nota de implementación (calidad de audio del NSPanel)

```
El mic del NSPanel Pro capta muy bajo (RMS voz ~1000-1200, ruido ~25) con el preset
genérico de PortAudio (sin AGC). Mitigaciones implementadas en audio_server.py:
  - Normalización RMS (target 3500, gain hasta 30x) ANTES del STT
  - vad_filter de Whisper SOBRE el audio normalizado (aísla voz, descarta ruido)
  - condition_on_previous_text=False, no_speech_threshold=0.6 (anti-alucinación)
Y en satellite.py:
  - Gate de energía antes del wake word (silencio no scorea → sin falsos positivos)
  - Descarte de comandos casi-silenciosos antes de enviar
Pendiente/futuro: AGC nativo de Android (termux-microphone-record / preset
VOICE_RECOGNITION de OpenSLES) o nodo RPi 5 + ReSpeaker (FASE 16 Etapa D) para
calidad de captura superior.
```

---

### FASE 19 - Mejoras de Canal WhatsApp

```
Objetivo: Conversaciones más naturales y ricas por WhatsApp — respuesta inline a intents
          con diálogo pendiente, auto-cierre de notificaciones, y mensajes con media/links.
Estado:   COMPLETA
Deps:     FASE 3.5 (integración WA, COMPLETA), FASE 9 (coordinador, COMPLETA).
```

- [x] 19.1  **Reply-as-response para intents con diálogo** — cuando el core genera una
            respuesta que requiere input del usuario (confirmación, dato faltante, pregunta),
            guardar el `message.id` de WA del mensaje enviado en el contexto de la conversación
            (`conversation.pending_wa_msg_id`). En `wa/index.js`, al recibir un mensaje con
            `msg.hasQuotedMsg`, resolver el ID del mensaje citado y compararlo con el
            `pending_wa_msg_id` de las conversaciones activas; si coincide, enrutar ese
            mensaje como continuación del intent pendiente (no como nuevo intent).
            El core debe exponer el flag `needs_reply: true` en la respuesta `/process`
            cuando el agente espera input adicional.

- [x] 19.2  **Auto-confirmar notificaciones de solo-aviso** — cuando el core responde con
            `needs_reply: false` (aviso sin acción requerida del usuario), el adaptador WA
            envía automáticamente una reacción ✅ o un reply breve "ok" al mensaje original,
            marcando visualmente que el intent fue procesado. Implementar en `wa/index.js`
            usando `msg.react("✅")` como primera opción (más limpio); fallback a reply "ok"
            si la reacción falla. El flag `needs_reply` también aplica a intents de tipo
            alerta/proactivo enviados desde el core al usuario.

- [x] 19.3  **Mensajes ricos en WhatsApp** — para respuestas que lo ameriten, incluir media:
- [x] 19.4  Respuestas de WhatsApp se enrutan al agente equivocado (cruce de intents) — reply con intent_id (quoted-reply) se rutea con get_request_by_id al agente dueño; nunca cae a get_pending_request (que agarraba el primer pendiente de cualquier agente). PR core #204
            - Link preview automático: si el texto contiene una URL, enviar via `client.sendMessage`
              con `linkPreview: true` (whatsapp-web.js lo genera solo).
            - Imagen adjunta: si el agente devuelve un `media_url` o `image_path` en la respuesta,
              cargar con `MessageMedia.fromUrl()` o `MessageMedia.fromFilePath()` y enviar
              antes o junto al texto.
            - Formato markdown WA: negrita `*texto*`, monoespaciado ` ```código``` `, listas `- item`.
              El core formatea la respuesta según canal (`source.channel == "whatsapp"`) usando
              helpers en `wa_formatter.py` (nuevo). Los canales voz/web no se ven afectados.
            - Casos concretos: clima → imagen del ícono meteorológico del día; inversiones →
              tabla de cotizaciones en monoespaciado; agenda → lista formateada de eventos.

Estado:   COMPLETA

---

### FASE 20 - Agente MercadoLibre

```
Objetivo: Búsqueda, benchmark, recomendación y seguimiento de precios en ML
          via API pública + OAuth 2.0 para operaciones autenticadas.
          Flujo conversacional multi-turno hasta encontrar el producto buscado.
Estado:   COMPLETA
Deps:     FASE 9 (coordinador, COMPLETA), FASE 6 (patrón agente+alertas, COMPLETA),
          FASE 19 (mensajes ricos WA, deseable para output).
Site:     MLU (Uruguay) por defecto; configurable via ML_SITE en .env (MLA, MLB, etc.)
```

#### Etapa A — Cliente público y búsqueda básica

- [x] 20.1  **Cliente ML público** (`ml_client.py`) — wrapper sobre la API pública de ML sin auth:
            `search(query, site, filters)` → lista de items paginada;
            `get_item(item_id)` → detalle completo (precio, condición, stock, vendedor, envío, fotos);
            `get_description(item_id)` → texto completo del producto;
            `get_seller(user_id)` → reputación, nivel de ventas, ubicación.
            Cache por defecto 10min (configurable); respeta rate limits ML (burst 10 req/s).
            Site configurable vía parámetro o `ML_SITE` en `.env`; default `MLU`.

- [x] 20.2  **Parsing de intents de búsqueda** — el LLM extrae de la consulta:
            `query` (término libre), `price_max`, `price_min`, `condition` (new/used/all),
            `category_hint` (texto libre → resolver a category_id vía `/sites/{site}/categories`),
            `free_shipping` (bool). Prompt específico de extracción (micro-LLM, similar a
            `_extract_destination()` en travel_agent.py). Sin categoría explícita, buscar en todo ML.

- [x] 20.3  **Benchmark de resultados** — dado el resultado de `search()`, generar tabla comparativa:
            precio, vendedor (nick + nivel), reputación (verde/amarillo/naranja/rojo), envío gratis,
            cantidad vendida, ubicación, link corto (permalink). Ordenar por score ponderado
            (precio normalizado 40%, reputación vendedor 30%, ventas 20%, envío 10%).
            Formato texto adaptado al canal: tabla monoespaciada para WA/chat, lista para voz.

- [x] 20.4  **Recomendación justificada** — el agente elige el mejor ítem del benchmark y
            genera una recomendación en lenguaje natural explicando por qué (precio justo,
            vendedor confiable, envío incluido, etc.). Si ningún ítem supera un umbral de
            calidad mínima (reputación < verde o precio outlier), lo indica y sugiere refinar
            la búsqueda. Respuesta voz: 2-3 oraciones. Respuesta WA/chat: párrafo + link.

#### Etapa B — Flujo conversacional multi-turno

- [x] 20.5  **Contexto de búsqueda por conversación** — `MLSearchContext` en `shared_state`
            por `source_key`: guarda la última query, filtros activos, página actual, y lista
            de items mostrados (referenciados por índice 1..N para follow-ups).
            Permite: "mostrá más" → página siguiente; "el segundo" → detalle del ítem 2;
            "filtrá por nuevo" → rerun con `condition=new`; "más barato" → rerun con
            `price_max` ajustado al mínimo encontrado; "seguí buscando" → nueva query derivada.

- [x] 20.6  **Refinamiento iterativo** — el agente detecta intents de refinamiento:
            `show_more`, `filter_update`, `item_detail`, `restart_search`.
            Para `item_detail`: llama `get_item()` + `get_description()` y resume en 3-4 puntos
            clave (qué incluye, garantía, ubicación vendedor, tiempo de entrega estimado).
            Para `filter_update`: reutiliza el contexto, aplica el filtro nuevo, resetea página.

#### Etapa C — Seguimiento de precios

- [x] 20.7  **Tracker de precios** (`ml_price_tracker.py`) — persistencia en
            `~/.local/share/capitan/ml_prices.json`. Estructura por usuario:
            `{user_id: [{item_id, title, target_price, snapshots: [{ts, price}], alert_sent}]}`.
            Comandos: "seguí el precio de este" (ítem del contexto actual), "dejá de seguir X",
            "¿cómo está el precio de lo que seguís?". El `item_id` se resuelve desde el contexto
            de búsqueda activo o por título si el usuario lo describe.

- [x] 20.8  **Alertas de precio** — el tracker tiene método `check()` registrado en el sistema
            de alertas existente (`alert_queue.py`): si precio actual < (precio_snapshot_anterior × (1 - ML_PRICE_DROP_PCT))
            → emite alerta "{title} bajó X% — ahora ${precio}". Umbral default 5% vía
            `ML_PRICE_DROP_PCT` en `.env`. Cooldown 24h por ítem para no repetir alertas.
            Chequeo cada hora junto al poller de alertas del core.

- [x] 20.9  **Seguimiento de búsqueda guardada** — además de items individuales, permitir
            guardar una query completa (ej: "notebook RTX 4060 hasta $3000"). Cada chequeo
            corre la búsqueda, compara contra el mejor precio previo registrado, y alerta si
            aparece un ítem nuevo más barato que el mínimo histórico. Útil para productos
            sin item_id estable (stock cambiante, varios vendedores).

#### Etapa D — OAuth y operaciones autenticadas

- [x] 20.10 **Registro de app ML** — proceso de setup único documentado:
            1. Crear app en https://developers.mercadolibre.com.ar → obtener `client_id` y `client_secret`.
            2. Configurar redirect URI: `http://localhost:8766/ml/callback` (puerto separado del core).
            3. Agregar `ML_CLIENT_ID`, `ML_CLIENT_SECRET` a `core/.env`.
            Scope requerido: `read` (para búsqueda autenticada y wishlist), `offline_access` (refresh).
            Sin estas vars, el agente opera en modo público sin OAuth (degradación limpia).

- [x] 20.11 **OAuth 2.0 Authorization Code flow** (`ml_auth.py`) — al solicitar auth:
            1. Generar URL de autorización ML y enviar al usuario por WA/voz/chat.
            2. Levantar servidor temporal `http://localhost:8766/ml/callback` con `http.server`
               (solo durante la ventana de auth, máx 5min).
            3. Capturar `code` del redirect, intercambiar por `access_token` + `refresh_token`
               via POST a `https://api.mercadolibre.com/oauth/token`.
            4. Persistir tokens en `~/.local/share/capitan/ml_token_{user_id}.json` (gitignored).
            Auto-refresh: si `access_token` vence (6h), usar `refresh_token` (180 días) transparentemente.

- [x] 20.12 **Operaciones autenticadas** — con token válido:
            `get_my_orders()` — historial de compras del usuario (útil para "¿ya compré esto antes?");
            `get_wishlist()` — items guardados del usuario en ML;
            `add_to_wishlist(item_id)` — guardar ítem desde el flujo conversacional.
            Si el usuario no autenticó, operaciones degradan a modo público con aviso.

- [x] 20.13 **oauth-app Cloud Run** — migración del servidor OAuth temporal (local :8766) a
            servicio permanente en `capitan.blasi.ar` (repo `home-agents-oauth`). App FastAPI que
            gestiona flujos ML y MP: recibe callback, intercambia code por tokens, guarda
            temporalmente con `short_code` (TTL 5 min), notifica al bot via WA Cloud API.
            Estado: elimina el servidor temporal en core; oauth-app es el punto de entrada público.

- [x] 20.14 **Backoffice: fallback de token por short_code** — cuando WA falla (ej: token 401),
            el token queda disponible en el oauth app por `GET /tokens/{short_code}`.
            Nuevo endpoint `POST /auth/{service}/fetch-shortcode` en `backoffice/server.py`:
            llama al oauth app y persiste el token en `~/.local/share/capitan/{svc}_token_{uid}.json`.
            UI en `agent_edit.html`: botón "Recuperar por short_code" (indigo) en la sección OAuth2
            de cada usuario del agente; los dos formularios (short_code y manual) se muestran
            exclusivos entre sí. El short_code aparece en los logs del oauth app y en la página de
            confirmación de ML.

Estado:   COMPLETA

---

### FASE 21 - Consolidación en Brain (Paso Intermedio)
```
Objetivo: Mover toda la infraestructura de producción a la Beelink SER9 Pro.
          La laptop queda como entorno de desarrollo puro (sin servicios corriendo).
          Misma restricción de modelo 7B que la configuración actual.
          HAOS migra desde el PC viejo dedicado al Brain.
Estado:   COMPLETA (23/23 — consolidación en Brain realizada: audio_server en LXC, NSPanels como I/O de audio, laptop dev-only; decisión 21.21 implementada vía FASE 16)
Hardware: Beelink SER9 Pro — AMD Ryzen AI 7 HX 255, 32GB DDR5, Radeon 780M (RDNA 3)
Stack:    Proxmox VE → VM HAOS + LXC Ubuntu privilegiado (core + backoffice + wa + Ollama)
Nota:     Stepping stone a FASE 8 (servidor con GPU discreta). No escala modelos: sigue en 7B.
```

#### Arquitectura objetivo

```
Brain (Proxmox VE)
├── VM: HAOS                     — imagen oficial, bridge LAN → IP real (192.168.68.101)
└── LXC Ubuntu privilegiado      — todos los servicios home-agents
    ├── core                     — FastAPI :8765
    ├── backoffice               — FastAPI :8080
    ├── wa                       — Node.js (whatsapp-web.js)
    ├── ear                      — ⚠ PENDIENTE (ver 21.21)
    └── ollama                   — CPU + ROCm 780M vía /dev/kfd + /dev/dri passthrough

Laptop → desarrollo puro (git, editor, deploy vía SSH)
```

LXC privilegiado (no VM) para que el passthrough de /dev/kfd + /dev/dri/renderD128 (ROCm)
y /dev/snd (audio ALSA, si corre el ear) sea directo y sin complejidad de IOMMU de APU.

#### Etapa A — Proxmox y red

- [x] 21.1  Instalar Proxmox VE en el Brain (ISO oficial, bare metal).
            IP estática en la interfaz física del host PVE.
            Hostname: `capitan`, accesible como `capitan.local` (mDNS) o por IP fija.
- [x] 21.2  Crear bridge `vmbr0` sobre la interfaz física.
            El bridge da a las VMs y LXCs IP real en la LAN (sin NAT).
            Reservar IP del HAOS VM en el router (DHCP reservation por MAC → 192.168.68.101).
- [x] 21.3  SSH desde laptop configurado: clave pública copiada al host PVE y al LXC.
            Alias en `~/.ssh/config`: `Host capitan` → IP fija del LXC.

#### Etapa B — VM de HAOS

- [x] 21.4  Backup completo del HAOS actual: Settings → System → Backups → Download .tar.
- [x] 21.5  Crear VM en Proxmox con imagen oficial HAOS:
            Descargar `haos_ova-*.qcow2` (o usar Proxmox Helper Scripts — tteck).
            VM con red en `vmbr0` → IP real en LAN → reservar 192.168.68.101 por MAC.
- [x] 21.6  Restaurar el backup en el nuevo HAOS.
            Verificar: integraciones activas, entity_ids idénticos, Long-Lived Token funcionando.
            Smoke test: `curl http://192.168.68.101:8123/api/` con el token del .env.
- [x] 21.7  Autostart de la VM: Options → Start at boot → Yes.
- [x] 21.8  Apagar el PC viejo (solo tras confirmar 21.6 completo y token funcionando).

#### Etapa C — LXC Ubuntu privilegiado

- [x] 21.9  Crear LXC privilegiado (Ubuntu 24.04) en Proxmox:
            RAM: 12GB, cores: 6, storage: 40GB mínimo.
            Red en `vmbr0` → IP fija (ej: 192.168.68.102).
            `features: nesting=1` (necesario para systemd --user).
            Autostart: Yes.
- [x] 21.10 Pasar dispositivos GPU al LXC (en `/etc/pve/lxc/<id>.conf` en el host PVE):
            ```
            lxc.cgroup2.devices.allow: c 226:* rwm
            lxc.cgroup2.devices.allow: c 234:0 rwm
            lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir
            lxc.mount.entry: /dev/kfd dev/kfd none bind,optional,create=file
            ```
            (Solo relevante si se confirma ROCm — ver 21.13/21.14.)
- [x] 21.11 Instalar en el LXC: Python 3.13, Node 18, git, ffmpeg (incluye ffplay), build-essential.
            Instalar Piper: descargar binario v1.2.0 + voces en `~/.local/share/piper/`.
            Crear `~/home-agents-env` (venv).

#### Etapa D — Ollama en el LXC

- [x] 21.12 Instalar Ollama en el LXC (`curl -fsSL https://ollama.ai/install.sh | sh`).
            Pull `qwen2.5:7b`. Systemd unit generada automáticamente.
- [x] 21.13 Benchmark CPU-only como baseline:
            `time ollama run qwen2.5:7b "responde solo: hola"` → latencia warm.
- [x] 21.14 Intentar ROCm 780M en el LXC:
            Instalar ROCm 6.x dentro del LXC. Verificar visibilidad de `/dev/kfd` y `/dev/dri/renderD128`.
            Si el chip es gfx1151 (Strix Point): puede necesitar `HSA_OVERRIDE_GFX_VERSION=11.0.0`.
            Re-benchmarkar. Si latencia warm < 2s y estable → mantener ROCm. Si no → CPU-only.
- [x] 21.15 Documentar resultado del benchmark y decisión ROCm en NOTAS.
            Resultado: CPU-only 27.5s | ROCm gfx1103 (780M) 13.3s — 2x mejora.
            Decisión: mantener ROCm con HSA_OVERRIDE_GFX_VERSION=11.0.0 en ollama.service.d/rocm.conf.
            /dev/kfd major 511 (no 234). chmod 666 /dev/kfd necesario al boot.

#### Etapa E — Migración de home-agents al LXC

- [x] 21.16 Clonar `home-agents` con submodules en el LXC:
            `git clone --recurse-submodules git@github.com:mblasi/home-agents.git ~/workspace/home-agents`
            Instalar deps Python: `pip install -r core/requirements.txt`
            Instalar deps Node: `npm install` en `ear/wa/` (o donde esté el cliente WA).
- [x] 21.17 Crear `core/.env` en el LXC:
            `OLLAMA_URL=http://localhost:11434`
            `HAOS_URL=http://192.168.68.101:8123`
            Resto de vars: copiar desde la laptop (HAOS_TOKEN, BACKOFFICE_TOKEN, etc.).
- [x] 21.18 Instalar y habilitar systemd user units: `capitan-core.service`, `capitan-backoffice.service`.
            `loginctl enable-linger <user>` para que las units arranquen sin sesión activa.
            Smoke test: `curl http://localhost:8765/health` desde el LXC.
- [x] 21.19 Levantar el cliente WA (`node ear/wa/index.js` o como esté estructurado),
            escanear QR, verificar reconexión automática y respuesta a mensajes.
- [x] 21.20 Test end-to-end desde la laptop:
            `curl -X POST http://capitan.local:8765/process -H 'Content-Type: application/json' -d '{"text":"prende la luz"}'`
            Backoffice accesible en `http://capitan.local:8080`.

#### Etapa F — Ear (decisión tomada)

- [x] 21.21 **Decisión**: el ear corre en el LXC del Brain como servidor de audio — SIN hardware
            de audio local (no mic, no speaker, no /dev/snd). Es un proceso servidor que:
            - Recibe audio (WAV/chunks) desde los NSPanel Pro vía WebSocket o HTTP
            - Corre STT (faster-whisper) sobre ese audio
            - Llama al core (/process) y obtiene respuesta
            - Sintetiza TTS (Piper) y devuelve el WAV al NSPanel que lo emite
            Los NSPanel Pro son los únicos puntos de captura y reproducción de audio.
            La laptop queda 100% desarrollo sin ningún servicio corriendo.
            Implementación: ver FASE 16 (Red de Nodos de Audio Multi-Ambiente).
            Esta tarea se completa al terminar FASE 16 Etapa A (16.1-16.4).

#### Etapa G — Workflow de deployment desde laptop

- [x] 21.22 Crear `scripts/deploy.sh` en el repo umbrella:
            ```bash
            #!/usr/bin/env zsh
            # Deploy home-agents al LXC de producción en el Brain.
            set -e
            ssh capitan "
              cd ~/workspace/home-agents &&
              git pull --recurse-submodules &&
              source ~/home-agents-env/bin/activate &&
              pip install -q -r core/requirements.txt &&
              systemctl --user restart capitan-core capitan-backoffice
            "
            echo "Deploy completo."
            ```
            Uso: `bash scripts/deploy.sh` desde la laptop tras mergear un PR a main.
- [x] 21.23 Actualizar `CLAUDE.md` del repo umbrella: reflejar nueva arquitectura, IP/hostname
            del LXC, comandos de deploy y de smoke test remoto.

#### Procedimientos de actualización (referencia operativa)

```zsh
# Ollama — en el LXC via SSH
ssh capitan "sudo systemctl stop ollama && curl -fsSL https://ollama.ai/install.sh | sh && sudo systemctl start ollama"
# Los modelos descargados sobreviven la actualización.

# HAOS — desde la UI del HAOS en la VM (192.168.68.101:8123)
# Settings → System → Updates → Check for updates / Install
# La VM de Proxmox no se toca.

# home-agents (core + backoffice)
bash scripts/deploy.sh   # desde la laptop, tras mergear PR a main

# ear — si está en el LXC del Brain
ssh capitan "cd ~/workspace/home-agents && git pull --recurse-submodules && systemctl --user restart capitan"

# ear — si está en la laptop (opción B de 21.21)
git -C ~/workspace/home-agents pull --recurse-submodules && systemctl --user restart capitan

# OS del LXC
ssh capitan "sudo apt update && sudo apt upgrade -y"

# Proxmox host — desde la UI de PVE o via SSH al host
ssh root@<ip-pve> "apt update && apt dist-upgrade -y"
```

---

## NOTAS Y DECISIONES TOMADAS

### 2026-04-27
- Elegido qwen2.5:7b como LLM principal (phi3:mini descartado por lento)
- phi3-ha descartado (inventa entity_ids)
- Opción 3 elegida para wake word (training propio con openWakeWord)
- Porcupine descartado (dependencia externa, límites de uso)
- faster-whisper elegido sobre openai-whisper (HuggingFace download, más rápido)
- aplay descartado para TTS, usar ffplay
- Arquitectura decidida: todo el procesamiento en laptop, HAOS solo recibe REST calls
- acoustics parcheado para compatibilidad con scipy 1.17.1 / Python 3.13

### 2026-05-13
- Backoffice: página `/traces` unificada con solapas `proactive_check` / `goal_review`, listados flat ordenados por fecha descendente, paginados (25/página).
- Core: endpoint `/proactive/traces/{agent_id}` agrega `intent_type_counts` (conteo de items por tipo: advise/request/goal) para mostrarlo como badges en el listado sin leer el detalle.
- Templates `proactive_trace_list.html`, `proactive_trace_detail.html` y `traces.html` actualizados con badges de tipo.

### Pendiente decidir
- Latencia: ¿optimizar ahora o avanzar con la integración?
- Hardware servidor: timing y presupuesto

---

## ANEXO — ITERACIONES FUTURAS

Mejoras identificadas que no bloquean el plan actual pero vale la pena evaluar
en fases posteriores. Cada ítem tiene issue abierto en GitHub para seguimiento.

### A.1 Evaluar migración a Home Assistant MCP Server

**Contexto**: La integración actual con HAOS usa REST API con `entity_id` estáticos
en el contexto del LLM. El MCP Server de HA (`homeassistant.io/integrations/mcp_server`)
expone herramientas dinámicas (`list_entities`, `get_state`, `call_service`) que
permitirían al agente descubrir entidades en tiempo real y consultar estado antes de actuar.

**Por qué no ahora**: qwen2.5:7b vía Ollama no habla protocolo MCP nativamente.
Requeriría un puente MCP client → tool calls de Ollama, añadiendo complejidad sin
beneficio neto sobre lo que REST ya da.

**Condiciones para reevaluar**:
- Si Ollama incorpora soporte nativo MCP en alguna versión futura
- Si la lista de entidades crece lo suficiente como para que el contexto estático
  se vuelva un problema real
- Si se necesita leer estado antes de actuar (ej: "apagá lo que esté prendido")

**Restricción no negociable**: la solución debe correr 100% en LAN local, sin
tráfico a internet. Cualquier implementación MCP debe usar modelos locales (Ollama
u otro runtime local) como cliente MCP.

---

### ~~A.2 Red de nodos de audio multi-ambiente~~ → FASE 16

**Contexto**: La arquitectura actual tiene un único punto de acceso (la laptop con
micrófono y parlantes). Para hacer el agente realmente útil en toda la casa, se
necesitan nodos de audio en distintos ambientes (cocina, living, dormitorio, etc.)
que actúen como interfaces de voz distribuidas sobre la red WiFi hogareña.

**Hardware elegido: NSPanel Pro (Sonoff)**:
- Android 8.1 AOSP (Rockchip PX30 / RK3308), 64GB almacenamiento
- Micrófono y parlante accesibles desde Python via sounddevice/PortAudio (codec RK809)
- ADB over WiFi habilitado (puerto 5555), root disponible
- Termux instalado para scripts Python de voz; Termux:Boot para autoarranque
- HA Companion App como dashboard táctil (usuario HA por panel → dashboard por ambiente)
- Función dual: dashboard HA táctil + nodo de voz para home-agents
- Setup: ADB connect → instalar Termux → SSH → instalar Python + sounddevice + portaudio

**Arquitectura propuesta**:
- Nodos ligeros (NSPanel Pro o Raspberry Pi Zero 2W) con micrófono + parlante
- Cada nodo corre wake word detection localmente (openWakeWord, modelo capitan.onnx)
- Al detectar wake word, el nodo captura el audio del comando y lo envía via WebSocket
  o MQTT al servidor central (la laptop)
- El servidor central procesa STT → LLM → HAOS y devuelve el texto de respuesta al nodo
- El nodo sintetiza la respuesta con Piper TTS y la reproduce localmente
- Cada nodo se identifica con un nombre de ambiente (ej: `cocina`, `dormitorio`)
  para logs y ruteo de respuesta correcto

**Alternativa con hardware existente**:
- Los Echo (echo_de_matias, echo_dot, echo_pop_de_gala, echo_show) ya están en la casa
  y podrían usarse como parlantes de respuesta via HA `media_player.play_media`
- La captura de audio requeriría nodos propios de todas formas (los Echo son cerrados)

**Por qué no ahora**: requiere hardware adicional, diseño del protocolo de red
nodo↔servidor, y gestión de múltiples streams de audio simultáneos. La Fase 1 del
agente debe estar estable primero.

**Condiciones para reevaluar**:
- Cuando el agente single-node sea estable en uso diario
- Cuando haya presupuesto/tiempo para hardware de nodos
- Si el uso diario muestra que la cobertura de un solo ambiente es limitante

**Restricción no negociable**: todo el procesamiento pesado (STT, LLM, TTS) corre
en la laptop central. Los nodos son clientes ligeros — solo corren wake word detection
y streaming de audio. Nada sale de la LAN local.


### FASE 22 - Modelo de Intents Tipado (Intent Model 2.0)

```
Objetivo: Modelar correctamente los tres tipos de intents: advise (notificación TTL),
          request (el agente pide info al usuario; el siguiente mensaje ES la respuesta),
          goal (intención real cross-agente con árbol de sub-goals, ciclo de vida complejo
          y goal reviewer proactivo que busca cumplirlos con colaboración multi-agente).
Estado:   COMPLETA
Deps:     FASE 9 (intent_state básico), FASE 3.5 (WA para captura de request),
          FASE 12 (backoffice para vista de goals).
```

- [x] 22.1  **`core/intent_model.py`** — TypedDicts `AdviseIntent`, `RequestIntent`, `GoalIntent`,
            `GoalNote`. `VALID_TRANSITIONS` por tipo. `validate_transition()`, `is_active()`,
            `is_terminal()`. Sin dependencias — módulo puro de schema.

- [x] 22.2  **Refactorizar `core/intent_state.py`** — soporte de `intent_type` en `upsert()`,
            nuevos status (`active`, `acknowledged`, `succeeded`, `expired`). `acknowledge()`,
            `capture_reply()`, `get_pending_request()`. `_coerce_legacy()` para migración
            transparente sin script. Advise no genera recordatorios. Compat backward total.

- [x] 22.3  **`core/goal_store.py`** — storage separado en
            `~/.local/share/capitan/goals/{user_id}.json`. CRUD completo, árbol parent/child
            con cascade de completitud automático, `get_goals_for_agent()`, `get_goals_needing_review()`.

- [x] 22.4  **`_build_agent_prefix()` tipado** — advise `[AVISO]`, request `[PENDIENTE TU RESPUESTA]`,
            goals via `goal_store.get_goals_for_agent()` en sección separada. Filtra estados terminales.

- [x] 22.5  **Pipeline de captura de Request** en `process()` y `wa_inbound()` — el siguiente
            mensaje del usuario se captura sin pasar por el coordinador LLM. Hook opcional
            `handle_captured_reply()` en el agente origen.

- [x] 22.6  **`_apply_agent_updates()` tipado** — routea por `intent_type`. Soporte de `goal_updates`
            para transiciones explícitas de goals desde agentes.

- [x] 22.7  **`core/proactive.py` tipado** — `_persist_proactive_item()` routea por tipo.
            `_should_skip()` chequea `goal_store` para items tipo goal. WA notifications
            diferenciadas por tipo (question para request, detección de objetivo para goal).

- [x] 22.8  **Endpoints REST — Request capture** — `POST /users/{id}/intents/{id}/capture`,
            `GET /users/{id}/intents/pending-request`.

- [x] 22.9  **Endpoints REST — Goals** — CRUD completo + transition + notes + children.
            `GET /goals` (admin). Modelos Pydantic: `GoalCreate`, `GoalTransition`, `GoalNoteCreate`.

- [x] 22.10 **`core/base_agent.py` hooks opcionales** — `handle_captured_reply()`, `review_goal()`,
            `on_goal_transition()`. Duck-typed, sin herencia requerida.

- [x] 22.11 **Goal Reviewer en `ProactiveScheduler._loop()`** — `_review_goals()` itera goals
            activos vencidos por `review_interval_hours`. `discovered`→`planning` automático,
            `planning`/`in_progress` → llama `review_goal()` en colaboradores, `blocked` →
            reintenta o notifica. Hook opcional `review_goal(user_id, goal) -> {status?, note?}`.

- [x] 22.12 **Backoffice** — `intents.html` con badges de tipo, botón 'visto' para advise, form
            de captura para request, muestra `captured_reply`. `goals.html` nuevo: árbol,
            notas, colaboradores, transiciones. Sidebar con link Goals.

---

### FASE 23 - Routing LLM Genérico + Mejora Continua Bidireccional

```
Objetivo: Eliminar todo el keyword matching de los agentes. Reemplazarlo por routing
          LLM en dos niveles: coordinador elige agente (AgentCard) y cada agente elige
          su acción interna (BackendCard). Ambos niveles aprenden con cada interacción
          y mantienen un score de utilidad.
Estado:   COMPLETA
Deps:     FASE 9 (coordinator + FastClassifier), FASE 20 (ML), FASE 8 (CalendarAgent).
```

- [x] 23.1  **`core/backend_router.py`** — módulo nuevo. `BackendCard` dataclass con
            `action_id`, `label`, `description`, `requires_auth`, `auth_service`, `examples`.
            `to_catalog_text(extra_examples=None)` para enriquecer el catálogo con
            ejemplos aprendidos. `select_action(text, actions, model, auth_status,
            conv_context, agent_id)` — llama al LLM del agente con las BackendCards
            disponibles; filtra por `auth_status`; si solo hay una acción, retorna sin LLM;
            cuando se pasa `agent_id`, carga los ejemplos aprendidos de `agents.json` y los
            incluye en el catálogo.

- [x] 23.2  **`core/ml_agent.py` reescrito** — elimina todo keyword matching. Define
            `_ACTIONS: list[BackendCard]` con 5 acciones: `search_public`, `search_refine`
            (gated por contexto activo), `orders` (auth ml), `wishlist` (auth ml),
            `price_track` (gated). `process()` llama `select_action()` con `agent_id`.
            Fix incluido: `get_my_orders()` requiere `buyer={user_id}` en la API.

- [x] 23.3  **`core/mp_agent.py` reescrito** — elimina todo keyword matching. Define
            `_ACTIONS: list[BackendCard]` con 6 acciones: `balance`, `movements`,
            `pending_payments`, `summary`, `payment_link`, `request_money`.
            `process()` llama `select_action()` con `agent_id`.
            Flujo de confirmación (sí/no) se mantiene como máquina de estados antes del routing
            — es estado binario, no routing semántico.

- [x] 23.4  **`core/calendar_agent.py` — routing BackendCard** — define `_ACTIONS` con
            2 BackendCards: `holidays` (lookahead 365 días) y `calendar` (lookahead normal).
            `process()` llama `select_action()` con `agent_id` para determinar el lookahead
            en lugar del keyword matching anterior.

- [x] 23.5  **Mejora continua Nivel 1 — AgentCard** — `agent_config.append_learned_example()`
            + `agent_config.record_agent_outcome()`. `get_registry()` combina curados +
            `learned_examples` (deduplicados). FastClassifier se entrena con ejemplos combinados.
            `server.py` llama `record_agent_outcome()` con `success=not _is_error_result(resp)`
            después de cada request.

- [x] 23.6  **Mejora continua Nivel 2 — BackendCard** — `agent_config.record_action_outcome()`
            persiste en `action_examples.{action_id}`. `backend_router._load_action_examples()`
            los inyecta en el catálogo cuando se pasa `agent_id`. Cada agente llama
            `record_action_outcome()` con `success=desc is not None` después del dispatch.

- [x] 23.7  **Scoring de utilidad** — `agent_config.record_agent_outcome()` y
            `record_action_outcome()` actualizan contadores `{calls, successes}` en
            `agent_stats` y `action_stats[action_id]` respectivamente.
            `get_agent_stats(agent_id) → {calls, successes, score}` y
            `get_action_stats(agent_id) → {action_id: {calls, successes, score}}`.
            `score = successes/calls` con mínimo de 5 llamadas (None si < 5).
            Storage en `~/.local/share/capitan/agents.json`.

- [x] 23.8  **`backend_router.py` API unificada** — `record_agent_outcome(agent_id, text, success)`
            delega a `agent_config.record_agent_outcome()`. `record_action_outcome(agent_id,
            action_id, text, success)` delega a `agent_config.record_action_outcome()`.
            Las funciones anteriores `record_success` y `record_action_success` eliminadas.

---

### FASE 24 - Tracing Detallado de Interacciones

```
Objetivo: Guardar un trace completo de cada request — interacciones del coordinador con
          el LLM, catálogo de agentes analizado, agente seleccionado, acción del backend
          router, llamadas LLM del agente — y navegarlo en el backoffice para identificar
          oportunidades de mejora (ej: routing incorrecto, no-resultados evitables).
Estado:   COMPLETA
Deps:     FASE 9 (coordinator), FASE 23 (backend_router).
```

- [x] 24.1  **`core/trace_store.py`** — módulo nuevo. Dataclasses: `LLMCall` (source, model,
            system, prompt, raw_response, latency_ms, ts), `BackendRouterTrace` (catalog_text,
            action_selected, reason, llm_call), `AgentStepTrace` (agent_id, query,
            injected_prefix, backend_router, agent_llm_calls, response, success, latency_ms),
            `CoordinatorTrace` (input_text, catalog_text, fast_classifier_used, fast_agent,
            fast_conf, llm_call, plan_json, latency_ms), `RequestTrace` (trace_id, conv_id,
            ts, user_text, coordinator, steps, aggregation_call, final_response, total_latency_ms).
            Thread-local context: `set_current_trace(t)`, `get_current_trace()`, `add_llm_call(call)`.
            Storage: `~/.local/share/capitan/traces/{conv_id}.jsonl` (append-only, un JSON
            por línea). `append_trace(t)`, `get_traces(conv_id)` → lista reversed (más reciente
            primero), `get_trace(conv_id, trace_id)`. Retención: max 100 traces por conv_id.

- [x] 24.2  **Instrumentar `coordinator.py`** — `_call_llm()` retorna `(str, LLMCall|None)`.
            `coordinate()` captura: catalog_text, path tomado (fast_classifier o LLM),
            fast_agent/conf si aplica, y el plan resultante como JSON. `aggregate()` registra
            su llamada LLM como `aggregation_call` en el trace. Sin cambios en lógica ni firmas públicas.

- [x] 24.3  **Instrumentar `backend_router.py`** — `select_action()` captura catalog_text,
            system prompt, prompt enviado, respuesta raw del LLM, action seleccionada y reason.
            Persiste como `BackendRouterTrace` en el `AgentStepTrace` activo del trace actual.
            Si solo hay una acción (no se llama LLM), registra igual con `llm_call=None`.

- [x] 24.4  **Instrumentar `agent.py` (HAOS)** — `_ask_llm()` registra cada llamada LLM del
            agente HAOS en `agent_llm_calls` del step activo. Captura: model, system/prompt
            extraídos del messages[], raw_response, latency_ms.

- [x] 24.5  **Instrumentar `server.py`** — en `/process`: crea `RequestTrace`, lo activa como
            contexto thread-local, `_run_plan()` hace `push_step()` antes y `finish()` después
            de cada agente. Guarda trace en background al finalizar. `ProcessResponse` incluye
            `trace_id`.

- [x] 24.6  **REST endpoints en `core/server.py`** — `GET /conversations/{id}/traces` →
            lista de traces (summary: trace_id, ts, user_text, agents, latency, success).
            `GET /conversations/{id}/traces/{trace_id}` → trace completo como JSON.

- [x] 24.7  **Backoffice** — `trace_list.html`: lista de traces por conversación con badges.
            `trace_detail.html`: árbol visual expandible — Coordinador (fast-clf vs LLM, catálogo,
            plan), Steps (query, BackendRouter con catálogo + LLM call, llamadas LLM del agente,
            respuesta con highlight de errores), Agregación multi-step. Link "Traces" en
            `conversations.html`. Rutas `/conversations/{id}/traces` y `/{id}/traces/{trace_id}`.

### FASE 25 - Agente Google Maps

```
Objetivo: Agente de navegación y búsqueda de lugares usando Google Maps Platform.
          El usuario configura su propia API key; el agente resuelve rutas,
          búsquedas de lugares cercanos y detalles de establecimientos.
Estado:   COMPLETA
Deps:     FASE 9 (coordinador), FASE 3 (multi-agente), FASE 12 (backoffice para config de key).
API key:  GOOGLE_MAPS_API_KEY en core/.env — habilitadas: Geocoding, Places, Directions APIs.
```

- [x] 25.1  **`core/maps_client.py`** — wrapper HTTP sobre Google Maps Platform. Métodos:
            `geocode(address)` → (lat, lng); `reverse_geocode(lat, lng)` → dirección;
            `get_directions(origin, destination, mode)` → pasos, distancia_total, duracion_total;
            `search_nearby(location, place_type, radius_m)` → lista de places con name, rating,
            open_now, distance; `search_text(query, location)` → idem;
            `get_place_detail(place_id)` → name, address, phone, website, opening_hours, rating.
            API key desde `GOOGLE_MAPS_API_KEY` en `core/.env`.
            Lanza `MapsKeyMissing` si no está configurada, `MapsAPIError` para errores de la API.
            Cache de 10 min para geocoding y place details; sin cache para directions (tráfico en tiempo real).

- [x] 25.2  **Onboarding de API key** — si `GOOGLE_MAPS_API_KEY` falta o es inválida, el agente
            responde con instrucciones: URL de Google Cloud Console, APIs a habilitar (Geocoding,
            Places, Directions), cómo agregar la key al `core/.env`.
            En el backoffice: campo en `/settings` para ingresar `GOOGLE_MAPS_API_KEY`; botón
            "Verificar" hace una geocoding de prueba y muestra estado (válida / inválida / sin cuota).
            También configurable: `HOME_LOCATION` (dirección o lat,lng) usada como origen default.

- [x] 25.3  **`core/maps_agent.py`** — agente principal registrado en `agent_registry.py`.
            LLM extrae de la consulta: `intent` (directions / nearby_search / place_detail / geocode),
            `origin` (texto o "casa"), `destination`, `place_type` (restaurant, pharmacy, hospital…),
            `transport_mode` (driving/walking/transit; default driving), `location_ref` (texto libre).
            Si origin es "casa" o no se especifica, usa `HOME_LOCATION` del env.
            Descripción en el catálogo: keywords mapa, ruta, cómo llego, cómo voy, dónde queda,
            cerca, restaurante, farmacia, horario, abierto, google maps, direcciones.

- [x] 25.4  **Intent `directions`** — llama `get_directions()`. Respuesta para voz: distancia y
            tiempo total + 2-3 pasos clave en lenguaje natural ("Tomá Av. Italia y en 3km girá a
            la derecha en..."). Respuesta para WA/chat: tabla con todos los pasos, distancias
            parciales y duración parcial + deeplink `https://maps.google.com/maps?saddr=...&daddr=...`.
            Si `transport_mode=transit`, incluir líneas de transporte si la API las devuelve.

- [x] 25.5  **Intent `nearby_search` / `search_text`** — llama `search_nearby()` o `search_text()`.
            Lista top-5 con: nombre, rating (★★★☆☆), open_now (abierto/cerrado), distancia.
            Guarda resultados en `shared_state[source_key]["maps_results"]` para multi-turno:
            "el primero" / "más detalles del segundo" → llama `get_place_detail()` del ítem
            referenciado y responde con teléfono, web, horarios completos.

- [x] 25.6  **Intent `place_detail`** — cuando la consulta es directamente por un establecimiento
            ("¿a qué hora cierra el Farmashop de Pocitos?"). LLM extrae el nombre y posible
            zona; hace `search_text()` para resolver el place_id y luego `get_place_detail()`.
            Responde con horario del día actual resaltado, teléfono y estado abierto/cerrado ahora.

- [x] 25.7  **Registro definitivo y tests** — registrar en `agent_registry.py` con `id="maps"`,
            `description` orientada al coordinador LLM. Agregar `GOOGLE_MAPS_API_KEY` y
            `HOME_LOCATION` como vars opcionales al bloque `.env` en el backoffice y en `CLAUDE.md`.
            Tests manuales: ruta casa→trabajo, "farmacia cerca", "horario del McDonalds de 18 de julio".

---

### FASE 26 - Sistema de Rutinas

Estado: COMPLETA
Deps:   FASE 9 (coordinador + agent_history), FASE 22 (goal engine — modelo de referencia).

Las rutinas son patrones de comportamiento inferidos dinámicamente a partir del historial
de interacciones del usuario. A diferencia de los goals (intenciones explícitas), las rutinas
se detectan por observación y se construyen iterativamente.

- [x] 26.1  **`routine_store.py`** — persistencia en `~/.local/share/capitan/routines/{user_id}.json`.
            Máquina de estados: `candidate → active → paused | dismissed`.
            Promoción automática a `active` cuando `confidence ≥ 0.6` y `occurrence_count ≥ 3`.
            Deduplicación por similitud Jaccard antes de crear duplicados.
            API: `create_routine`, `record_occurrence` (EMA 30/70), `transition`, `find_similar`,
            `get_active_routines`, `mark_triggered`, `get_all_active_across_users`.

- [x] 26.2  **`routine_detector.py`** — detección LLM periódica.
            Carga mensajes del usuario de todos los agentes (solo role=user).
            Llama a qwen2.5:7b con prompt estructurado que pide JSON array de rutinas candidatas.
            Si detecta una rutina similar a una existente (Jaccard): incrementa ocurrencias.
            Si es nueva: crea `candidate`. Intervalo mínimo configurable (default 6h por usuario).
            `detect_for_user(user_id)` + `run_all_users()` para el poller de background.

- [x] 26.3  **Integración en `server.py`**:
            - Background thread `routine-detector` que llama `run_all_users()` cada 6h
              (configurable con `ROUTINE_DETECT_INTERVAL`).
            - `_build_agent_prefix()`: rutinas `active` inyectadas en el contexto de cada agente
              como `[RUTINA] Título (confianza: X%): descripción`.
            - `_apply_agent_updates()`: maneja `routine_updates` en el dict de retorno de agentes.
              Con `routine_id` → transiciona rutina existente.
              Sin `routine_id` + `title` → crea rutina candidata nueva.

- [x] 26.4  **Endpoints REST**:
            `GET /routines` — vista admin de rutinas activas de todos los usuarios.
            `GET /users/{uid}/routines[?status=...]` — rutinas de un usuario con filtro opcional.
            `POST /users/{uid}/routines` — crear rutina manualmente.
            `GET /users/{uid}/routines/{rid}` — detalle de una rutina.
            `POST /users/{uid}/routines/{rid}/transition` — transicionar estado.
            `DELETE /users/{uid}/routines/{rid}` — eliminar rutina.
            `POST /users/{uid}/routines/detect` — forzar detección inmediata (bloquea 60s máx).

- [x] 26.5  **`base_agent.py`**: documenta `routine_updates` en el contrato de retorno del protocolo.

---

### FASE 27 - Afinidades entre agentes + proactividad colaborativa

Estado: COMPLETA
Deps:   FASE 26 (SharedState), FASE 9 (proactividad base), FASE 24 (traces).

Los agentes pueden tener relaciones de afinidad configuradas por el usuario. Durante el ciclo
proactivo, cada agente construye automáticamente un contexto cross-dominio leyendo datos de
SharedState publicados por sus agentes afines. Esto habilita sugerencias proactivas que emergen
de la colaboración entre dominios sin hardcodear lógica inter-agente.

- [x] 27.1  **`shared_state.py`** — añade `get_by_prefix(prefix)`: retorna todas las entradas
            no expiradas cuya clave comienza con `prefix.`. Permite filtrar datos por namespace
            de agente (ej: `weather.*`, `calendar.*`) en O(n) sobre las entradas vivas.

- [x] 27.2  **`agent_config.py`** — cuatro funciones nuevas:
            `get/set_affinities(agent_id)` — lista de agent_ids con los que hay afinidad.
            `get/set_shared_state_prefix(agent_id)` — namespace que este agente publica en SharedState.
            Ambos persisten en `~/.local/share/capitan/agents.json`.

- [x] 27.3  **`proactive_mixin.py`** — `_build_affinity_context(agent_id)` lee affinities de
            agent_config, obtiene el shared_state_prefix de cada afín y llama get_by_prefix para
            construir un bloque de texto tipo "- weather (weather.*): temp=22.5, is_raining=False".
            En `proactive_check`: el bloque se inyecta al prompt del LLM entre active_intents y
            el historial. Hook `proactive_system_prompt`: si el agente define este atributo de clase,
            se usa como system prompt; si no, el genérico de ProactiveMixin.

- [x] 27.4  **`clima_agent.py`** — declara `shared_state_prefix = "weather"`. ClimaAgent ya
            publicaba `weather.*` en SharedState; ahora ese namespace queda formalizado para que
            otros agentes puedan declarar afinidad con él.

- [x] 27.5  **`maps_agent.py`** — hereda `ProactiveMixin` (primer agente no-genérico en hacerlo).
            `proactive_schedule = 3600` (horario). `default_affinities = ["weather"]` — por defecto
            tiene afinidad con el agente de clima. `proactive_system_prompt` orienta al LLM hacia
            sugerencias de movilidad emergentes del contexto (clima + rutinas + historial).

- [x] 27.6  **`core/server.py`** — `GET /agents` incluye `affinities` y `shared_state_prefix`
            por agente (con fallback a atributos de clase). Endpoints nuevos:
            `GET/PUT /agents/{id}/affinities` — leer/escribir lista de afines.
            `GET/PATCH /agents/{id}/shared-state-prefix` — leer/escribir namespace.

- [x] 27.7  **Backoffice** — `agent_edit.html` sección "Afinidades entre agentes":
            campo `shared_state_prefix` (qué namespace publica este agente) y multi-select
            de agentes afines con checkboxes, mostrando el namespace de cada uno.
            `backoffice/server.py` proxea los nuevos endpoints al core.

- [x] 27.8  **Tests** — `tests/test_agent_affinities.py`: 13 tests cubren get/set de affinities
            y shared_state_prefix, SharedState.get_by_prefix (incluye expiración y aislamiento
            de prefijos), y _build_affinity_context (sin affinities, con datos, sin prefix, sin datos).

---

### FASE 28 - Gestión de Modos por Canal (UX Multi-Canal)

```
Objetivo: Formalizar las capacidades de input/output de cada canal de interacción
          (wa, mic/ear, web) y hacer que el agente respete esas restricciones al
          elegir el modo de respuesta. Revisar el campo `notification_mode` del usuario
          para que tenga sentido en un contexto multi-canal.
Estado:   COMPLETA (28.1 CHANNEL_CAPS + 28.2 reconciliación con downgrade+log + 28.3 response_type [ya existía] + 28.4 wa_notify_format [opción b])
Deps:     FASE 3.5 (WA), FASE 18 (UX audio), FASE 12 (backoffice).
```

- [x] 28.1  **Mapa de capacidades por canal** — definir en `core/` un diccionario o clase
            `CHANNEL_CAPS` que declare para cada canal (`"wa"`, `"ear"`, `"web"`) qué modos
            de input y output soporta:
            ```
            wa:  input=[text, audio], output=[text, audio]
            ear: input=[audio],       output=[audio]
            web: input=[text],        output=[text]
            ```
            El campo `source` que ya llega en `/process` se usa para lookupear las caps.
            Estas capacidades deben ser consultables desde el agente y desde el coordinador.

- [x] 28.2  **Restricción de modo en el coordinador** — al construir el contexto de respuesta,
            el coordinador (o el dispatch en `agent_registry.py`) debe filtrar el modo elegido
            por el agente contra `CHANNEL_CAPS[source].output`. Si el agente pidió `audio` pero
            el canal es `web` (solo texto), degradar a `text` automáticamente y loguear el
            downgrade. Si el canal tiene múltiples opciones de output (ej. WA), respetar la
            elección del agente o la preferencia del usuario.

- [x] 28.3  **Campo `response_type` en la respuesta del agente** — YA EXISTÍA
            (`response_type: text|audio|auto`, default auto=mirror del input; los agentes lo
            setean vía `updates`). Implementado como — el agente puede incluir en
            su respuesta un campo opcional `response_mode: "text" | "audio" | "auto"` para
            señalizar preferencia. `"auto"` (default) delega la decisión al canal/preferencia
            del usuario. El adaptador de cada canal (WA, ear, web) aplica la lógica:
            modo solicitado ∩ caps del canal, con fallback a text.

- [x] 28.4  **Revisión del campo del usuario** — el campo ya es `wa_notify_format`
            (específico de WA, NO el `notification_mode` ambiguo). Opción (b) ya realizada: es la
            preferencia de output de WA, y `channel_caps.resolve_output_mode` la usa como desempate
            cuando el modo es 'auto' y el input es ambiguo. Backoffice ya lo muestra (toggle).
            Original: — el campo actual
            (`notification_mode: text | audio`) fue diseñado para WA pero su semántica es
            ambigua en multi-canal. Decidir e implementar una de estas opciones:
            a) Reemplazarlo por preferencias por canal: `channel_prefs.wa.output_mode`,
               `channel_prefs.ear.output_mode`, etc.
            b) Renombrarlo a `default_output_mode` y usarlo como fallback cuando el canal
               soporta múltiples modos y el agente devuelve `"auto"`.
            La opción (b) es más conservadora y suficiente hasta tener más canales activos.
            Actualizar backoffice (`user_edit.html`) para reflejar el campo renombrado/reestructurado.

---

### FASE 29 - Ejecución Real de Planes de Inversión

```
Objetivo: Pasar el agente de inversiones de modo "dummy" (P&L hipotética) a modo real:
          mapear un monto de capital a un plan, ejecutar las órdenes en un broker,
          y ofrecer palancas de entrada/salida manuales y automáticas.
Estado:   Pendiente
Deps:     FASE 6 (planes, portfolio.py, COMPLETA), FASE 9 (coordinador, COMPLETA),
          FASE 26 (rutinas, para triggers automáticos).
Nota:     Alcance inicial acotado a instrumentos con API pública disponible (crypto vía
          exchange API, CEDEARs/acciones vía broker con API REST). El modo dummy coexiste:
          los planes sin capital asignado siguen siendo hipotéticos.
```

- [ ] 29.1  **Abstracción de broker (`broker_client.py`)** — interfaz común para ejecutar
            órdenes de compra/venta independientemente del proveedor. Métodos:
            `place_order(ticker, side, amount_usd)`, `get_positions()`, `get_balance()`,
            `cancel_order(order_id)`. Primera implementación concreta: broker simulado
            (`SimulatedBroker`) que registra órdenes localmente sin tocar APIs externas,
            para poder desarrollar y testear el flujo completo antes de conectar un broker real.
            Diseño abierto para agregar `LemonBroker`, `IOLBroker`, `BitsoClient`, etc.

- [ ] 29.2  **Activación de plan con capital real (`portfolio.py`)** — `activate_plan(user_id,
            plan_name, capital_usd)`: marca el plan como "activo" con el capital asignado,
            calcula la cantidad de cada instrumento según los pesos del plan y el precio actual,
            y registra las órdenes de compra en `broker_client`. El plan activo tiene
            `mode: "real" | "simulated"` y `capital_usd`, `activated_at` en su metadata.
            Los planes sin activar conservan `mode: "dummy"` y su P&L hipotética.

- [ ] 29.3  **Seguimiento de posiciones reales** — `portfolio.py` distingue posiciones dummy
            (precio snapshot al crear el plan) de posiciones reales (cantidad efectiva comprada,
            precio promedio de entrada). `calculate_plan_pnl()` usa precios de broker para
            planes reales y yfinance para dummy. El backoffice muestra badge "REAL" / "DUMMY"
            por plan, y para planes reales muestra capital invertido, valor actual y P&L en $.

- [ ] 29.4  **Comandos de entrada/salida por voz y WA** — el agente de inversiones reconoce:
            - "activá el plan X con $Y" → `activate_plan()` + confirmación explícita antes de ejecutar
            - "salí del plan X" → liquida todas las posiciones del plan (`close_plan()`)
            - "salí de TICKER en el plan X" → cierra solo esa posición
            - "¿cómo están mis posiciones reales?" → resumen de planes activos con P&L en $
            Toda orden que mueve dinero real requiere confirmación del usuario antes de ejecutar
            (intent con `needs_reply: true` y texto "¿Confirmás la compra de X por $Y?").

- [ ] 29.5  **Palancas automáticas de entrada** — sistema de triggers configurables por plan:
            - `entry_trigger`: condición para auto-activar un plan (ej: "cuando BTC baje 5% en
              el día", "el primer lunes de cada mes"). Implementado como regla evaluada en
              `finance_alerts.check()` o como rutina de FASE 26.
            - `entry_capital_usd`: capital a invertir al dispararse el trigger.
            - Flujo: trigger evalúa → notifica al usuario con opción de confirmar o cancelar
              dentro de una ventana de tiempo (ej: 30min). Si no hay respuesta, no ejecuta.
            - Los triggers se configuran desde el backoffice (campo en el formulario del plan).

- [ ] 29.6  **Palancas automáticas de salida** — por posición o por plan completo:
            - `stop_loss_pct`: cierra automáticamente si P&L cae por debajo del umbral.
            - `take_profit_pct`: cierra si P&L supera el umbral.
            - `trailing_stop_pct`: stop dinámico que sigue el máximo alcanzado.
            - Evaluados en cada ciclo de `finance_alerts.check()`. Al dispararse, notifica
              por WA/TTS antes de ejecutar y da una ventana de cancelación configurable
              (`exit_confirm_window_sec`, default 0 = inmediato para stop_loss).
            - Configurables por plan desde el backoffice.

- [ ] 29.7  **Historial de órdenes reales** — `broker_client` persiste cada orden ejecutada
            en `finance_orders_{uid}.json`: timestamp, ticker, side, cantidad, precio, status,
            broker. Endpoint `GET /finance/plans/{uid}/orders` en core. Sección en backoffice
            bajo el plan activo: tabla de órdenes con filtro por plan y estado.

---

### FASE 30 - Tool Calling por Agente (Agentic Loop)

```
Objetivo: Reemplazar el patrón "prompt con acciones en texto + parse manual" por tool
          calling real sobre Ollama. Cada agente declara un conjunto de tools (opcionalmente
          vacío). El proceso de ejecución implementa un agentic loop: LLM decide qué tool
          invocar, el agente la ejecuta, el resultado vuelve al LLM, hasta que el LLM
          produce una respuesta final. Todo queda registrado en los traces.
          Las tools son administrables desde el backoffice y se hidratan a partir de
          schemas OpenAPI: generados automáticamente para el core-api, o a través de
          adapters para APIs externas.
Estado:   COMPLETA
Deps:     FASE 9 (coordinador), FASE 24 (tracing).
```

- [x] 30.1  **`ToolDef` y `ToolStore` (`tool_store.py`)** — modelo de datos para una tool y su
            store de persistencia por agente:
            - `ToolDef`: `name`, `description`, `parameters` (JSON Schema), `source_url`
              (de dónde se hidrataron), `last_refreshed_at`, `enabled: bool`.
            - `ToolStore`: CRUD de tools por `agent_id`, persistido en
              `~/.local/share/capitan/tools/{agent_id}.json`.
            - Las tools se pueden habilitar/deshabilitar individualmente sin eliminarlas.
            - Cada agente puede tener tools o no. Un agente sin tools sigue funcionando
              con su lógica actual como fallback.

- [x] 30.2  **Schema OpenAPI del core-api (`GET /openapi-tools`)** — endpoint en `server.py`
            que retorna un schema OpenAPI 3.0 de los endpoints internos de core que son
            candidatos a ser tools (subset explícitamente marcado, no toda la API).
            Los endpoints candidatos se anotan con un decorator o campo `expose_as_tool=True`.
            El schema incluye description, parameters y response summary para cada operación.
            Este endpoint es el que usan los agentes del sistema para auto-hidratarse.

- [x] 30.3  **Adapter OpenAPI para backends externos (`openapi_adapter.py`)** — módulo que,
            dado un backend con API documentada, produce un schema OpenAPI normalizado:
            - Si el backend expone `/openapi.json` o `/swagger.json`: lo consume directamente.
            - Si no: recibe un documento de descripción (markdown/texto) y lo convierte a
              schema OpenAPI mediante una llamada LLM (one-shot, resultado cacheado).
            Backends iniciales a cubrir: `trace_store` (interno, via 30.2), `intent_state`
            (interno, via 30.2), `weather_providers` (externo, Open-Meteo tiene OpenAPI),
            `ml_client` (externo, MercadoLibre tiene OpenAPI pública).
            El adapter expone `get_schema(backend_id) -> dict` que retorna el schema
            normalizado independientemente del origen.

- [x] 30.4  **Hidratación de tools por agente (`tool_hydrator.py`)** — lógica en el backend
            core que, dado un `agent_id`, obtiene el schema de cada backend asociado al agente
            (via 30.2 o 30.3), filtra las operaciones relevantes para ese agente, y actualiza
            el `ToolStore` con las `ToolDef` resultantes. Endpoint `POST /agents/{agent_id}/tools/refresh`
            que dispara la hidratación y retorna el listado actualizado. La lógica de "qué
            backend corresponde a qué agente" se declara en el agente mismo (`backends` ya
            existe en `base_agent.py`; extender con `tool_sources: list[str]`).

- [x] 30.5  **Agentic loop en `process()` (`agent_loop.py`)** — implementación genérica del
            loop de tool calling sobre Ollama (`/api/chat` con campo `tools`):
            ```
            messages = [system] + conv.context() + [user]
            while True:
                response = llm(messages, tools=enabled_tools)
                if response.stop_reason != "tool_use": break
                for call in response.tool_calls:
                    result = dispatch_tool(call.name, call.arguments)
                    messages.append(tool_result(call.id, result))
            return response.content
            ```
            `dispatch_tool` invoca el endpoint o función correspondiente a cada tool.
            El loop tiene un límite configurable de iteraciones (default 5) para evitar
            ciclos. Si se agota, el agente retorna la última respuesta parcial del LLM.
            Los agentes existentes migran a este loop cuando tienen tools habilitadas;
            sin tools, siguen con su lógica actual intacta.

- [x] 30.6  **`ToolCall` en traces (`trace_store.py`)** — agregar formalmente el evento de
            invocación de tool al modelo de trace:
            - Nueva dataclass `ToolCall`: `tool_name`, `arguments: dict`, `result: dict`,
              `latency_ms`, `ts`, `iteration: int` (número de vuelta del loop).
            - `AgentStepTrace` incorpora `tool_calls: list[ToolCall]`.
            - El agentic loop (30.5) registra cada `ToolCall` en el step activo via
              `record_tool_call()` (nuevo helper en `trace_store.py`).
            - Las `LLMCall` del loop se registran con `source = "agent_{agent_id}_iter_{n}"`.

- [x] 30.7  **Backoffice — gestión de tools por agente** — sección nueva en la página de
            configuración de cada agente en el backoffice:
            - Lista de tools disponibles con nombre, descripción, origen (URL del schema)
              y último refresh.
            - Toggle enable/disable por tool individual.
            - Botón "Refresh tools" que llama a `POST /agents/{agent_id}/tools/refresh`
              (30.4) y recarga la lista.
            - Si el agente no tiene `tool_sources` declarados, la sección muestra un
              mensaje informativo en lugar de un error.

- [x] 30.8  **Migración piloto: `SystemAgent`** — migrar `system_agent.py` como primer agente
            al nuevo modelo. Sus tools se hidratan desde el core-api (30.2): `list_agents`,
            `get_intents`, `list_proactive_runs`, `get_trace`, `get_goal`, etc. El `_SYSTEM`
            hardcodeado se reemplaza por un system prompt genérico sin lista de acciones.
            Los tests existentes se actualizan para cubrir el loop y la invocación de tools.

- [x] 30.9  **Tests** — `tests/test_tool_store.py`: CRUD de ToolDef, enable/disable, persistencia.
- [ ] 30.10  Discusion: modelar skills reutilizables y componibles (coordinador + agentic loop)
            `tests/test_tool_hydrator.py`: hidratación desde schema mockeado (sin llamadas
            reales). `tests/test_agent_loop.py`: loop completo con Ollama mockeado — verifica
            iteraciones, límite de ciclos, registro en trace.

---

### FASE 31 - Optimización de Performance LLM en Brain

```
Objetivo: Explorar palancas de mejora de latencia LLM en el Brain (Beelink, Radeon 780M gfx1103).
          Baseline actual: 27.5s CPU-only, 13.3s ROCm con HSA_OVERRIDE_GFX_VERSION=11.0.0.
          Target: reducir latencia warm por debajo de 5s sin cambiar el modelo.
Estado:   COMPLETA (5/5 — Vulkan/ROCm, keepalive, iGPU, benchmark de quantización: se mantiene q4_k_m)
Deps:     FASE 21 (Brain operativo con LXC — COMPLETA)
Hardware: Beelink SER9 Pro — Ryzen AI 7 HX 255, 32GB DDR5, Radeon 780M (RDNA 3 / gfx1103)
```

- [x] 31.1  Vulkan backend: benchmarkar `OLLAMA_GPU_BACKEND=vulkan` vs ROCm en Brain.
            La 780M tiene soporte Vulkan nativo y estable — puede superar el ROCm parcial.
            Medir latencia warm con ambos backends. Documentar ganador en NOTAS.
- [x] 31.2  Warm LLM keepalive: configurar `OLLAMA_KEEP_ALIVE` para evitar descarga del
            modelo entre requests. Por defecto Ollama descarga el modelo tras 5 min idle.
            Agregar `OLLAMA_KEEP_ALIVE=-1` al systemd unit del LXC.
- [x] 31.3  Lazy entity index: diferir la construcción del entity index (nomic-embed-text)
            al primer request en lugar de hacerlo en startup. Elimina los 30s de arranque
            del core. El índice se construye en background al recibir el primer /process.
- [x] 31.4  Benchmark warm vs cold: medir latencia warm (modelo ya cargado) vs cold para
            entender el real bottleneck. Si warm < 3s, el problema es solo el cold start.
- [x] 31.5  Quantización alternativa: benchmarkar qwen2.5:7b con distintas quantizaciones
            (q4_0 vs q4_k_m vs q5_k_m) en Brain para encontrar el mejor balance velocidad/calidad.
            Resultado (warm, prompt domótica, GPU ROCm): q4_k_m 1.68s/12.8 tok/s (actual) ·
            q4_0 1.35s/16.2 tok/s · q5_k_m 1.41s/15.3 tok/s. q4_0 ~20% más rápido y mantiene el
            formato ACTION en el caso simple, pero es el quant de menor calidad (riesgo en
            coordinador multi-paso / respuestas matizadas). **Decisión: seguir en q4_k_m** — el
            0.33s de q4_0 no justifica el riesgo de calidad; q5_k_m no gana lo suficiente para su
            tamaño. Nota operativa: cargar 3 modelos de ~5GB a la vez en la iGPU compartida causa
            ROCm "unspecified launch failure" (transitorio) — benchmarkear uno por vez con keep_alive=0.

---

### FASE 32 - Migración de datos a base de datos formal

```
Objetivo: Reemplazar los JSON files en ~/.local/share/capitan/ por una base de datos
          estructurada (SQLite). Elimina problemas de concurrencia, mejora queries,
          facilita backup y migración entre servidores.
Estado:   COMPLETA (32.1-32.6: esquema + db.py + migración + módulos migrados a SQLite +
          backup. Validado en producción contra datos reales del Brain: el core lee y escribe
          de capitan.db; los JSON migrados se movieron a un backup (_pre_db_backup_*). Quedan
          como archivos por diseño: embeddings .npy, wakeword_samples, wa-session, traces JSONL,
          wakeword_metrics. Los **paneles** también se completaron a la DB (tabla `panels`, core
          expone `GET/POST/DELETE /panels`; backoffice/scripts/provisioning lo consumen;
          `panels.yaml` removido).)
Deps:     FASE 21 (Brain estable — COMPLETA)
Motivación: actualmente los datos (usuarios, intents, conversaciones, portfolios,
            contextos, routines, etc.) son ~30 archivos JSON sin esquema formal,
            sin transacciones, sin índices. Migración costosa pero necesaria para escalar.
```

- [x] 32.1  Inventario y esquema: mapear todos los archivos de datos/config actuales a tablas
            SQLite. **Entidades del sistema** (objetos de dominio propios) que hoy viven en files:
            usuarios, paneles (`panels.yaml`), conversaciones, intents, goals, routines, agents,
            portfolios, contexts, ml_prices, finance_news, feriados, wakeword_metrics, embeddings.
            Identificar relaciones (user → intents/conversations/portfolio; panel → users).
            Definir esquema con migraciones (alembic o schema_version manual).
            > Las entidades de **HAOS** (entity_index / aliases / mapa de `ha_client`) son otra cosa
            > (catálogo externo de Home Assistant) — opcional moverlas a una tabla de config; no es
            > el foco. El foco son los objetos del sistema (usuarios, paneles, etc.).
- [x] 32.2  Capa de acceso unificada: crear `core/db.py` con conexión SQLite y helpers
            CRUD que reemplacen los json read/write actuales. Mantener API idéntica
            para no romper agentes existentes.
- [x] 32.3  Migración de datos existentes: script `scripts/migrate_to_db.py` que lee los
            JSON actuales y los inserta en la DB. Idempotente y con dry-run.
- [x] 32.4  Migrar módulos críticos: users.py, conversations.py, intents.py, portfolios.
            Un módulo a la vez con tests. Los JSON se mantienen como fallback hasta
            que todos los módulos estén migrados.
- [x] 32.5  Backup automático: script diario que hace `sqlite3 capitan.db .dump > backup.sql`
            y lo guarda en un directorio de backups rotados (7 días).
- [x] 32.6  Eliminar JSON files: una vez todos los módulos migrados y backup operativo,
            borrar los archivos JSON y el código de lectura legacy.

---

### FASE 33 - Backoffice en la nube (acceso remoto seguro, egress-only)

```
Objetivo: Tener un backoffice accesible desde internet SIN exponer el Brain ni HAOS.
          La nube nunca inicia conexiones hacia la casa: el Brain empuja estado para
          dibujar el dashboard y POLEA una cola de comandos para ejecutar acciones de
          administración (patrón command / executor). Plataforma: Google Cloud.
Estado:   COMPLETA — cloud + bridge + login consistente (roster email→rol) + RBAC, y SSO
          del backoffice local (reusa el Google sign-in de la nube) + RBAC local. Verificado e2e.
Deps:     FASE 12 (backoffice local — COMPLETA, fuente de datos y UI a reusar),
          FASE 21 (Brain estable — COMPLETA), FASE 32 (datos en SQLite — COMPLETA).
Principio de seguridad: el Brain sólo hace conexiones SALIENTES (HTTPS) a la nube.
          Cero port-forwarding, cero inbound, HAOS/core nunca tocan internet. La
          superficie de ataque en la casa es nula; si la nube cae, el sistema local
          sigue operando y el backoffice local (LAN) sigue disponible.
Arquitectura:
          [Brain LXC] --push estado-->  [Cloud Run + Firestore]  <--dashboard-- [navegador]
          [Brain LXC] --poll comandos->  (cola en Firestore)     <--emite cmd-- [navegador]
          [Brain LXC] --post resultado-> (estado del comando)
Stack GCP elegido: Cloud Run (web + API, scale-to-zero), Firestore (snapshot de
          estado + cola de comandos), Identity Platform/Firebase Auth (login del
          dashboard, restringido al email del usuario), Secret Manager (credenciales),
          Service Account con permiso mínimo para el bridge. Alternativa evaluada:
          Pub/Sub pull para comandos — se prefiere Firestore por unificar estado+cola
          y dar histórico/auditoría con TTL.
```

#### Etapa A - Diseño y contrato
> Diseño completo en `masterplan/fase33_cloud_backoffice.md`.
- [x] 33.1  Documentar el modelo egress-only y el modelo de amenazas: qué datos salen de
            la red local, qué NO sale nunca (tokens HAOS, .env, PII sensible), y por qué la
            nube no puede iniciar conexiones hacia la casa.
- [x] 33.2  Definir el contrato del snapshot de estado (server→nube): servicios up/down,
            latencias STT/LLM/HAOS, agentes activos, últimos comandos, métricas de wake word,
            usuarios (sin datos sensibles). Minimizar el subconjunto que sale de la LAN.
- [x] 33.3  Definir el catálogo TIPADO de comandos admin permitidos (allowlist): restart de
            servicio, redeploy, ver logs, recargar config, reentrenar wake word, re-enrolar voz,
            etc. Cada comando es un tipo cerrado con parámetros validados. NUNCA shell arbitrario.
- [x] 33.4  Definir autenticación en ambas direcciones: dashboard vía Identity Platform
            restringido al email del usuario; bridge del Brain vía token OIDC de Service Account
            (sin API keys embebidas si se puede). Definir rotación de credenciales.

#### Etapa B - Servicio en la nube (Cloud Run + Firestore)
> Desplegado en capitan-495518 (southamerica-east1): https://capitan-cloud-m2x3ep3hfa-rj.a.run.app
- [x] 33.5  Servicio Cloud Run (FastAPI) en `cloud/`: endpoints `POST /ingest/state`,
            `GET /commands/pending`, `POST /commands/{id}/result`, y la API que consume el
            dashboard. HTTPS gestionado, scale-to-zero.
- [x] 33.6  Firestore: colección `state` (snapshot actual + histórico corto) y `commands`
            (estados pending/running/done/error con TTL). Reglas de seguridad por colección.
- [x] 33.7  Frontend del dashboard servido por Cloud Run: nuevo y mínimo (estado de
            servicios, latencias, agentes, historial, panel de acciones que emite comandos).
- [x] 33.8  Login del dashboard con Identity Platform/Firebase Auth, allowlist por email.
- [x] 33.9  IaC reproducible (script gcloud): `infra/provision.sh` (Cloud Run, Firestore,
            TTL, SAs) + `infra/setup_firebase.sh` (Identity Platform/Firebase Auth).

#### Etapa C - Bridge / executor en el Brain
> Desplegado en capitan-lxc: `cloud/bridge/` + systemd `capitan-bridge.service`.
- [x] 33.10 Daemon `cloud_bridge.py` (systemd unit en el LXC): push periódico del snapshot
            de estado a `/ingest/state`, reusando datos que ya escriben core/backoffice.
- [x] 33.11 Loop de polling: `GET /commands/pending` con backoff/reconexión; ejecuta cada
            comando contra el allowlist tipado; postea el resultado a `/commands/{id}/result`.
- [x] 33.12 Executor seguro: cada tipo de comando mapeado a una función concreta (sin eval).
            Auditoría: log de cada comando ejecutado, parámetros y resultado.
- [x] 33.13 Credenciales del bridge: Service Account con permiso mínimo (sólo los endpoints
            necesarios), almacenadas fuera del repo. Rotación documentada.

#### Etapa D - Seguridad, costo y operación
- [x] 33.14 Rate limiting y validación de payloads en ingest/commands; firma/verificación.
            (token bucket por identidad + middleware de tamaño 512KB; OIDC = firma; Pydantic)
- [x] 33.15 Auditoría visible en el dashboard: quién emitió cada comando, cuándo y resultado.
- [x] 33.16 Mantener dentro del free tier de GCP (Cloud Run scale-to-zero, cuota de Firestore);
            alerta de presupuesto. (budget USD 5, alertas 50/90/100%)
- [x] 33.17 Failover: si la nube cae, el Brain sigue operando local y el bridge reintenta; si el
            bridge cae, el backoffice local en LAN (FASE 12) sigue disponible. (verificado e2e)

#### Etapa E - Login consistente con gestión de usuarios + RBAC
> Decisión: email de login dedicado en User; RBAC cloud = admin full / familiar read-only /
> adolescente restringido (read-only, vista básica) / niño·invitado·guest sin acceso.
- [x] 33.18 Identidad de login: agregar campo `email` a User (core/users.py + db_schema +
            migración idempotente ALTER TABLE), default a gcal_email; editable en el backoffice
            local; tests. El email es la identidad contra la que se valida el login de Google.
- [x] 33.19 Contrato + bridge: incluir `email` en `users_summary` del snapshot; el cloud, al
            ingestar el snapshot, materializa un roster email→rol en Firestore para autorizar.
- [x] 33.20 Cloud auth consistente: `require_dashboard_user` autoriza contra el roster (reemplaza
            el `ALLOWED_EMAILS` estático, que queda sólo como bootstrap de emergencia → admin);
            email no registrado → 403; la dependencia devuelve Principal(email, rol, caps).
- [x] 33.21 RBAC del cloud backoffice: capacidades por rol (admin: ver todo + emitir comandos;
            familiar: read-only completo; adolescente: read-only vista básica sin PII/auditoría;
            resto: sin acceso). Gate de `/api/commands` y filtrado de datos sensibles por
            capacidad; el frontend oculta acciones sin permiso; tests.
- [x] 33.22 SSO broker en la nube: endpoint `/sso/start?redirect_uri=...` que, tras el Google
            sign-in ya existente, emite un token firmado (HMAC, exp corto) y redirige al
            backoffice local. Allow-list de redirect_uri (orígenes LAN permitidos).
- [x] 33.23 Backoffice local: aceptar el SSO token (verificar firma+exp), mapear email→usuario→rol
            (DB local), sesión atada al usuario; el header muestra usuario·rol; `BACKOFFICE_TOKEN`
            queda como bootstrap de emergencia offline (→admin). Acceso por IP de la LAN.
- [x] 33.24 RBAC en el backoffice local: admin escribe; familiar/adolescente read-only (bloqueo
            de POST/PATCH/DELETE/PUT por middleware); roles sin acceso rechazados. Tests.

### FASE 34 - Deploy remoto al Brain (CD sobre el bridge egress-only)

```
Objetivo: Desplegar al Brain desde cualquier lado (fuera de la LAN) de forma segura,
          versionada y reversible, SIN abrir un solo puerto entrante en la casa. El
          deploy es un comando tipado más en el allowlist del bridge (FASE 33): el
          dashboard cloud lo emite, el Brain lo polea y lo ejecuta como un release CD
          (pin de ref por submodule → snapshot → deploy atómico → health-gate →
          rollback automático si falla), registra la versión desplegada y la reporta.
Estado:   COMPLETA (34.17 postergada — extracción de submodules, tanda aparte). Motor único
          LIVE en el Brain con dos invocadores (executor remoto + deploy.sh), pin/health/rollback
          atómico por repo, versionado semver (34.12, v0.1.0), logs en vivo end-to-end (D5),
          driver cloudrun (cloud-bo desde el Brain + rollback a revisión previa) y satélites bajo
          el motor (34.13 auto-update + 34.16 force pull). MATRIZ UNIFICADA DE TARGETS (34.15):
          una fila por cosa que corre (core/audio_server/backoffice/cloud-bo + un satélite por
          panel) con versión que corre + última disponible + link a GH + botón "Actualizar" que
          elige el comando solo; en cloud-bo (opera) y backoffice local (read-only). Contrato de
          release persistido (34.2: refs/ts/resultado/rollback en deploy_state.json; "quién emitió"
          por la auditoría de comandos 33.15). Tests (34.10) + docs (34.11) completos.
Deps:     FASE 33 (bridge egress-only + allowlist tipado + auth/audit/RBAC — COMPLETA,
          ya existe el comando `deploy.run` que esta fase eleva a CD real),
          FASE 21 (Brain estable — COMPLETA), FASE 12 (backoffice — COMPLETA).
Principio de seguridad: se hereda intacto el modelo de FASE 33 — el Brain sólo hace
          conexiones SALIENTES. El deploy NO es un canal nuevo: es un tipo de comando
          más en la cola que el Brain ya polea. Cero inbound, cero port-forwarding, cero
          SSH expuesto. Descartado VPN/Tailscale + SSH por abrir canal entrante.
Principio de unificación de backend (CIMIENTO, no cleanup posterior): existe UN solo
          motor de deploy que corre en el Brain (snapshot → pin de ref → install →
          restart → health-gate → rollback). Ese motor es el ÚNICO backend de deploy.
          Hay UN solo frontend de deploy: el dashboard cloud egress-only (FASE 33), para
          operar el deploy de forma REMOTA. En LOCAL no hay frontend/UI interno: el
          operador es Claude (corriendo en la laptop), que invoca el motor directamente
          vía `scripts/deploy.sh` / la skill `deploy`. Es decir, dos invocadores del
          mismo motor:
            - Remoto: dashboard cloud egress-only → comando `deploy.release` → el bridge
                      executor NO reimplementa deploy, sólo invoca el motor en el Brain.
            - Local:  Claude → `scripts/deploy.sh` (wrapper fino que invoca el motor por
                      SSH). No es una "UI": es el operador humano/Claude llamando al motor.
          Regla: ninguna lógica de deploy (pin/install/restart/health/rollback) puede
          vivir duplicada en `deploy.sh` ni en `cloud/bridge/executor.py`. Toda vive en
          el motor; ambos invocadores sólo lo llaman. Se construye desde la primera tarea
          de la Etapa B, no se "unifica" al final.
Principio de versionado formal en GitHub: el motor de deploy crea versiones FORMALES en
          GitHub (git tag + GitHub Release) por cada release exitoso, de modo que "qué
          versión está desplegada" sea un ref real, inmutable y trazable (no un sha suelto).
          La versión desplegada de CADA componente (core, ear, umbrella), referenciando ese
          release, se muestra en LOS DOS frontends: el dashboard cloud egress-only Y el
          backoffice interno (LAN, FASE 12). El rollback también queda registrado como evento
          sobre esos refs versionados, visible en ambos.
Punto de partida (gap a cerrar): hoy `deploy.run` (cloud/bridge/executor.py) hace
          `git pull --recurse-submodules` ciego a main + install + restart. No pinea
          ref, no snapshotea el estado previo, no hace health-check, no revierte si el
          restart deja el sistema roto, no versiona en GitHub y no registra/muestra qué
          versión quedó corriendo por componente.
Alcance multi-dispositivo (segundo gap): el componente `ear` NO corre en un solo lugar.
          `audio_server.py` corre en el Brain LXC; `satellite.py`/`satellite_ui.py` corren en
          CADA NSPanel (comedor, etc.) vía Termux, desplegados por un mecanismo APARTE y no
          trazado (`scripts/nspanel.sh` hace `scp` del satellite a cada panel; el hot-update
          es scp + pkill, fuera de `deploy.sh`). El motor de deploy no toca los paneles. Por
          eso la versión correcta a modelar no es "ref por componente" sino una MATRIZ
          `dispositivo × componente → versión` (Brain: core/backoffice/wa/audio_server; cada
          NSPanel: satellite), donde un panel puede quedar rezagado sin que nada lo registre.
          Camino egress-only: el satélite ya se registra contra `audio_server` (cuyo estado
          ya viaja al snapshot), así que reporta su versión al registrarse → snapshot → nube.
Arquitectura (un motor, dos invocadores):
          REMOTO (frontend): [dashboard cloud] --deploy.release(refs)--> [Firestore]
                             [Brain bridge] --poll--> executor (sin lógica propia) ─┐
          LOCAL (sin UI):    [Claude/laptop] --SSH--> scripts/deploy.sh (wrapper) ─┤
                                                                                   ▼
                                            [MOTOR DE DEPLOY en el Brain]
              snapshot ref actual → fetch+checkout ref pedido → install → restart
              → health-gate (/health core+backoffice)
                  → OK:   tag + GitHub Release por componente → registra versión desplegada
                  → FAIL: rollback al snapshot (registra evento sobre los refs versionados)
```

DECISIONES CONSOLIDADAS (2026-06-20, al tomar la fase — amplían el alcance de arriba):
  D1. Brain = ejecutor UNIVERSAL. TODO el deploy (de cualquier componente, en cualquier
      dominio) se dispara como comando del backoffice CLOUD y lo ejecuta el Brain al polearlo
      (egress-only). No hay deploy directo desde la notebook fuera del flujo de comandos. Razón:
      desde fuera de casa la notebook NO tiene ruta a la LAN (Brain/paneles); el único plano de
      control común es el cloud-bo. El `scripts/deploy.sh` local queda como wrapper fino para
      cuando Claude opera DESDE la LAN, invocando el mismo motor.
  D2. El motor tiene UN driver por tipo de target (misma interfaz: snapshot→deploy→health→
      rollback→registro de versión):
        - driver `ser9-service` (core, wa, backoffice-local, ear/audio_server, bridge):
          git pin ref → install si cambió requirements → systemctl restart → health-gate
          (/health) → rollback = checkout del ref del snapshot.
        - driver `panel` (satellite.py/satellite_ui.py por NSPanel): el motor (en la LAN)
          hace el push VERIFICADO (checksum+readback) → restart vía supervisor → health =
          el nodo re-registra en audio_server con su versión → rollback = push del ref previo.
          Absorbe la Etapa E (deploy a paneles robusto) y los footguns de pkill/supervisor.
        - driver `cloudrun` (cloud-bo, oauth-app/meli): `gcloud run deploy --source` (egress
          a GCP) → health-gate = curl a la URL pública → rollback = `gcloud run services
          update-traffic` a la revisión previa (Cloud Run conserva revisiones).
  D3. El Brain requiere credencial gcloud con rol run.admin (+ acceso al build) para el driver
      cloudrun. Sigue siendo EGRESS-ONLY (llama a las APIs de Google, saliente). Aprovisionar.
  D4. Circularidad de la cloud (desplegar cloud-bo y romperla = perder el canal de comandos):
      se mitiga con health-gate + rollback automático a la revisión previa de Cloud Run que el
      propio Brain dispara (no depende de la cloud para revertir). Escape hatch documentado:
      `gcloud run deploy` manual desde la notebook si el rollback automático también falla.
  D5. Feedback rico con LOGS EN VIVO (requisito de UX): el modelo de comandos pasa de
      fire-and-result a PROGRESO INCREMENTAL — el motor emite líneas de log; el bridge las
      postea append-only (Firestore) por comando; el cloud-bo las polea y las muestra en
      streaming durante el deploy. La consola local tail-ea el log del motor directo. Aplica a
      deploys disparados desde cloud-bo Y desde la consola local.
  D6. Visualización de versión (requisito de UX): la versión corriendo de CADA componente, con
      LINK a la versión tageada en GitHub (release), se muestra en LOS DOS backoffices (local y
      cloud). Es la matriz dispositivo×componente→versión de 34.14, con deep-link al release.
  D7. Atomicidad POR-COMPONENTE (no por-release): si un release toca varios componentes y uno
      falla su health-gate, sólo ESE componente revierte a su snapshot; los demás (sanos) quedan
      desplegados. No se revierte un componente sano porque otro falló. (Confirmado 2026-06-20.)
  D8. Versionado SEMVER (vX.Y.Z) por componente; el tag vive en el repo de cada componente
      (core/ear/umbrella) y el GitHub Release referencia ese tag. El bump (patch auto vs
      minor/major explícito) se define en 34.12. (Confirmado 2026-06-20.)
  D9. El driver cloudrun usa una SA de deploy DEDICADA (separada de runtime y bridge SA), con
      permiso mínimo: run.admin (deploy + update-traffic/rollback), cloudbuild.builds.editor,
      artifactregistry.writer, iam.serviceAccountUser (actuar como la runtime SA), storage sobre
      el bucket de staging de Cloud Build. Key JSON en el Brain (egress-only). Script idempotente:
      cloud/infra/provision_deploy_sa.sh. (Confirmado 2026-06-20.)
      ACTIVADO Y PROBADO (2026-06-21, T4a): driver cloudrun deploya el cloud-bo desde el Brain
      end-to-end (build en Cloud Build → deploy → health → ok), y el rollback automático a la
      revisión previa quedó validado (en intentos fallidos por permisos, el cloud-bo se restauró
      sano solo). Hecho: gcloud CLI instalado en el Brain; SA capitan-deployer con run.admin +
      cloudbuild.builds.editor + artifactregistry.writer + storage.admin + logging.viewer
      (proyecto) + actAs sobre runtime SA del cloud-bo y la default compute SA del build; key JSON
      en ~/.config/capitan/deployer-key.json del Brain + SA activada en gcloud (root). Permisos
      reproducibles en cloud/infra/provision_deploy_sa.sh. FALTA: capitan-oauth como 2º target
      (otra región us-east1 + env vars/secrets); driver panel (34.13 T4b).
```

#### Etapa A - Contrato del release
- [x] 34.1  Extender el comando tipado a `deploy.release` (o ampliar `deploy.run`) en
            `cloud/app/commands.py`: aceptar `core_ref` y `ear_ref` opcionales (default =
            HEAD remoto de main), validados como sha/tag/branch con un validador estricto
            (rechazar refs arbitrarios/inyección); mantener `restart_wa`. Tests del catálogo.
- [x] 34.2  Definir el contrato de "release" como dato versionado: refs desplegados por
            submodule + commit del umbrella, timestamp, quién lo emitió, resultado y estado
            del health-gate, y si hubo rollback. Persistencia local en el Brain (fuente de
            verdad) y subconjunto reportado en el snapshot a la nube.

#### Etapa B - Motor de deploy en el Brain (único backend: atómico + reversible)
- [x] 34.3  Crear el MOTOR de deploy como artefacto ÚNICO que corre en el Brain (script/
            módulo, p.ej. `scripts/deploy_engine.sh` o `cloud/bridge/deploy_engine.py`),
            invocable por CLI con args tipados (refs por submodule, restart_wa). Es el único
            lugar con lógica de deploy; ningún frontend la duplica. Snapshot pre-deploy:
            capturar el ref/commit actual de cada submodule (y del umbrella) ANTES de tocar
            nada, para revertir exactamente a ese estado.
- [x] 34.4  Deploy con pin (en el motor): `git fetch` + `checkout` del ref pedido por
            submodule (en lugar del `pull` ciego a main); reinstalar requirements sólo si
            cambiaron; restart de servicios. Lock de deploy (un único release a la vez) e
            idempotencia.
- [x] 34.5  Health-gate post-deploy (en el motor): tras el restart, verificar `/health` de
            core y backoffice (y readiness del propio bridge) con timeout + retries antes de
            declarar éxito. Reusar la lógica del smoke test de `scripts/deploy.sh`.
- [x] 34.6  Rollback automático (en el motor): si el health-gate falla, revertir a los refs
            del snapshot, reinstalar, reiniciar y re-chequear; reportar `FAILED + rolled-back`
            con el detalle de cada paso. Tras un rollback el sistema queda en el último estado
            sano.
- [x] 34.12 Versionado formal en GitHub (en el motor, camino de éxito post health-gate):
            crear tag + GitHub Release por componente desplegado (core/ear/umbrella) con el ref
            efectivamente desplegado y un esquema de versión consistente (semver o fecha+sha).
            El tag/release es la fuente de verdad de "qué versión está corriendo" (ref inmutable).
            El rollback registra un evento sobre esos refs versionados. Esta versión por
            componente la consumen los dos frontends (34.7). Requiere credencial de GitHub para
            el motor en el Brain (egress-only; el Brain ya hace sólo conexiones salientes).

#### Etapa C - Visibilidad y operación
- [x] 34.7  Registrar la versión desplegada por componente (core/ear/umbrella → release de
            GitHub + estado del release) y exponerla en LOS DOS frontends: (a) dashboard cloud
            egress-only vía snapshot, y (b) backoffice interno (LAN, FASE 12) leyendo el estado
            local del Brain. Mostrar versión actual corriendo, último deploy, resultado y si
            hubo rollback. Auditoría reusa la de FASE 33 (quién emitió, cuándo).
- [x] 34.13 Satélites NSPanel bajo el motor único (cierra el gap multi-dispositivo): el motor
            (o un sub-comando `deploy.satellites`) despliega `satellite.py`/`satellite_ui.py` a
            los paneles registrados con pin de ref (no el `scp` suelto de `nspanel.sh`), reusando
            su transporte; registra la versión desplegada por panel. El satélite AUTO-REPORTA su
            versión (ref/tag corriendo) al registrarse en `audio_server`. Tests con scp/ssh
            mockeados. (Hereda el modelo egress-only y los footguns de pkill/supervisor del panel.)
- [x] 34.14 Matriz `dispositivo × componente → versión` en LOS DOS frontends: en vez de "versión
            de core", una tabla por dispositivo (Brain: core/backoffice/wa/audio_server; cada
            NSPanel: satellite) con la versión corriendo, si está rezagada vs. el release vigente,
            y último deploy/rollback por dispositivo. La versión por panel llega vía snapshot
            (audio_server → bridge). Reusa el panel de versiones de 34.7.
- [x] 34.8  Panel de deploy en el dashboard cloud (RBAC: sólo admin emite): botón de deploy
            contextual por componente en la matriz de versiones (repo Brain → deploy.release;
            cloud-bo → deploy.cloud; '⬆ actualizar' cuando behind). Reusa el gate CAPS.emit y
            el streaming de logs (streamCommand) de FASE 33; el frontend oculta la acción a
            no-admin. El form admin genérico (select+JSON) se conserva para pin de refs y wa/bridge.
- [x] 34.9  Invocadores sobre el motor único (cierra el principio de unificación). Las dos
            rutas invocan el MISMO motor (34.3-34.6); ninguna reimplementa nada:
            (a) REMOTO — el `executor` del bridge (`cloud/bridge/executor.py`) deja de hacer
                `git pull` propio y pasa a invocar el motor con los refs de `deploy.release`;
                el bridge sólo traduce comando→args y reporta resultado;
            (b) LOCAL — `scripts/deploy.sh` pasa a ser un wrapper fino que invoca el motor por
                SSH (es el deploy que Claude corre desde la laptop; no hay UI interna de deploy).
            Verificar que no quede lógica de pin/install/restart/health/rollback duplicada
            fuera del motor.

```
REGISTRO — Deploy a los paneles (satélites): frágil y sin trazabilidad (a formalizar como
Etapa E al tomar la fase). Hallazgos de campo 2026-06-19 (update manual de satellite.py en
comedor + pieza):
  1. deploy.sh no cubría el satélite ni el audio_server (ear). audio_server ya se agregó
     (restart + smoke), pero el satellite.py de cada NSPanel sigue desplegándose a mano
     (scp + pkill), fuera de todo flujo verificado.
  2. El push del supervisor (voice-node.sh) por heredoc SSH se TRUNCÓ a archivo vacío con un
     blip de red, sin error visible → el satélite no arrancaba y nada lo detectó. Falta
     verificación de integridad post-copia (conteo de líneas/checksum) y readback.
  3. Termux:Boot NO disparó start-ha.sh tras `adb reboot` (Android booteó pero sshd + voice
     node quedaron caídos) → hubo que recuperar a mano por ADB (abrir Termux, tipear sshd).
  4. Los procesos lanzados detached por SSH (`setsid nohup`) mueren al cerrar la sesión salvo
     que el supervisor sostenga `termux-wake-lock`; lanzar el satélite suelto no persiste.
  5. Divergencia entre paneles: la pieza se aprovisionó con una versión VIEJA de nspanel.sh
     (boot directo `nohup python satellite.py`, sin supervisor); el comedor con voice-node.sh.
     No había forma de saber "qué corre en cada panel".
  6. Sin visibilidad de versión: el satélite no reporta qué código corre → no hay certeza de
     la versión por panel. Cruza la matriz dispositivo×componente→versión ya descrita arriba.
Estado tras la sesión: ambos paneles quedaron con el mismo mecanismo (voice-node.sh + boot
script canónico) y el mismo satellite.py, y ambos reportan IP al audio_server. Pero todo el
procedimiento fue manual y sin red de seguridad.

Etapa E (T4b) — HECHO 2026-06-21 (escritura verificada + convergencia + #602 resuelto):
  E.1 ✓ Escritura VERIFICADA por checksum (put_verified: scp + readback de sha256 con reintentos)
       en `scripts/nspanel.sh`, reemplazando el `ssh "cat > file" <<EOF` ciego que truncaba.
  E.3 ✓ Robustez de arranque: causa de #602 hallada = el `start-ha.sh` de la pieza quedó en
       0 bytes (heredoc truncado) → Termux:Boot lo ejecutaba pero no arrancaba nada. start-ha.sh
       canónico (wake-lock+sshd+HA+supervisor) + Termux:Boot + dumpsys deviceidle whitelist
       (batería). Validado: la pieza arranca TODO sola al reboot (sshd+supervisor+satellite).
  E.4 ✓ `nspanel.sh converge <node_id> <room> [ip]`: lleva CUALQUIER panel al estado canónico
       (satellite + scripts de arranque verificados, Termux:Boot+batería), idempotente; corrige
       setups viejos/truncados. provision refactorizado para usar el mismo write_node_scripts.
       Aplicado a comedor y pieza.
  E.2 (pendiente, va con T5/matriz): el satélite reporta su VERSIÓN (hash) en el heartbeat →
       audio_server la expone en GET /nodes → matriz dispositivo×componente.
  Pendiente T4b-motor: integrar el deploy de paneles al MOTOR único (comando deploy.satellites
       que invoca la convergencia) para operarlo desde el cloud-bo como los otros drivers.
  NOTA: el TERMUX_USER difiere por panel (comedor u0_a113, pieza u0_a53, según apps previas en
       cada Android); se pasa por env TERMUX_USER. A futuro: detectarlo automáticamente.
```

#### Etapa F - Matriz de targets unificada + compartimentación física
- [x] 34.15 Matriz de TARGETS unificada (operatoria): en vez de mostrar repos/services/cloudrun/
            paneles como abstracciones separadas, una sola lista de "targets desplegables" (core,
            audio_server, backoffice, cloud-bo, un panel por NSPanel), cada uno con versión que
            corre + última disponible + un botón "Actualizar" que elige el comando solo
            (deploy.release / deploy.cloud / deploy.satellites). Registro único `TARGETS` en el
            motor, consumido por el snapshot y los dos frontends. wa/bridge quedan en "avanzado".
- [x] 34.16 `deploy.satellites` (force pull de paneles): el panel ya auto-actualiza cada
            MODEL_SYNC_SECS; el comando marca el nodo (`POST /nodes/{id}/update` en audio_server)
            y el próximo heartbeat le devuelve `update:true` → corre `_check_code_update()` fuera
            de ciclo. node_id '*'/'all' → todos. Cierra el botón de deploy por panel en la matriz.
- [ ] 34.17 (FUTURO) Compartimentación física por unidad deployable: extraer `backoffice/`,
            `cloud/` (bo+bridge, acoplados por el contrato `app.commands`) y `wa/` del umbrella a
            submodules propios, cada uno con su línea de versión. NO 1:1 estricto por target:
            cloud-bo+bridge y audio_server+satélite están acoplados por código y van juntos.
            umbrella queda con scripts/masterplan/docs/infra (orquestación, no runtime). Trabajo
            grande y casi irreversible (repos GH nuevos, CI, paths de deploy) → tanda aparte.

#### Etapa D - Tests y documentación
- [x] 34.10 Tests: validación del comando con refs (`cloud/tests`); executor con snapshot /
            health / rollback mockeando git + systemd + HTTP (`cloud/bridge/test_bridge.py`);
            caso e2e del flujo deploy → health falla → rollback al ref previo. + registro de
            versión cloud en el state, consistencia del registro TARGETS, deploy.satellites.
- [x] 34.11 Docs: actualizar `cloud/README.md`, `cloud/bridge/README.md`, la sección de
            deploy de `CLAUDE.md`, `masterplan/arquitectura_funcional.md` (flujo de release y
            rollback) y este plan. Reflejar la nueva versión visible en el dashboard.

### FASE 35 - Observabilidad de voz/LLM + dashboards de métricas

```
Objetivo: Centralizar TODAS las métricas relevantes del análisis de voz (wake word,
          falsos positivos, voice-id, retrains) y de las interacciones con LLMs
          (latencias, tokens, tool calls, coordinador, aciertos/errores), exponerlas en
          un dashboard amigable e interactivo en el backoffice local, y pushearlas al
          backoffice cloud (vía el bridge egress-only de FASE 33) con su propio dashboard.
Estado:   COMPLETA (8/8 — Etapa A instrumentación+API, Etapa B dashboards backoffice+cloud
          + push egress-only, Etapa C tests+docs).
Deps:     FASE 24 (tracing de interacciones — fuente de métricas LLM), FASE 16 (métricas
          de nodos/voz: _bump_metric, estado del retrain), FASE 33 (bridge egress-only +
          cloud backoffice + RBAC), FASE 12 (backoffice local).
```

#### Etapa A - Instrumentación y almacenamiento
- [x] 35.1  Métricas de análisis de voz: serie temporal + agregados de wake detections,
            falsos positivos (por nodo), voice-id (conf, identificado vs guest, aciertos),
            y eventos de retrain (n_positive, n_negative, trigger, duración, versión).
            Reusar lo que ya escriben `audio_server` (`_bump_metric`) y `/wakeword/train`.
            Persistir en SQLite con retención configurable.
            Hecho: `core/metrics_store.py` (tablas voice_metrics/retrain_events, ingesta,
            agregación voice_aggregates/voice_series/retrain_history, retención
            METRICS_RETENTION_DAYS); endpoint `POST /metrics/voice/event`; el ear
            (`audio_server`) emite cada evento fire-and-forget al core (METRICS_PUSH).
            Las funciones de consulta quedan listas para exponerse como API GET en 35.3.
- [x] 35.2  Métricas de interacciones LLM: latencias por modelo/agente, tokens
            (prompt/completion), tool calls, latencia del coordinador, tasa de
            aciertos/errores y fallbacks. Fuente: `trace_store` (FASE 24); derivar agregados
            sin duplicar el almacenamiento de traces.
            Hecho: `metrics_store.record_request_metrics` deriva filas agregables de cada
            RequestTrace a SQLite (tablas llm_calls/agent_steps/request_metrics) sin duplicar
            el trace. Captura de tokens (prompt_eval_count/eval_count) en LLMCall y en los
            sitios principales (coordinator, agent._ask_llm, agent_loop, generic_agent,
            backend_router). Agregadores llm_aggregates/llm_by_model/agent_aggregates/
            request_aggregates/llm_series. server hookea record_request_metrics al cerrar
            el trace. Fix: faltaba el import de metrics_store en server (revertido por un
            checkout concurrente en 35.1) → POST /metrics/voice/event tiraba NameError.
- [x] 35.3  Capa de agregación + API de métricas en `core`: endpoints GET para series
            temporales y agregados (por rango temporal, por nodo, por agente/modelo), con
            shape listo para graficar (labels + series).
            Hecho: GET /metrics/voice/{summary,series,retrains} y
            /metrics/llm/{summary,by-model,by-agent,series}. Rango por since/until/hours,
            filtros model/agent_id/node_id; series con shape {labels, series}. Tests:
            test_metrics_api (9). Quedan listos para los dashboards 35.4 (backoffice) y 35.6 (cloud).

#### Etapa B - Dashboards
- [x] 35.4  Dashboard de métricas en el backoffice local: páginas amigables e interactivas
            (gráficos de línea/barras, filtros por rango/nodo/agente, auto-refresh).
            Secciones separadas: Voz/Wake/Voice-id/Retrain y LLM/Agentes/Latencias.
            Hecho: página `/metrics` (Chart.js) con tabs Voz/LLM, filtros (rango/nodo/agente),
            auto-refresh y tarjetas+gráficos+tablas. Proxy `/api/metrics/{path}` en el
            backoffice reenvía a la API del core (mismo origen, autenticado). Nav "Métricas".
- [x] 35.5  Push de métricas al cloud: extender el bridge (FASE 33, egress-only) para enviar
            agregados de métricas al backoffice cloud; contrato + rate limiting + auth.
            Hecho: `cloud/bridge/metrics_snapshot.py` arma los agregados desde la API del core
            (resiliente); `cloud_bridge.push_metrics` los empuja a `POST /ingest/metrics` cada
            METRICS_PUSH_INTERVAL (300s). Cloud: modelo `MetricsSnapshot`, `store_metrics`/
            `get_metrics` en Firestore (TTL), endpoint con auth de bridge (OIDC) + rate limit.
- [x] 35.6  Dashboard de métricas en el cloud backoffice: mismas vistas amigables e
            interactivas, con el RBAC de FASE 33 (admin ve todo; roles limitados, vista básica).
            Hecho: sección Métricas en `cloud/app/templates/dashboard.html` (Chart.js),
            `GET /api/metrics` con `rbac.filter_metrics` (sin view_full → sólo resúmenes y
            series, sin detalle por modelo/agente ni reentrenamientos).

#### Etapa C - Tests y documentación
- [x] 35.7  Tests: agregadores de métricas (voz y LLM) con datos sintéticos; endpoints de
            métricas; contrato del push al cloud mockeando el bridge.
            Hecho: core `test_metrics_store` (agregadores voz+LLM, datos sintéticos) y
            `test_metrics_api` (endpoints GET del core). Cloud `test_metrics_api` (endpoints
            /ingest/metrics y /api/metrics con TestClient, auth override + Firestore mockeado,
            RBAC) y `test_metrics_contract` (modelo + RBAC + el snapshot del bridge valida
            como MetricsSnapshot). Bridge: `metrics_snapshot` resiliente.
- [x] 35.8  Docs: actualizar `README.md`, `masterplan/arquitectura_funcional.md` (sección de
            observabilidad/métricas) y la política de dashboards de `CLAUDE.md`.
            Hecho: README sección "Observability"; arquitectura_funcional sección
            "Observabilidad — métricas"; CLAUDE.md política de métricas persistidas + dashboards web.

### FASE 36 - Continuidad conversacional unificada (voz + WhatsApp)

```
Objetivo: Una capa de conversación como COLUMNA VERTEBRAL de la continuidad, channel-aware,
          en vez de parches por canal. Debe: (a) sostener intercambios multi-turno sin
          re-disparar (wake word en voz, mensaje nuevo en WA); (b) integrar las notificaciones
          proactivas como turnos de conversación, para que la respuesta del usuario caiga en
          contexto y rutee al agente dueño; (c) identificar al usuario una vez por sesión
          (no por conversación); (d) dar a cada agente un contexto consistente (user_context
          por-agente + historial reciente). Reemplaza y expande el épico 18.16 (#532).
Estado:   EN CURSO (5/11 — Etapa A completa: 36.1, 36.2, 36.3; Etapa B: 36.4, 36.5 listas,
          falta 36.6 deploy+e2e contra NSPanel físico).
Deps:     conversations.py (FASE 9/22), intent_state + proactivo (FASE 22/27), 19.4 (ruteo WA
          por intent_id — base del frente proactivo), FASE 16 (audio_server/satellite), FASE 35
          (métricas, para 36.10).

Modelo conceptual (decisiones de diseño):
  - Conversation channel-aware: TTL y semántica por canal (voz: corta/síncrona ~120s; WA:
    larga/asíncrona, persistente). El source_key sigue identificando el hilo; se agrega
    política de reanudación por recencia.
  - ContinuationState unificado: needs_reply / is_clarification / pending_field dejan de ser
    flags sueltos y se modelan como UN estado de "esperando respuesta" persistido en la
    conversación, devuelto en /process y wa_inbound, y consumible por cualquier canal.
  - Proactivos = turnos `assistant` en una conversación, atados a su intent_id. El reply
    (quoted o por recencia) se liga a esa conversación → agente dueño (extiende 19.4).
  - Identidad: greeted_at por usuario/canal; saludo 1x por sesión señalando reconocimiento.
  - Contexto a agentes: contrato uniforme (user_context por-agente + conv.context()),
    auditado y testeado por agente (no asumido).
```

#### Etapa A - Fundaciones del modelo de conversación (core)
- [x] 36.1  `Conversation` channel-aware: TTL configurable por canal (voz ~120s, WA largo/
            persistente) + política de reanudación por recencia (`resume_latest(source)`).
            Refactor de `conversations.py` sin romper el keying actual. Tests. (PR core #207;
            limpió STORE_PATH/json muertos)
- [x] 36.2  `ContinuationState` unificado: modela needs_reply/is_clarification/pending_field
            como un estado de "esperando respuesta" persistido en la conversación (waiting/kind/
            prompt/field/agent_id); pending_field pasa a propiedad respaldada; los flags legacy
            se derivan; las respuestas exponen `continuation`. Migración del pending_field legacy.
            PR core #208. (wa_inbound expone continuation: pendiente afinar en 36.7/36.8)
- [x] 36.3  Contexto uniforme a agentes. BUG corregido: el server inyectaba user_context solo
            dentro de `if prefix:` → agentes sin prefix no lo recibían; ahora SIEMPRE (ambos
            paths). conv.context() ya lo usan todos. Accessor `base_agent.user_context_from` +
            contrato documentado. PR core #209. (clima/finance ya cumplían)

#### Etapa B - Continuidad en paneles/voz (core + ear)
- [x] 36.4  `audio_server`: `/process-audio` devuelve metadata de continuación (headers
            `X-Conversation-Id`, `X-Needs-Reply`) y propaga `conversation_id` al core en cada
            request (antes se descartaba). `_call_core` → (response, agent_id, conversation_id,
            needs_reply). PR ear #43. Tests.
- [x] 36.5  `satellite`: ante `needs_reply`, reabre el mic SIN wake word (beep + grabación),
            threadeando el `conversation_id`; cierra el ciclo si no hay respuesta a tiempo
            (silencio) o se alcanza `FOLLOWUP_MAX`. Turno extraído a `_run_turn`. PR ear #44.
            Tests del loop con `sounddevice`/audio_server mockeados.
- [ ] 36.6  Deploy a paneles + verificación e2e: wake → comando → repregunta → respuesta sin
            re-wake; sin regresiones de falsos positivos.

#### Etapa C - Continuidad en WhatsApp (core)
- [ ] 36.7  Conversación activa en WA: TTL largo; un mensaje entrante reanuda la última
            conversación activa del remitente si existe (no crea una nueva por gap temporal).
            Tests.
- [ ] 36.8  Proactivos como turnos: las notificaciones proactivas (advise/goal/request)
            registran un turno `assistant` en una conversación con su `intent_id`; el reply
            (quoted-reply o por recencia) se liga a esa conversación y rutea al agente dueño
            (extiende 19.4). Tests del cruce resuelto end-to-end.

#### Etapa D - Identidad y saludo (core)
- [ ] 36.9  Saludo por sesión: `greeted_at` por usuario/canal; saludar 1x por sesión
            señalando reconocimiento del usuario (no en cada conversación nueva). Cooldown
            configurable. Reemplaza el saludo por-conversación actual. Tests.

#### Etapa E - Observabilidad y documentación
- [ ] 36.10 Métricas de continuidad (turnos por conversación, % de exchanges multi-turno,
            repreguntas sostenidas, replies a proactivos) integradas a los dashboards de FASE 35.
- [ ] 36.11 Tests e2e cross-canal (voz y WA) del ciclo completo + docs: sección "continuidad
            conversacional" en `masterplan/arquitectura_funcional.md` y `README`.

### FASE 37 - Backoffice cloud completo (paridad de secciones egress-only + sidebar)

```
Objetivo: Llevar el backoffice cloud (FASE 33) de una única página SPA con tarjetas
          apiladas a un backoffice con sidebar + secciones, con paridad funcional con el
          backoffice local en TODO lo que tiene sentido exponer egress-only. Además,
          reemplazar el mecanismo genérico de comandos (dropdown de tipo + input JSON que
          respeta un schema) por una interfaz de comandos lograda: acciones contextuales
          por entidad y formularios tipados con widgets propios. PREMISA TRANSVERSAL:
          el backoffice cloud debe ser mobile-friendly (responsive, mobile-first), ya que
          el acceso remoto egress-only es típicamente desde el celular — toda sección,
          sidebar y formulario de comandos debe funcionar y ser usable en pantalla chica.
Estado:   COMPLETA (13/13). Pendiente sólo el deploy/verificación e2e en hardware (satélite/ssh).
Deps:     FASE 33 (backoffice cloud + bridge egress-only + RBAC — COMPLETA, base a extender),
          FASE 35 (dashboards de métricas — COMPLETA, ya viven en el cloud),
          FASE 34 (deploy remoto — la sección Deploy del sidebar consume su versión reportada).
Principio de seguridad: se hereda intacto el modelo egress-only de FASE 33. El Brain sólo
          hace conexiones SALIENTES. Toda sección nueva se alimenta por snapshot-push
          (cloud/bridge/snapshot.py → POST /ingest/state) o por comando-poll (allowlist
          tipado de cloud/app/commands.py). Cero inbound. Nunca salen de la LAN: .env,
          tokens HAOS/OAuth, ni contenido de conversaciones en claro.
Reglas que gobiernan qué entra al cloud (ambas deben cumplirse por sección):
          (1) Seguridad/PII: el dato puede salir sin exponer secretos ni contenido sensible.
          (2) Egress-only: el dato se alimenta por snapshot-push o comando-poll.
Decisiones tomadas:
          - Superficie de control: agregar comandos de operación ACOTADOS al allowlist
            (agent.toggle, panel.reboot, proactive.run), sólo admin, validados como los
            existentes. No shell arbitrario.
          - PII: secciones sensibles se muestran como resumen/conteos para todos; el detalle
            (contenido) queda detrás de una capacidad RBAC admin-only NUEVA (view_pii),
            distinta de view_full.
          - Frontend: SPA único (no multipágina Jinja como el local), una sola Firebase auth
            flow, sidebar con la taxonomía del local (Monitoreo/Sistema/Administración) y
            router client-side por hash; cada link y vista gated por capacidad. Mobile-first:
            layout responsive, sidebar colapsable/drawer en pantalla chica, tablas y charts
            que se reflowan, targets táctiles adecuados. Es requisito de aceptación, no un
            extra — el acceso remoto se da mayormente desde el celular.
          - Comandos: NO más select-de-tipo + input JSON genérico. Acciones contextuales
            junto a la entidad (restart por servicio, toggle por agente, reboot por panel,
            retrain en Wake word, reload por target, run por agente) y, para comandos sin
            entidad-ancla, formularios tipados con widgets renderizados desde la metadata
            de presentación de /api/catalog (enum→dropdown, int→número min/max, bool→toggle,
            node/user→selector). Confirmación en acciones destructivas + feedback inline del
            estado (pending→running→done/error) reusando la auditoría.
Mapa de paridad local→cloud (qué se incluye y bajo qué gate):
          - Inicio        → Resumen (landing nuevo; access)
          - Dashboard     → Servicios/Agentes/Actividad (ya existe, se reorganiza; access)
          - Métricas      → Métricas (ya existe; detalle view_full)
          - Estadísticas  → se funde en Métricas/Resumen
          - Alertas       → Alertas (nuevo; campo snapshot 'alerts'; access)
          - Logs          → Logs (nuevo; comando logs.tail; emit)
          - Traces        → resumen agregado en Métricas; detalle view_pii
          - Agentes       → Agentes (lista ya existe + toggle vía agent.toggle; emit)
          - Intenc/Goals/Rutinas → conteos en Resumen; detalle view_pii
          - Conversaciones→ conteos; sin contenido (detalle view_pii)
          - Usuarios      → roster read-only (ya viaja en users_summary; view_full)
          - Wake word     → estado + retrain (wakeword.retrain; emit)
          - Paneles       → estado + reboot (panel.reboot; emit)
          - Deploy        → versión desplegada (FASE 34; emit admin)
          - Config (.env) → sólo acción config.reload (sin editor de .env)
          - FUERA del cloud: Shared State, Ambientes (rooms), Integraciones (OAuth/tokens).
```

PREMISA TRANSVERSAL DE UX (comandos): TODO lo relativo a comandos invocables —
          catálogo, observabilidad del estado (pending→running→done/error), y la UX de
          definición de parámetros— debe construirse con calidad de producto final-user,
          aunque el ítem no lo detalle explícitamente. Nada de inputs JSON crudos ni jerga
          interna: widgets tipados, labels claros, validación inline, feedback legible.
          Aplica especialmente a 37.5/37.6 pero gobierna toda superficie de comandos.

#### Etapa A - Contrato y RBAC
- [x] 37.1  Contrato del snapshot ampliado: campos `alerts`, `wakeword.status`, conteos de
            intents/goals/routines/conversaciones y versión desplegada (cruza FASE 34).
            Documentar qué sale y qué NO (sin contenido PII en claro). Tests de contrato del
            snapshot (`cloud/tests`).
- [x] 37.2  Capacidad `view_pii` (admin-only) en `cloud/app/rbac.py`, distinta de `view_full`;
            `filter_state` redacta el detalle PII según ella (deja conteos). Catálogo de comandos
            extendido en `cloud/app/commands.py` (`agent.toggle`, `panel.reboot`, `proactive.run`)
            con validadores existentes. Tests de RBAC y de catálogo.

#### Etapa B - Frontend reestructurado (sidebar + secciones)
- [x] 37.3  Base SPA con sidebar (Monitoreo/Sistema/Administración), router por hash y links
            gated por caps (`access`/`view_full`/`view_pii`/`emit`); el sidebar oculta lo no
            permitido y el router rechaza navegación a vistas sin capacidad.
- [x] 37.4  Secciones: Resumen, Servicios, Métricas, Alertas, Logs, Agentes, Actividad, Wake
            word, Paneles, Usuarios, Deploy, Auditoría. Cada vista gated por capacidad.
            (Logs queda como placeholder gated hasta el endpoint de 37.6.)
- [x] 37.5  Interfaz de comandos contextual (reemplaza el `<select>` + input JSON): acciones
            por entidad (restart/toggle/reboot/retrain/reload/run) con widgets propios,
            confirmación en destructivas y feedback inline del estado; formularios tipados para
            comandos sin entidad-ancla (ej. logs.tail), renderizados desde la metadata de
            presentación de `/api/catalog`. Elimina `#cmd-params` JSON.
- [x] 37.12 Mobile-friendly: el SPA (sidebar, secciones y formularios de comandos) debe ser
            responsive/mobile-first. Sidebar colapsable a drawer en viewport chico, tablas y
            charts (Chart.js) que se reflowan sin scroll horizontal, targets táctiles
            adecuados, sin layout roto en portrait. Verificar las vistas clave en ancho de
            celular. Premisa transversal de la fase, no una sección aparte.
            (Drawer+scrim y reflow ya en 37.3; acá: tablas anchas scrollean dentro de su card,
            targets táctiles más grandes. Verificación visual en navegador queda al desplegar.)

#### Etapa C - Backend cloud
- [x] 37.6  Endpoints `/api/alerts` y `/api/logs` (poll del resultado de `logs.tail`); ampliar
            `/api/me`/`/api/state` con las caps nuevas y `/api/catalog` con la metadata de
            presentación por parámetro (`kind`/`label`/`choices`/`min`/`max`/`default`) sin
            cambiar `validate_command`. RBAC aplicado por endpoint.

#### Etapa D - Bridge / executor (Brain)
- [x] 37.7  `cloud/bridge/snapshot.py`: emitir los campos nuevos reusando datos que ya computan
            core/backoffice (sin PII en claro; sólo conteos). No reimplementar lógica.
            (Alertas vía `/alerts/recent` no-consumible —core—, no `/alerts` que drena el TTS.)
- [x] 37.8  `cloud/bridge/executor.py`: implementar `agent.toggle`, `panel.reboot`,
            `proactive.run` (tipo→función concreta, sin eval; auditoría como los existentes),
            invocando las APIs/scripts del Brain ya existentes.

#### Etapa F - Logs del satélite por panel (ambos backoffices)
- [x] 37.10 Ver los logs del satélite de CADA panel en LOS DOS backoffices (local LAN + cloud
            egress-only). El log vive en el panel (`~/.satellite.log` en Termux). Mecanismo único
            reutilizable "traer N líneas del satélite del panel X" (ssh a Termux:8022 desde el
            Brain, o relay vía `audio_server`), invocado por: (a) backoffice local con selector de
            panel en `/logs` (fetch directo, está en la LAN), y (b) cloud vía comando tipado
            (extender `logs.tail` con `node_id` opcional, o `logs.satellite`) → bridge ejecuta el
            fetch → resultado al panel Logs (37.4/37.6). Sin duplicar la lógica de fetch entre
            local y bridge. Tests con ssh mockeado.

#### Etapa E - Tests y documentación
- [x] 37.9  Tests cloud (`cloud/tests`) + bridge (`cloud/bridge/test_bridge.py`) de todo lo
            nuevo; docs en `masterplan/arquitectura_funcional.md`, `cloud/README.md` y `README`;
            lint de estado + sync de issues. (Suites: cloud 143, core 734, ear 106.)

#### Etapa G - Observabilidad de detección: score WW + voice-id en el tiempo (ambos backoffices)
- [x] 37.11 Visualizar el comportamiento del SCORE de wake word vs el threshold a lo largo del
            tiempo, en la sección Métricas de AMBOS backoffices (local LAN + cloud egress-only).
            El score hoy sólo vive en stdout del satélite (`ear/satellite.py:_score_chunk`,
            logea >= `SCORE_LOG_MIN`, dispara >= `WAKEWORD_THRESH`) — NO se persiste. Pipeline
            nuevo: el satélite reporta los frames scoreados (granularidad near-misses + picos:
            todos los frames con `score >= SCORE_LOG_MIN`, incluidos los que NO dispararon) con
            el `threshold` vigente y el `rms` → relay por `audio_server` → core (endpoint nuevo
            tipo `POST /metrics/wakeword/score`) → `metrics_store` (tabla nueva `ww_scores`:
            ts, node_id, score, threshold, fired, rms; con `prune` por `METRICS_RETENTION_DAYS`)
            → `GET /metrics/wakeword/series` → chart en `backoffice/templates/metrics.html` y la
            sección cloud `cloud/app/templates/dashboard.html` (Chart.js, view_full): serie de
            score con la línea de threshold superpuesta, para ver el margen y los casi-disparos.
            Egress-only: viaja por el push de métricas existente (`cloud/bridge/metrics_snapshot.py`
            → `POST /ingest/metrics`), sin inbound. Tests de ingesta/serie/prune y del relay con
            HTTP mockeado.
- [x] 37.12 Visualizar el comportamiento del VOICE-ID (`speaker_conf`) vs `SPEAKER_THRESHOLD` a lo
            largo del tiempo, en Métricas de ambos backoffices. El dato YA se persiste por evento
            en `voice_metrics.speaker_conf` (lo empuja `audio_server` en cada tp/fp); falta (a)
            exponer el `SPEAKER_THRESHOLD` vigente (no se guarda con el evento — sumarlo al evento
            o al summary), y (b) una serie de `speaker_conf` (hoy `voice_series()` sólo devuelve
            conteos tp/fp): agregar la consulta (puntos por evento o promedio/percentil por bucket)
            + endpoint, y el chart en local+cloud con `speaker_conf` vs la línea de threshold,
            distinguiendo known vs guest. Reusa el dato existente, sin nuevo pipeline de ingesta.
            Tests de la serie nueva y del threshold expuesto.

### FASE 38 - Configuración por panel (administrable desde ambos backoffices)

```
Objetivo: Dar a cada panel NSPanel una sección de CONFIGURACIÓN administrable desde el backoffice
          local (LAN) y el cloud (egress-only), 100% funcional. Empieza con dos parámetros y deja
          lugar para más:
            1. Tiempo de inactividad para apagar la pantalla (screen_timeout_secs, 0 = nunca).
            2. Dashboard por defecto del panel (default_dashboard, deeplink de HA Companion).
Estado:   COMPLETA (7/7). Pendiente sólo la verificación e2e en hardware (satélite/su/am).
Deps:     FASE 16 (paneles + audio_server + heartbeat/auto-update), FASE 33/37 (cloud + comandos
          tipados + snapshot egress-only), FASE 32 (tabla panels en SQLite).
Decisiones tomadas:
          - Pantalla: apagado NATIVO de Android (settings put system screen_off_timeout), no
            atenuación por brillo. Un solo parámetro en segundos.
          - Dashboard: dropdown poblado desde los dashboards reales de HA (lovelace, vía WebSocket
            lovelace/dashboards/list); se guarda el deeplink completo que abre la Companion.
          - Persistencia: columna `config` JSON en la tabla panels (no columnas tipadas) → se
            agregan claves nuevas sin migración. Fuente de verdad en core.
          - Aplicación: el SATÉLITE hace PULL de su config (mirror del auto-update de código) y la
            aplica en caliente. Único aplicador del dashboard (no toca start-ha.sh → no pelea con
            nspanel.sh converge). Egress-only: cero inbound; el flag /config-changed sólo da
            inmediatez (converge igual en el ciclo de sync y al arrancar).
```

- [x] 38.1  core: columna `panels.config` (migración idempotente `_ensure_column`) + round-trip y
            validación (merge parcial, allow-list) en `/panels`; `GET /panels/config/{node_id}`;
            `ha_client.list_dashboards()` por WebSocket (`lovelace/dashboards/list`, + Overview,
            cache) y `GET /dashboards`; dep `websocket-client`. Tests (`test_panels_api`,
            `test_ha_client` con WS mockeado).
- [x] 38.2  ear/audio_server: `GET /nodes/{id}/config` (proxy de core + versión md5),
            `POST /nodes/{id}/config-changed` (flag de inmediatez, mirror de `/update`),
            `config_update` en el heartbeat. Tests.
- [x] 38.3  ear/satellite: `_check_config_update` (PULL, mirror de `_check_code_update`; al
            arrancar + en el loop + on-flag por heartbeat) y `_apply_remote_config`
            (`screen_off_timeout` vía `su` + dashboard vía `am start -d`). Tests con subprocess/HTTP
            mockeados.
- [x] 38.4  backoffice local: `POST /panels/{name}/config` (upsert en core + flag a audio_server)
            + selector de dashboards (`/dashboards`) y form de config por panel en `panels.html`.
- [x] 38.5  cloud: comando `panel.config` (CATALOG/PRESENTATION con kind `dashboard`) + executor
            `_panel_config` (upsert core + flag audio_server) + snapshot (config por panel +
            `dashboards`) + UI contextual "configurar" por panel en `dashboard.html`. Tests
            (`test_commands`, `test_bridge`).
- [x] 38.6  Docs: `arquitectura_funcional.md` (config de paneles + flujo pull), READMEs (raíz,
            core, ear, cloud); lint de estado + sync de issues.
- [x] 38.7  Prefill con la config REAL del dispositivo: el satélite lee el `screen_off_timeout`
            vigente (`settings get`) y reporta su config aplicada en el heartbeat
            (`dev_screen_timeout_secs`/`dev_dashboard`); `audio_server` la expone en `/nodes`
            (`device_config`) y la lleva el snapshot; ambos backoffices prellenan el form con el
            estado del dispositivo (fallback a la config guardada en core). Tests.

### FASE 39 - Mensajería P2P entre usuarios mediada por agente (multi-canal, por turnos)

```
Objetivo: Permitir que dos usuarios CONOCIDos mantengan una conversación por TURNOS que
          atraviese canales: de un panel a otro, de WhatsApp a un panel y de un panel a
          WhatsApp. El intercambio lo media un agente nuevo que el orquestador rutea como a
          cualquier otro dominio. Ejemplos: "decile a Lucía que ya salgo", "respondele a papá",
          "mandale al panel de la cocina que baje a cenar", "avisale a mamá por WhatsApp".
Estado:   Pendiente.
Deps:     FASE 9  (coordinador LLM — routing agnóstico por catálogo de AgentCards),
          FASE 22 (intents tipados — request/continuation reusados para turnos diferidos),
          FASE 36 (continuidad conversacional unificada — ContinuationState, multiturno voz/WA),
          FASE 3.5/19 (canal WhatsApp inbound `/wa/inbound` + push `wa_notifier.notify`),
          FASE 2.5 (usuarios — identidades por canal: wa_phone, voice_id, panel_id),
          FASE 32 (doc store SQLite — persistencia de la sesión P2P).
PRINCIPIO RECTOR (no-bias, transversal): ningún caso de uso debe sesgar a un agente
          particular. El relay P2P se modela como UN AGENTE MÁS (`messenger`) con su AgentCard
          + ejemplos; el coordinador LLM decide rutear "decile a X…" / "respondele a Y…" por
          planeación, igual que cualquier dominio. Queda PROHIBIDO agregar lógica de mensajería
          al coordinador. El relay del turno de vuelta tampoco se hardcodea: la conversación del
          receptor queda en `ContinuationState.waiting` (owner=messenger) y la continuación
          GENÉRICA enruta la respuesta al agente dueño — el mismo mecanismo de clarification/field.
Decisiones tomadas:
          - Agente NUEVO `messenger` (no extender profile/user_mgmt): registrado en REGISTRY con
            AgentCard + examples; el fast_classifier lo aprende de sus ejemplos. Cero hardcode en
            coordinator.py.
          - Entrega: STORE-AND-FORWARD async. El mensaje queda PENDIENTE hasta que el destinatario
            sea alcanzable o interactúe; los turnos alternan en el tiempo (no requiere ambos
            presentes). Reusa la máquina de intents/continuation, no un canal nuevo en vivo.
          - Turnos ESTRICTOS: la sesión P2P lleva `turn_owner`; un mensaje fuera de turno se
            encola/avisa, no pisa el turno del otro.
          - Ruteo a destino: AUTO con fallback. El LLM extrae destinatario (+ hint opcional de
            canal); el sistema resuelve panel asignado/último activo → fallback wa_phone; si no
            hay canal alcanzable, avisa al emisor (no se pierde el mensaje, queda pendiente).
          - Privacidad: HOGAR ABIERTO. Cualquier usuario conocido puede mensajear a otro; guest/
            invitado NUNCA emite ni recibe. El destinatario puede mute/DND y bloquear emisores.
          - Identidad: resolución nombre→user sobre el roster (alias/fuzzy); ambigüedad dispara
            CLARIFICATION del coordinador ("¿a qué Lucía?"), reusando needs_clarification.
          - GAP de infra que se construye: entrega DIRIGIDA a un panel concreto. Hoy los paneles
            no tienen push proactivo dirigido (sólo respuesta síncrona, `alert_queue` GLOBAL y
            flags en heartbeat). Se agrega un BUZÓN DE SALIDA POR-NODO que el satélite drena y
            anuncia por TTS. WhatsApp reusa `wa_notifier.notify(phone, text)`.
```

PREMISA DE DASHBOARD (CLAUDE.md): la feature introduce datos nuevos (sesiones P2P, mensajes
          relayados, latencia de entrega por canal). Reflejarlo en observabilidad persistida
          (`metrics_store`) y en `/metrics` de ambos backoffices + panel zellij — se cubre en 39.8.
          Egress-only: sólo conteos, sin contenido de mensajes en claro hacia la nube.

#### Etapa A - Modelo de sesión + agente messenger
- [ ] 39.1  Modelo de sesión P2P persistido (`core/p2p_session.py`, doc store SQLite FASE 32):
            participantes (from_user/to_user), `turn_owner`, `status`
            (open/awaiting_sender/awaiting_recipient/closed/declined), binding de canal por
            participante, log de turnos (texto + canal + ts) y TTL. CRUD + tests del ciclo de
            vida y de la alternancia estricta de turnos (mensaje fuera de turno se encola, no pisa).
- [ ] 39.2  Agente `messenger` (`core/messenger_agent.py`) implementando `BaseAgent.process`:
            extrae destinatario + cuerpo del query reformulado por el coordinador, resuelve el
            user destino, crea/continúa la sesión P2P y encola la entrega. Registrado en REGISTRY
            con AgentCard + examples ("decile a X que…", "respondele a Y", "avisale a mamá por
            WhatsApp", "mandale al panel de la cocina…"). Retorna `intent_updates`/continuation
            para esperar el turno. Tests del process mockeando entrega y resolución de usuario.
- [ ] 39.3  Resolución destinatario nombre→user (alias/fuzzy sobre el roster), exclusión de
            guest/invitado, y disparo de CLARIFICATION ante ambigüedad reusando el
            `needs_clarification` del coordinador (sin lógica nueva en coordinator.py). Tests.

#### Etapa B - Capa de entrega dirigida (multi-canal)
- [ ] 39.4  Abstracción `deliver(user, text, session)` que elige canal por binding/presencia:
            panel asignado (`panel_id`) / último panel activo → fallback `wa_phone`; si no hay
            canal, marca no-entregable y avisa al emisor (queda pendiente). Selección y fallback
            testeados.
- [ ] 39.5  Buzón de salida POR-NODO para paneles (NUEVO; cubre el gap de push dirigido): cola
            por `node_id` en core/audio_server; el satélite la drena (heartbeat node-scoped o
            `GET /nodes/{id}/outbox`) y la anuncia por TTS con marca de quién envía. La entrega
            WhatsApp reusa `wa_notifier.notify`. Tests de encolado/drenado con HTTP mockeado.
- [ ] 39.6  Relay del turno de vuelta: cuando el receptor responde (voz panel o WA), su
            `ContinuationState` (owner=messenger) enruta la respuesta al messenger vía la
            continuación GENÉRICA; el messenger la entrega al otro participante y alterna el turno.
            Resuelve el cross-user (la captura por intent es hoy por-usuario) dentro de la sesión
            P2P. Tests del relay bidireccional y de la alternancia de turnos.

#### Etapa C - Privacidad y control
- [ ] 39.7  Mute/DND y bloqueo por usuario: preferencias en `User` (ventana DND, emisores
            muted/blocked); `deliver()` respeta DND (encola hasta el fin de la ventana) y descarta
            de emisores bloqueados avisando al emisor. Guest nunca emite ni recibe. Tests de
            gating.

#### Etapa D - Observabilidad y documentación
- [ ] 39.8  Métricas: persistir en `metrics_store` los eventos de relay (enviados/entregados/
            pendientes/fallidos por canal + latencia de entrega). Panel zellij (nuevo o extender
            history/agents) + sección en `/metrics` de ambos backoffices (sólo conteos; egress-only
            por el push de métricas existente, sin contenido en claro). Tests de ingesta/serie.
- [ ] 39.9  Documentación: `README.md` (core + raíz) y `masterplan/arquitectura_funcional.md`
            (agente `messenger`, sesión P2P, capa de entrega dirigida, buzón por-nodo). Conteo de
            sesiones P2P en el Resumen del backoffice cloud (detalle de contenido sólo bajo
            `view_pii`).

### FASE 40 - Auditoría del flujo de ejecución + orquestación 100% agnóstica (sin bias de agente)

```
Objetivo: Garantizar que la elección de agente sea SIEMPRE producto de la planeación del LLM
          sobre (prompt del usuario + AgentCards disponibles). Erradicar los cortocircuitos
          deterministas pre-coordinador que condicionan o secuestran el routing. Corregir el bug
          observado: un `request` intent pendiente (típicamente un proactivo de finanzas, creado
          SIN `conversation_id`) captura cualquier enunciado siguiente como su respuesta y
          devuelve "Entendido, el plan 'X' queda sin cambios" ante, p.ej., una consulta de clima.
Estado:   COMPLETA (panel zellij de 40.6 N/A — los paneles ear ya no existen, FASE 21).
Deps:     FASE 9  (coordinador LLM — el corazón agnóstico a preservar),
          FASE 22 (intents tipados + captura 22.5 — el path a corregir),
          FASE 36 (ContinuationState — el mecanismo CORRECTO de espera de respuesta),
          FASE 24 (tracing — para evidenciar y medir los bypasses).
PRINCIPIO RECTOR: el corazón es 100% agnóstico — el LLM arma el plan desde (prompt + AgentCards)
          y de ahí surge, orgánico y eventual, el uso de un agente. PROHIBIDO bias hacia un agente
          o lógica determinista que condicione qué agente atiende. Los únicos cortes admisibles
          antes del LLM son housekeeping de canal verdaderamente agnóstico (cierre/ack) y NO deben
          decidir agente. La pregunta "¿este enunciado es respuesta a algo pendiente o un comando
          nuevo?" debe resolverse de forma agnóstica (idealmente por el propio planner), nunca por
          precedencia dura.
Hallazgos de la auditoría inicial (ya realizada — base de esta fase):
          - 4 cortocircuitos antes del coordinador en `server.py:process`: (3) `is_close_phrase`,
            (3b) `is_acknowledgment`, (3c) `get_pending_request`→`handle_captured_reply`
            (server.py:615-632), (4) `fast_classifier` dentro de `coordinate()`. El 3c rompe el
            principio.
          - Causa raíz: `get_pending_request` (intent_state.py:231-233) matchea CUALQUIER
            conversación cuando el intent no tiene `conversation_id`; los proactivos de finanzas
            (finance_agent.py:485-498) se crean SIN `conversation_id` → hijack cross-canal. En
            server.py:617 se captura el texto como respuesta sin verificar si realmente es una
            respuesta ni si la conversación está esperando. `_is_affirmative` False → finance_agent.py:521.
          - El path WhatsApp (server.py:933-946) prefiere `intent_id` explícito (quoted-reply) pero
            cae al mismo `get_pending_request` como fallback.
```

#### Etapa A - Auditoría documentada
- [x] 40.1  Documentar en `arquitectura_funcional.md` el flujo real de ejecución de un comando
            (voz y WhatsApp) end-to-end, enumerando TODOS los puntos donde se elige o se puentea el
            agente (los 4 cortocircuitos + fast_classifier + aggregation) con file:line, y marcando
            cada uno como agnóstico / no-agnóstico contra el principio rector.

#### Etapa B - Fix del secuestro de captura
- [x] 40.2  Corregir el hijack: la captura de un request pendiente (server.py 3c) sólo procede
            cuando la conversación está EFECTIVAMENTE esperando esa respuesta — acoplar a
            `ContinuationState.waiting` (FASE 36) con match estricto de `conversation_id`; nunca
            capturar contra un intent sin `conversation_id` en otra conversación. Test de regresión:
            con un request proactivo pendiente, "¿cómo está el clima?" debe ir al planner y rutear
            a weather, NO a finance.
- [x] 40.3  Los `request` intents proactivos deben sellar el `conversation_id` del canal/turno
            donde se ENTREGAN (no nacer sin él): al entregarse por WhatsApp (`wa_notifier`) o al
            inyectarse en un turno de voz, fijar el `conversation_id` en ese momento.
            `get_pending_request` deja de matchear "cualquier conversación" salvo intención
            explícita. Tests.

#### Etapa C - Decisión agnóstica respuesta-vs-comando
- [x] 40.4  Hacer agnóstica la decisión "¿respuesta a lo pendiente o comando nuevo?": pasar la
            pregunta pendiente como CONTEXTO al coordinador y dejar que el plan resuelva el destino
            (incluida la opción "es la respuesta al intent X" como un resultado más del planner),
            en vez de precedencia dura pre-LLM. Conservar a lo sumo un fast-path barato para
            respuestas inequívocas (sí/no a una pregunta yes/no) sin sesgar el resto. Tests de
            ambos caminos.

#### Etapa D - Auditar los demás cortocircuitos
- [x] 40.5  Revisar 3 (close), 3b (ack) y 4 (fast_classifier) contra el principio: que ninguno
            DECIDA agente de forma sesgada. Acotar `is_close_phrase`/`is_acknowledgment` a
            housekeeping puro (no dispararse sobre comandos reales — falsos positivos).
            fast_classifier: confirmar que su bypass es agnóstico (entrenado de ejemplos, gateado
            por ausencia de contexto) y agregar guard de umbral/ambigüedad. Tests de falsos positivos.

#### Etapa E - Observabilidad de bypass
- [x] 40.6  Instrumentar cada bypass: registrar en el trace (FASE 24) cuándo una request NO pasó
            por el planner y por qué cortocircuito (close/ack/capture/fast_classifier). Métrica de
            tasa de bypass por tipo en `/metrics` (ambos backoffices) + panel zellij, para detectar
            regresiones de bias. Tests de ingesta.
            (panel zellij N/A: `ear/dashboard.kdl` y `panel_*.py` ya no existen — pipeline laptop
            reemplazado en FASE 21; la observabilidad persistida vive en los `/metrics` web.)

### FASE 41 - Runtime de agentes recursivo (extensión de FASE 40)

```
Objetivo: Eliminar TODA heurística determinista pre-planner y unificar el sistema bajo UNA sola
          abstracción de agente recursiva: cada agente ES un orquestador. Su process() (1) pide un
          plan al LLM en un loop LLM↔tools con su contexto (prompt + user_context + cards de agentes
          afines + specs de tools); (2) ejecuta cada delegación a un sub-agente como la tool
          `call_agent`, recursivamente y en paralelo cuando son independientes; (3) consolida en el
          turno final del loop. El housekeeping (cerrar/ignorar/capturar/clarificar) son TOOLS del
          agente raíz: que "chau" cierre la conversación es decisión orgánica del LLM, no una keyword.
          Sin fast_classifier, sin cortocircuitos. El usuario recibe una respuesta consolidada
          construida por un árbol de agentes orquestados.
Estado:   COMPLETA (flip del flag postergado — pendiente de decisión por latencia; ver 41.10).
Deps:     FASE 40 (orquestación agnóstica — esta fase erradica los cortes que 40 sólo acotó),
          FASE 9  (coordinador/aggregate — referencia del prompt de consolidación),
          agent_loop.run_loop (núcleo del loop LLM↔tools a generalizar),
          tool_store/tool_hydrator (specs de tools), agent_config afinidades (sub-agentes).
DECISIÓN: big-bang — se migran TAMBIÉN todos los agentes de dominio a la interfaz recursiva.
          Behind feature-flag (AGENT_RUNTIME_RECURSIVE) hasta validar e2e; path viejo como fallback.
RIESGO:   latencia (el árbol multiplica llamadas LLM; aceptado), hot-path reescrito (mitigado por
          flag + health-gate + rollback), no-determinismo del cierre/ack/captura (comportamiento
          pedido; guards de runtime evitan loops/explosión, no fuerzan routing).
Plan:     `.claude/plans/quizzical-snacking-teacup.md`.
```

#### Etapa A - Diseño documentado
- [x] 41.1  Documentar en `arquitectura_funcional.md` el modelo recursivo (agente=orquestador), el
            loop unificado LLM↔tools, las fases plan/ejecución/consolidación, los guards
            (max_depth/max_iters/budget/visited) y las tools de housekeeping. Reemplaza la sección de
            cortocircuitos de FASE 40.

#### Etapa B - Runtime recursivo (núcleo)
- [x] 41.2  `core/agent_runtime.py`: `RecursiveAgent` (satisface el Protocol BaseAgent) + loop
            extendido de `run_loop` con la tool `call_agent(agent_id, query)` recursiva, paralelismo
            de tool_calls, guards de recursión y tracing de árbol. Tests con LLM y agentes hijos
            mockeados.

#### Etapa C - Tools de housekeeping + agente raíz
- [x] 41.3  ToolDefs + dispatch `close_conversation`/`ignore`/`capture_reply`/`clarify` sobre
            conv/intents (reusa `manager.close`, `intent_state.capture_reply/get_pending_request`,
            `conv.set_continuation`). Raíz = `RecursiveAgent(sub_agents=RBAC, tools=housekeeping)`;
            inyección de la pregunta pendiente. Tests: el LLM mock elige cada tool
            ("chau"→close, "ok"→ignore, "sí"→capture, ambiguo→clarify).

#### Etapa D - Migración de agentes de dominio (big-bang)
- [x] 41.4  Migrar weather + travel + maps a `RecursiveAgent`: ToolDefs (openmeteo/geocoding/
            maps_client) + dispatch (envolviendo backends existentes) + system_prompt + afinidades
            (maps→weather). Tests por agente con backends mockeados.
- [x] 41.5  Migrar haos a `RecursiveAgent`: tools `find_entity`/`get_state`/`call_service`
            (ha_client) + RAG de entidades + dispatch + system_prompt. Tests con ha_client mockeado.
- [x] 41.6  Migrar finance + mercadolibre a `RecursiveAgent`: tools dolarapi/yfinance/ml_client/
            portfolio + dispatch + system_prompt + afinidades. Tests con backends mockeados.
- [x] 41.7  Migrar scheduler (calendar_client) + profile + user_mgmt + system a `RecursiveAgent`
            (system ya usa run_loop). ToolDefs + dispatch + system_prompt + afinidades. Tests por agente.

#### Etapa E - Reemplazo del hot-path
- [x] 41.8  `server.py`: quitar de `process()`/`process_stream()` los cortocircuitos (close/ack/
            capture) y enrutar todo al `RecursiveAgent` raíz. Eliminar `fast_classifier` y retirar
            `coordinator.coordinate`/`_run_plan` del hot-path (el árbol los subsume). Flip del flag.
            Tests e2e (LLM mockeado): close/ignore/capture/clarify, single-domain, multi-domain.

#### Etapa F - Observabilidad del árbol
- [x] 41.9  `trace_store`/`metrics_store`: trace anidado (depth, subárbol, tool_calls por nodo) +
            métricas nuevas (llamadas LLM por request, tool_calls por request, profundidad máxima,
            uso de tools de housekeeping). Deprecar `bypass_rate` (tiende a 0) y reemplazar en
            `/metrics` (ambos backoffices). Tests de ingesta.

#### Etapa G - Deploy + verificación
- [x] 41.10 Validar tras flag, flip, `bash scripts/deploy.sh core` (health-gate + rollback), smoke de
            voz/WhatsApp y revisión de latencia real en el Brain.
            HECHO: core desplegado (v0.1.6) con el flag `AGENT_RUNTIME_RECURSIVE` en **OFF** (runtime
            recursivo dormido; producción sigue en el path FASE 40). Validado standalone contra el
            Ollama real del Brain: el árbol responde correcto (clima/dólar con datos reales,
            "chau"→cierre vía tool). **Latencia ~12-17s en queries de dominio** (vs ~3-5s del path
            viejo) por la multiplicación de llamadas LLM; "chau" ~2.2s. **FLIP POSTERGADO**: pasar
            producción al árbol recursivo es decisión del usuario por el trade-off de latencia; al
            flipear (env `AGENT_RUNTIME_RECURSIVE=true` + restart) recién ahí se elimina el path viejo
            (coordinator + fast_classifier). Smoke de voz/WhatsApp real queda para después del flip.

### FASE 42 - Optimización de latencia del runtime recursivo (pre-flip)

```
Objetivo: Bajar la latencia del árbol de agentes recursivo (FASE 41) antes de flipear el flag a
          producción. La validación e2e dio ~12-17s en queries de dominio (vs ~3-5s del path FASE
          40) por la multiplicación de llamadas LLM (raíz plan + hijo plan + hijo consolidación +
          raíz consolidación). Sin sacrificar el principio agnóstico (no se reintroducen
          cortocircuitos deterministas).
Estado:   Pendiente.
Deps:     FASE 41 (runtime recursivo desplegado dormido, flag AGENT_RUNTIME_RECURSIVE).
```

#### Etapa A - Palancas de latencia
- [ ] 42.1  Saltear la consolidación cuando un nodo delegó a UN solo sub-agente y no produjo prosa
            propia ni otras tools: devolver la respuesta del hijo directa (ahorra una llamada LLM por
            nivel). En el runtime, agnóstico. Tests.
- [ ] 42.2  Modelo por tier: las hojas de dominio usan un modelo más chico/rápido (configurable
            `AGENT_LEAF_MODEL`); el raíz mantiene el modelo grande para el routing. Tests.
- [ ] 42.3  Hint de routing: pasar la sugerencia del fast_classifier como CONTEXTO (no bypass) en el
            prompt del raíz, para acelerar/acertar la delegación (menos iteraciones del tool-loop).
            Sigue decidiendo el LLM. Tests.

#### Etapa B - Validación
- [ ] 42.4  Re-validar la latencia contra el Ollama real del Brain (standalone, read-only) y reportar.
            Dejar listo para el flip (decisión del usuario).
