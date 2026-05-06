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

---

### FASE 6 - Agente Inversiones
```
Objetivo: Consultas financieras por voz, datos privados locales
Estado:   EN CURSO (6/7 — solo queda 6.6)
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
- [ ] 6.6  RAG sobre noticias financieras (scraping + embeddings)
- [x] 6.7  Resumen diario automático (en finance_alerts.check()):
           Dólar oficial/blue, UYU, movimientos de watchlist. Emite a FINANCE_BRIEFING_HOUR (8am).

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
Estado:   Pendiente (planificar en paralelo con FASE 3-4, ejecutar cuando el sistema esté estable)
Laptop:   Pasa a rol de cliente/satélite y entorno de desarrollo
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
- [ ] 8.10 Ollama con soporte GPU (inferencia ~10-30x más rápida que CPU)
- [ ] 8.11 Recompilar faster-whisper con soporte CUDA
- [ ] 8.12 Docker Compose para todos los servicios (orquestador, agentes, bases de datos)
- [ ] 8.13 IP estática en LAN, hostname fijo (ej: `agentes.local`)
- [ ] 8.14 Acceso SSH seguro desde laptop y otros dispositivos de la red

#### Etapa C - Migración de servicios
- [ ] 8.15 Migrar Ollama + modelos al servidor (servidor nuevo como :11434)
- [ ] 8.16 Migrar orquestador FastAPI (FASE 3) al servidor
- [ ] 8.17 Migrar todos los agentes al servidor
- [ ] 8.18 Laptop queda como: cliente de voz (mic/speaker) + entorno de desarrollo
- [ ] 8.19 Período de operación paralela: laptop + servidor corriendo juntos para validar
- [ ] 8.20 Cutover: redirigir laptop al servidor, apagar servicios locales

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
- [ ] 8.26 Systemd units para auto-restart de todos los servicios
- [ ] 8.27 Monitoreo de recursos: temperatura GPU/CPU, uso de VRAM, latencias por agente
- [ ] 8.28 Alertas si un servicio cae (notificación por WhatsApp vía FASE 3.5)
- [ ] 8.29 Backup automático de modelos fine-tuneados y configuraciones
- [ ] 8.30 Wake-on-LAN desde laptop (servidor puede estar en suspend fuera de horario)

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

---

### FASE 11 - Agente Amigo / Asesores Personales
```
Objetivo: Agente conversacional con quien charlar libremente, pedir consejos o consultar
          a un asesor especializado. Sin intención de acción — respuestas en lenguaje
          natural, tono informal, memoria entre sesiones.
Estado:   Pendiente
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
Objetivo: Distribuir la interfaz de voz por toda la casa sin centralizar el audio
          en un único dispositivo. Nodos ligeros capturan voz por habitación y
          delegan todo el procesamiento (STT, LLM, TTS) al servidor central en la laptop.
          Output alternativo via los Echos ya instalados (HAOS media_player) sin
          necesidad de hardware nuevo para empezar.
Estado:   Pendiente
Deps:     FASE 1 (ear/listen.py, STT, TTS), FASE 3 (core/server.py, /process),
          FASE 2.5 (speaker_id — los nodos lo propagan), FASE 12 (backoffice)
Hardware: Etapa A requiere Raspberry Pi Zero 2W + micrófono USB + parlante 3.5mm.
          Etapa B funciona con hardware existente (Echos via HAOS).
Nota:     Ver también Anexo A.2 (origen de esta fase).
```

#### Etapa A — Protocolo y nodo satélite básico
- [ ] 16.1  Protocolo nodo↔servidor: especificación de mensajes WebSocket para streaming
            de audio en chunks. Estructura: `{node_id, room, chunk_b64, sample_rate}`.
            El nodo envía chunks post-wake-word; el core responde con texto de respuesta.
            Fallback: POST HTTP con el audio completo si WebSocket no disponible.
- [ ] 16.2  `ear/satellite.py` — cliente ligero para el nodo satélite: detecta wake word
            con openWakeWord (modelo capitan.onnx), captura el comando, envía chunks al
            core vía WebSocket, recibe texto de respuesta y sintetiza TTS local con Piper.
            Sin STT ni LLM locales — toda la inferencia pesada queda en la laptop central.
            Configurable: CORE_WS_URL, ROOM, DEVICE_INDEX_MIC, DEVICE_INDEX_SPK.
- [ ] 16.3  `core/audio_nodes.py` + `GET /audio-nodes` — registro en memoria de nodos
            conectados: `{node_id, room, ip, last_seen, state: active|offline}`.
            Auto-registro al conectar vía WebSocket; limpieza de nodos expirados.
- [ ] 16.4  `core/ws_audio.py` — servidor WebSocket `/ws/audio` en el core: recibe chunks
            del nodo, acumula y pasa al STT local (faster-whisper), llama internamente a
            `process()` con `source.room` del nodo, devuelve el texto de respuesta al nodo.
- [ ] 16.5  Propagación de `source.room` en el pipeline completo: historial,
            backoffice y dashboard muestran el ambiente de origen de cada comando.
            El campo ya existe en `source`; esta tarea lo hace obligatorio para nodos.

#### Etapa B — Output via Echo (sin hardware nuevo)
- [ ] 16.6  `core/response_router.py` — routear la respuesta al speaker correcto según
            `source.room`. Si el room tiene un Echo asignado: sintetizar TTS a WAV y
            reproducir via HAOS `media_player.play_media`. Si no: TTS local como ahora.
            Tabla de routing: `room → entity_id` configurable en `.env` o agents.json.
- [ ] 16.7  Backoffice `/rooms` — CRUD de ambientes: nombre, entity_id del Echo asignado,
            node_id del satélite si hay uno conectado. Tabla editable con estado en tiempo real.

#### Etapa C — Observabilidad y robustez
- [ ] 16.8  Health check periódico por nodo de audio: ping cada 30s desde el core,
            marcar offline si no responde en 3 intentos. Backoffice muestra estado en tiempo real.
- [ ] 16.9  Panel en dashboard zellij (`panel_nodes.py`): nodos de audio activos, ambiente
            del último comando, latencia STT+LLM por nodo, estado online/offline.
- [ ] 16.10 Guía de instalación del nodo satélite en Raspberry Pi Zero 2W: dependencias
            (Python, openWakeWord, Piper, pyaudio), configuración de audio (ALSA),
            systemd service con auto-reconexión, verificación end-to-end.

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
Objetivo: Mejorar la experiencia de interacción por voz: feedback sonoro al detectar
          la wake word y duck de volumen automático para no interferir con audio en
          reproducción mientras el usuario habla.
Estado:   Pendiente
Deps:     FASE 1 (pipeline base, COMPLETA), FASE 16 deseable para extensión a nodos.
```

- [ ] 18.1  **Sonido de confirmación en wake word** — reproducir un beep/chime breve
            (archivo WAV) via ffplay inmediatamente al detectar la wake word, antes de
            iniciar la grabación del comando. El sonido debe ser corto (<500ms) y
            no solaparse con la grabación STT. Archivo de audio en `ear/assets/wakeword_ack.wav`.

- [ ] 18.2  **Duck de volumen durante grabación** — al detectar wake word, bajar el
            volumen del sistema al mínimo posible (o mutear) antes de grabar el comando,
            y restaurarlo al nivel previo al terminar. Usar `pactl set-sink-volume` para
            control de PulseAudio/PipeWire. Debe detectar el nivel actual, bajar, grabar,
            y restaurar incluso si la grabación falla o el pipeline lanza excepción
            (try/finally). Implementar en `ear/listen.py`.

Estado:   Pendiente

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
Estado:   Pendiente
Deps:     FASE 9 (coordinador, COMPLETA), FASE 6 (patrón agente+alertas, COMPLETA),
          FASE 19 (mensajes ricos WA, deseable para output).
Site:     MLU (Uruguay) por defecto; configurable via ML_SITE en .env (MLA, MLB, etc.)
```

#### Etapa A — Cliente público y búsqueda básica

- [ ] 20.1  **Cliente ML público** (`ml_client.py`) — wrapper sobre la API pública de ML sin auth:
            `search(query, site, filters)` → lista de items paginada;
            `get_item(item_id)` → detalle completo (precio, condición, stock, vendedor, envío, fotos);
            `get_description(item_id)` → texto completo del producto;
            `get_seller(user_id)` → reputación, nivel de ventas, ubicación.
            Cache por defecto 10min (configurable); respeta rate limits ML (burst 10 req/s).
            Site configurable vía parámetro o `ML_SITE` en `.env`; default `MLU`.

- [ ] 20.2  **Parsing de intents de búsqueda** — el LLM extrae de la consulta:
            `query` (término libre), `price_max`, `price_min`, `condition` (new/used/all),
            `category_hint` (texto libre → resolver a category_id vía `/sites/{site}/categories`),
            `free_shipping` (bool). Prompt específico de extracción (micro-LLM, similar a
            `_extract_destination()` en travel_agent.py). Sin categoría explícita, buscar en todo ML.

- [ ] 20.3  **Benchmark de resultados** — dado el resultado de `search()`, generar tabla comparativa:
            precio, vendedor (nick + nivel), reputación (verde/amarillo/naranja/rojo), envío gratis,
            cantidad vendida, ubicación, link corto (permalink). Ordenar por score ponderado
            (precio normalizado 40%, reputación vendedor 30%, ventas 20%, envío 10%).
            Formato texto adaptado al canal: tabla monoespaciada para WA/chat, lista para voz.

- [ ] 20.4  **Recomendación justificada** — el agente elige el mejor ítem del benchmark y
            genera una recomendación en lenguaje natural explicando por qué (precio justo,
            vendedor confiable, envío incluido, etc.). Si ningún ítem supera un umbral de
            calidad mínima (reputación < verde o precio outlier), lo indica y sugiere refinar
            la búsqueda. Respuesta voz: 2-3 oraciones. Respuesta WA/chat: párrafo + link.

#### Etapa B — Flujo conversacional multi-turno

- [ ] 20.5  **Contexto de búsqueda por conversación** — `MLSearchContext` en `shared_state`
            por `source_key`: guarda la última query, filtros activos, página actual, y lista
            de items mostrados (referenciados por índice 1..N para follow-ups).
            Permite: "mostrá más" → página siguiente; "el segundo" → detalle del ítem 2;
            "filtrá por nuevo" → rerun con `condition=new`; "más barato" → rerun con
            `price_max` ajustado al mínimo encontrado; "seguí buscando" → nueva query derivada.

- [ ] 20.6  **Refinamiento iterativo** — el agente detecta intents de refinamiento:
            `show_more`, `filter_update`, `item_detail`, `restart_search`.
            Para `item_detail`: llama `get_item()` + `get_description()` y resume en 3-4 puntos
            clave (qué incluye, garantía, ubicación vendedor, tiempo de entrega estimado).
            Para `filter_update`: reutiliza el contexto, aplica el filtro nuevo, resetea página.

#### Etapa C — Seguimiento de precios

- [ ] 20.7  **Tracker de precios** (`ml_price_tracker.py`) — persistencia en
            `~/.local/share/capitan/ml_prices.json`. Estructura por usuario:
            `{user_id: [{item_id, title, target_price, snapshots: [{ts, price}], alert_sent}]}`.
            Comandos: "seguí el precio de este" (ítem del contexto actual), "dejá de seguir X",
            "¿cómo está el precio de lo que seguís?". El `item_id` se resuelve desde el contexto
            de búsqueda activo o por título si el usuario lo describe.

- [ ] 20.8  **Alertas de precio** — el tracker tiene método `check()` registrado en el sistema
            de alertas existente (`alert_queue.py`): si precio actual < (precio_snapshot_anterior × (1 - ML_PRICE_DROP_PCT))
            → emite alerta "{title} bajó X% — ahora ${precio}". Umbral default 5% vía
            `ML_PRICE_DROP_PCT` en `.env`. Cooldown 24h por ítem para no repetir alertas.
            Chequeo cada hora junto al poller de alertas del core.

- [ ] 20.9  **Seguimiento de búsqueda guardada** — además de items individuales, permitir
            guardar una query completa (ej: "notebook RTX 4060 hasta $3000"). Cada chequeo
            corre la búsqueda, compara contra el mejor precio previo registrado, y alerta si
            aparece un ítem nuevo más barato que el mínimo histórico. Útil para productos
            sin item_id estable (stock cambiante, varios vendedores).

#### Etapa D — OAuth y operaciones autenticadas

- [ ] 20.10 **Registro de app ML** — proceso de setup único documentado:
            1. Crear app en https://developers.mercadolibre.com.ar → obtener `client_id` y `client_secret`.
            2. Configurar redirect URI: `http://localhost:8766/ml/callback` (puerto separado del core).
            3. Agregar `ML_CLIENT_ID`, `ML_CLIENT_SECRET` a `core/.env`.
            Scope requerido: `read` (para búsqueda autenticada y wishlist), `offline_access` (refresh).
            Sin estas vars, el agente opera en modo público sin OAuth (degradación limpia).

- [ ] 20.11 **OAuth 2.0 Authorization Code flow** (`ml_auth.py`) — al solicitar auth:
            1. Generar URL de autorización ML y enviar al usuario por WA/voz/chat.
            2. Levantar servidor temporal `http://localhost:8766/ml/callback` con `http.server`
               (solo durante la ventana de auth, máx 5min).
            3. Capturar `code` del redirect, intercambiar por `access_token` + `refresh_token`
               via POST a `https://api.mercadolibre.com/oauth/token`.
            4. Persistir tokens en `~/.local/share/capitan/ml_token_{user_id}.json` (gitignored).
            Auto-refresh: si `access_token` vence (6h), usar `refresh_token` (180 días) transparentemente.

- [ ] 20.12 **Operaciones autenticadas** — con token válido:
            `get_my_orders()` — historial de compras del usuario (útil para "¿ya compré esto antes?");
            `get_wishlist()` — items guardados del usuario en ML;
            `add_to_wishlist(item_id)` — guardar ítem desde el flujo conversacional.
            Si el usuario no autenticó, operaciones degradan a modo público con aviso.

Estado:   Pendiente

---

### FASE 21 - Agente MercadoPago

```
Objetivo: Consulta de saldo, movimientos, cobros y pagos via MercadoPago,
          con OAuth propio (ecosistema MP distinto al de ML aunque mismo developer portal).
          Foco en consulta y monitoreo; operaciones de pago requieren confirmación explícita.
Estado:   Pendiente
Deps:     FASE 20.10-20.11 (patrón OAuth ya establecido, reutilizable); FASE 9 (coordinador).
          Si 20.11 ya implementó ml_auth.py, mp_auth.py puede ser una generalización.
```

#### Etapa A — OAuth y cliente MP

- [ ] 21.1  **Registro de app MP** — setup único en https://www.mercadopago.com.uy/developers:
            Crear app distinta a la de ML (misma cuenta de developer, diferente `client_id`).
            Redirect URI: `http://localhost:8767/mp/callback` (puerto separado de ML y core).
            Scopes: `read` + `offline_access` mínimo; `write` + `money_transfer` solo si se
            implementan pagos (etapa C). Vars `MP_CLIENT_ID`, `MP_CLIENT_SECRET` en `core/.env`.

- [ ] 21.2  **OAuth 2.0 y cliente MP** (`mp_auth.py`, `mp_client.py`) — mismo patrón que
            `ml_auth.py` (20.11): URL auth → servidor temporal :8767 → code → tokens → refresh.
            `mp_client.py` wrappea la API REST de MP con auth header `Bearer {access_token}`;
            auto-refresh transparente; tokens en `~/.local/share/capitan/mp_token_{user_id}.json`.
            Si las vars no están configuradas, el agente informa que necesita autorización y
            guía el proceso al usuario.

#### Etapa B — Consultas de cuenta (solo lectura)

- [ ] 21.3  **Saldo y cuenta** — `get_balance()`: saldo disponible y en proceso por moneda
            (ARS, UYU, USD si aplica). Respuesta natural: "Tenés $X disponibles y $Y en proceso".
            `get_account_info()`: nombre del titular, email, nivel de cuenta (mercadolíder, etc.).

- [ ] 21.4  **Movimientos y historial** — `get_movements(limit, date_from, date_to)`:
            lista de transacciones con tipo (pago recibido, retiro, transferencia, compra ML),
            monto, estado, descripción y fecha. Parsing de consultas: "¿cuánto cobré esta semana?",
            "¿cuándo fue el último retiro?", "¿hay algún pago pendiente?".
            Cache 5min (los movimientos son sensibles a tiempo real).

- [ ] 21.5  **Cobros pendientes y rechazados** — `get_pending_payments()`: filtra movimientos
            por estado `pending` o `in_process`; `get_rejected_payments()`: estado `rejected` con
            motivo de rechazo. Útil para: "¿hay algún cobro que no se acreditó?".

- [ ] 21.6  **Resumen periódico** — método `summary(period)` que agrega: cobros totales,
            pagos totales, saldo neto, transacción más grande, del período indicado (hoy/semana/mes).
            Integrado al sistema de alertas: resumen diario opcional a hora configurable
            via `MP_BRIEFING_HOUR` en `.env` (análogo a `FINANCE_BRIEFING_HOUR`).

#### Etapa C — Cobros y solicitudes de dinero (operaciones escritura)

- [ ] 21.7  **Link de cobro / QR** — `create_payment_link(amount, description, payer_email?)`:
            genera un `checkout/preference` y devuelve el `init_point` (URL de pago MP) listo
            para compartir. Uso: "generá un link de cobro por $500 con descripción 'alquiler'".
            Para uso presencial: `create_qr(amount, description)` via `instore/orders/qr`
            (requiere `pos_id`, documentar setup previo).

- [ ] 21.8  **Solicitud de dinero (money request)** — `request_money(amount, payer_id_or_email, description)`:
            crea una solicitud de cobro a otro usuario MP. Uso: "pedile $200 a Juan por la cena".
            Requiere confirmación explícita antes de ejecutar: el agente muestra el resumen
            ("¿Confirmo solicitud de $200 a juan@mail.com por 'cena'?") y espera `needs_reply: true`
            (integrado con FASE 19.1). Scope `money_transfer` requerido.

- [ ] 21.9  **Transferencia entre cuentas MP propias** — `transfer_to_bank(amount, account)`:
            extracción a CBU/CVU bancaria. Solo ejecuta con doble confirmación (confirmar monto
            y confirmar destino en dos mensajes separados). Scope `money_transfer`. Registrar
            en log local con timestamp para auditoría.

Estado:   Pendiente

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

**Arquitectura propuesta**:
- Nodos ligeros (Raspberry Pi Zero 2W o similar) con micrófono + parlante
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
