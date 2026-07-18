*Aclaración, y va primero: este post no es comercial. Objetivos: aprender, dejar de sufrir los ecosistemas cerrados tipo Alexa/Google, y uso familiar. No hay startup ni pitch. Hay una casa que ahora entiende lo que le pido.*

**No lo planifiqué. Fui tirando del hilo.**

Hace dos meses tenía una idea vaga: una red de agentes de IA que viva en mi casa y no en la nube de nadie. Hoy tengo eso corriendo — voz, domótica, agenda, clima, orquestación entre agentes — en un mini-PC, sin que un solo byte salga de mi red local.

Lo que me vuela la cabeza no es el resultado. Es la velocidad: 40 días con actividad en dos meses, sesiones de ~4 horas — unas 160 horas reales, nunca full-time, en ratos muertos convertidos en tiempo productivo. El saldo: ~1.450 commits, 46 fases, 464 tareas cerradas.

**La arquitectura**

Un servidor central en casa (el Brain): mini-PC con iGPU Radeon corriendo STT (faster-whisper), LLM local (qwen2.5:7b sobre ROCm) y TTS. En cada ambiente, un panel de pared Android reflasheado corre un satélite de voz en Python: wake word entrenada desde cero, voice-id para saber quién habla, y el pedido viaja al Brain por la red local, que lo resuelve contra Home Assistant y responde hablando. El loop entero — desde "Capitán" hasta que se prende la luz — se cierra adentro de tu casa.

Arriba, un orquestador decide qué agente (o combinación) resuelve cada pedido y arma el plan. Los agentes colaboran: el de agenda le pregunta al de clima, el de finanzas cruza tu perfil de riesgo con el mercado. Un objetivo difuso ("escaparme un finde a la playa, algo tranqui y sin dispararme el presupuesto") se descompone en pasos y se persigue en background, te avise en cinco minutos o en tres días. Proactividad real, no un cron. Y abajo: deploy con health-gate y rollback automático, backoffice, métricas.

**De dónde sale la velocidad**

La IA generativa no me hizo escribir más rápido: me cambió el tamaño del salto entre "quiero esto" y "esto anda". Las fricciones — un binding de C que no compila, una GPU que Ollama descarta en silencio — se resuelven en minutos, y el cuello de botella pasó a ser decidir qué construir. Y ahí está lo escalable de verdad: una sola persona, en ratos libres, sostiene la complejidad de lo que antes era un equipo.

**El tren está pasando**

No es "vibe coding" — es crear agentes, orquestarlos, levantar productos enteros desde una idea. Ya no es tomar un ticket y codear: es pensar el punta a punta y tomar decisiones a un ritmo al que no estamos acostumbrados. El músculo nuevo es el criterio. Mi regla: "90/10 al cuadrado" — el 90% de las veces profundizo un 10%, y el 10% de las veces profundizo un 90%.

No es fácil. Te expone: pasás a ser vos el cuello de botella. Pero cuando lo dominás, la adrenalina se hace sentir. A los que no se animan: métanse. Van a ver cómo esos nice-to-have que nunca se priorizan se cuelan solos en el backlog.

👇 El video lo muestra andando en 90 segundos. Todo local, todo en casa.
