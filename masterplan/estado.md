# Master Plan - Red de Agentes Locales
# Matías Blasi | matias@blasi.ar
# Última actualización: 2026-04-29

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
Estado:   EN CURSO (~70% completo)
```

#### Completado
- [x] 1.1  Stack base instalado (Ollama, Whisper, Piper, PyAudio)
- [x] 1.2  Audio pipeline: captura 44100Hz → resampleo 16000Hz
- [x] 1.3  STT validado: faster-whisper español, 100% confianza
- [x] 1.4  LLM validado: qwen2.5:7b, 3.5s, formato ACTION correcto
- [x] 1.5  Pipeline completo voz→STT→LLM validado (15.7s total)
- [x] 1.6  openWakeWord: repo clonado, dependencias OK, train.py importa
- [x] 1.7  Piper: 4 voces españolas descargadas
- [x] 1.8  Samples positivos "Capitán" generados (90 samples, voz daniela)

#### Pendiente
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

#### Decisiones pendientes
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
          parentesco, y personalizar la experiencia. Prerequisito para interacciones
          contextuales como "reproduce mi música preferida" o "¿cómo está mi portfolio?"
Estado:   POSTERGADA — retomar después de FASE 7, prerequisito para FASE 11
          No es necesaria para FASE 3-7: el routing no depende de quién habla.
          Se vuelve relevante cuando los agentes de dominio necesitan personalizar
          por usuario (FASE 11) o cuando RBAC tiene sentido con múltiples usuarios reales.
```

#### Impacto por módulo

**home-agents-core** (nuevos archivos):
  · users.py          modelo User, registro CRUD, persistencia JSON/SQLite
  · enrollment.py     workflow de captura de frases y cómputo de embedding
  · Endpoints nuevos: GET/POST/DELETE /users, GET/PATCH /users/{id}/profile
  · server.py         recibe speaker_id en POST /process, inyecta perfil al LLM
  · RBAC middleware   check_role() aplicado por intent

**home-agents-ear** (archivos nuevos/modificados):
  · listen.py         speaker ID después del wake word, speaker_id en HTTP body
  · panel_users.py    nuevo panel: usuarios registrados, speaker activo, enrollment progress
  · dashboard.kdl     agregar panel_users a floating_panes

#### Tareas
- [ ] 2.5.1  Modelo de usuario: roles (admin/familiar/niño/invitado) y relaciones de parentesco
             (padre/madre/hijo/hija/pareja/abuelo/invitado/propietario)
- [ ] 2.5.2  Persistencia del registro: JSON/SQLite en ~/.local/share/capitan/users
             Embeddings como .npy por separado — datos biométricos, nunca a la nube
- [ ] 2.5.3  API REST en core: GET/POST/DELETE /users, GET/PATCH /users/{id}/profile
- [ ] 2.5.4  Bootstrap del admin: enrollment guiado al detectar sistema sin usuarios registrados
             Sistema anuncia → captura N frases → persiste con role=admin
- [ ] 2.5.5  Comando de voz para agregar usuario (solo admin):
             "Capitán, agregar a Gala como hija con acceso familiar"
- [ ] 2.5.6  Proceso guiado de enrollment por voz: N frases predefinidas, tono de inicio/fin,
             detección de ruido, confirmación. Nuevo estado en ear: enrolling
- [ ] 2.5.7  Identificación de speaker en tiempo real: cosine similarity sobre audio ya capturado
             (< 200ms), speaker_id adjunto al POST /process. Fallback: perfil guest
- [ ] 2.5.8  RBAC básico: tabla de permisos por rol, check_role() en core,
             respuesta de voz al denegar acceso
- [ ] 2.5.9  Panel de usuarios en dashboard ear: lista de usuarios, speaker activo en el último
             pedido, progress bar de enrollment en curso

---

### FASE 3 - Infraestructura Multi-Agente
```
Objetivo: Patrón de extensión para agentes de dominio + estado compartido cross-agente
Estado:   EN CURSO (5/7 ya implementados durante FASE 1-2)
```

#### Ya implementado
- [x] 3.2  Orquestador central → server.py (FastAPI :8765, POST /process)
- [x] 3.3  Router de intención → agent_registry.dispatch() (keywords + LLM fallback)
- [x] 3.5  Logging y observabilidad → /tmp/capitan/*.json + dashboard zellij
- [x] 3.6  API unificada → POST /process, GET /agents, GET /health, GET /conversations
- [x] 3.7  Dashboard de estado → panel_agents.py (agente activo, fuente, conversación)

#### Pendiente
- [ ] 3.1  Contrato de interfaz para agentes de dominio: BaseAgent protocol en código,
           patrón de registro en agent_registry, guía para agregar FASE 4-7
- [ ] 3.4  Estado compartido cross-agente: slot de contexto legible/escribible por cualquier
           agente activo (ej: clima sabe que llueve → haos puede ajustar persianas)

---

### FASE 3.5 - Integración WhatsApp
```
Objetivo: Canal de texto y audio hacia el orquestador vía WhatsApp
Estado:   Pendiente (dep satisfecha: orquestador ya existe)
Deps:     FASE 3.2 ✓ (orquestador implementado), FASE 1.3 ✓ (STT), FASE 1 TTS ✓
Privacidad: solo números autorizados, todo corre local
```

#### Etapa A - Canal de texto
- [ ] 3.5.1  Elegir cliente WA: whatsapp-web.js (Node 18) vs evolution-api (self-hosted REST)
- [ ] 3.5.2  Setup del cliente: sesión persistente con QR scan, reconexión automática
- [ ] 3.5.3  Webhook receiver en el orquestador (FastAPI endpoint /wa/inbound)
- [ ] 3.5.4  Whitelist de números autorizados (solo responde a contactos configurados)
- [ ] 3.5.5  Routing texto → orquestador → agente → respuesta de vuelta por WA
- [ ] 3.5.6  Manejo de contexto por número: historial de conversación en sesión

#### Etapa B - Canal de audio (PTT)
- [ ] 3.5.7  Recibir mensajes de voz (PTT) de WhatsApp → descargar OGG/Opus
- [ ] 3.5.8  Convertir OGG → WAV 16000Hz (ffmpeg o librosa)
- [ ] 3.5.9  Pasar por faster-whisper → texto → orquestador (mismo pipeline que mic)
- [ ] 3.5.10 Respuesta: opción texto o audio generado con Piper → enviar nota de voz

#### Decisiones pendientes
- [ ] Cliente WA: whatsapp-web.js (más simple, Node) vs evolution-api (REST genérico, más robusto)
- [ ] Respuesta: ¿siempre texto o detectar si el usuario mandó audio → responder audio?
- [ ] Persistencia de sesión WA: ¿LocalAuth en disco o base de datos?

---

### FASE 4 - Agente Clima
```
Objetivo: Consultas de clima por voz + integración con domótica
Estado:   Pendiente
```
- [ ] 4.1  Integración Open-Meteo API (libre, sin key, precisa)
- [ ] 4.2  Datos históricos y pronóstico extendido local
- [ ] 4.3  Integración con domótica:
           lluvia → cerrar persianas
           frío extremo → ajustar calefacción
           viento fuerte → alertas
- [ ] 4.4  Alertas proactivas por voz
- [ ] 4.5  Contexto geográfico (tu ubicación, sin enviarla a terceros)

---

### FASE 5 - Agente Agenda
```
Objetivo: Gestión de agenda por voz, privada y local
Estado:   Pendiente
```
- [ ] 5.1  CalDAV local (Radicale en HAOS o servidor dedicado)
- [ ] 5.2  Sincronización opcional con Google Calendar
- [ ] 5.3  Consultas por voz:
           "¿qué tengo mañana?"
           "agendá reunión el viernes a las 10"
           "¿cuándo es el próximo feriado?"
- [ ] 5.4  Integración con domótica:
           alarma de agenda → encender luces gradualmente
           reunión en 15min → recordatorio por voz
- [ ] 5.5  Recordatorios proactivos sin trigger de voz
- [ ] 5.6  Vista de agenda en panel de HAOS

---

### FASE 6 - Agente Inversiones
```
Objetivo: Consultas financieras por voz, datos privados locales
Estado:   Pendiente
Nota:     Datos sensibles, nunca salen de la red local
```
- [ ] 6.1  Definir fuentes de datos:
           Yahoo Finance (acciones internacionales)
           BCRA API (dólar, tasas Argentina)
           Ambito/Infobae scraping (mercado local)
- [ ] 6.2  Scraper/poller de cotizaciones (actualización periódica)
- [ ] 6.3  Portfolio local (tus activos, cifras, completamente privado)
- [ ] 6.4  Consultas por voz:
           "¿cómo está el dólar?"
           "¿cómo va mi portfolio hoy?"
           "¿cuánto subió GGAL esta semana?"
- [ ] 6.5  Alertas configurables (precio objetivo, variación %)
- [ ] 6.6  RAG sobre noticias financieras (scraping + embeddings)
- [ ] 6.7  Resumen diario automático al llegar a casa

---

### FASE 7 - Agente Viajes
```
Objetivo: Asistente de planificación y consulta de viajes
Estado:   Pendiente
```
- [ ] 7.1  Definir casos de uso concretos con tu familia
- [ ] 7.2  RAG sobre documentos de viaje (pasaportes, reservas, PDFs)
- [ ] 7.3  Integración con APIs de clima en destinos
- [ ] 7.4  Consultas por voz:
           "¿qué clima hace en Roma en octubre?"
           "¿tengo el pasaporte vigente?"
           "¿cuándo es el próximo viaje?"
- [ ] 7.5  Planificación con LLM (itinerarios, sugerencias)
- [ ] 7.6  Alertas de documentos por vencer

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
Estado:   Pendiente
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
- [ ] 9.1  Definir formato del catálogo de agentes: nombre, descripción, 3-5 ejemplos de queries válidas
- [ ] 9.2  Prompt del coordinador v1: utterance + catálogo → elige un agente + reformula query para ese agente
- [ ] 9.3  Reemplazar router de reglas (FASE 3.3) con llamada al coordinador LLM
- [ ] 9.4  A/B test: precisión de routing coordinador vs. reglas sobre queries del historial real
- [ ] 9.5  Medir overhead de latencia del coordinador; objetivo: que no supere 4s extra en warm

#### Etapa B — Queries multi-agente
- [ ] 9.6  Extender el plan de ejecución a N pasos con dependencias opcionales entre pasos
- [ ] 9.7  Orquestador ejecuta pasos sin dependencias en paralelo (asyncio / ThreadPool)
- [ ] 9.8  Coordinador recibe resultados de todos los agentes y genera respuesta unificada
- [ ] 9.9  Prompt de agregación: sintetizar respuestas parciales en texto coherente, sin repetir cada una

#### Etapa C — Descomposición y corrección
- [ ] 9.10 Detección de requests condicionales ("cuando X, hacé Y"): el coordinador genera un plan con condición explícita
- [ ] 9.11 Manejo de falla de agente: el coordinador detecta error en resultado y reintenta o responde con degradación elegante
- [ ] 9.12 Ciclo de clarificación: si el coordinador detecta ambigüedad irresoluble, genera una pregunta al usuario en vez de asumir

#### Etapa D — Optimización de latencia
- [ ] 9.13 Evaluar qwen2.5:3b como coordinador: instalar, benchmark de routing vs. 7b
- [ ] 9.14 Clasificador rápido para intenciones simples: entrenar con historial de requests reales (sklearn o reglas con score de confianza)
- [ ] 9.15 Híbrido: usar clasificador cuando confianza > umbral configurable, coordinador LLM para el resto

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
- [ ] 11.5  Memoria persistente entre sesiones: SQLite con historial de conversaciones
            previas por perfil. El amigo "recuerda" lo que hablaron antes.
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

### A.2 Red de nodos de audio multi-ambiente

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
