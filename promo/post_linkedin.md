*Aclaración necesaria, y va primero: este post no es sobre el producto en sí. Lo hice con varios objetivos, y ninguno es comercial. Uno: aprender. Dos: dejar de sufrir las fricciones de los ecosistemas cerrados de los Alexa y Google Assistant de la vida. Tres: uso netamente familiar. No hay startup acá, no hay pitch. Hay una casa que ahora entiende lo que le pido, y un fin de semana largo de aprendizaje que se estiró dos meses.*

---

**No lo planifiqué. Fui tirando del hilo.**

Hace dos meses tenía una idea vaga: una red de agentes de IA que viva en mi casa y no en la nube de nadie. Hoy tengo eso corriendo — voz, domótica, agenda, clima, orquestación entre agentes — en un mini-PC que entra en la palma de la mano, sin que un solo byte salga de mi red local.

Lo que me sigue volando la cabeza no es el resultado. Es la *velocidad*.

Miré el git antes de escribir esto. **40 días con actividad** repartidos en dos meses, con sesiones de unas 4 horas promedio: **~160 horas** de trabajo real, nunca full-time. Ratos después del laburo, algún finde, en un café, esperando que mis hijas salgan del pediatra, en un aeropuerto — donde sea que haya un tiempo muerto. Hoy es facilísimo convertir esos huecos en tiempo productivo.

Y el saldo de esas 160 horas: **~1.450 commits, 46 fases, 464 tareas cerradas.**

**La arquitectura**

El corazón es un servidor central que corre en casa — lo llamo el Brain — sobre un mini-PC con una iGPU Radeon haciendo de acelerador. Ahí vive todo el stack de inferencia: STT con faster-whisper, un LLM local (qwen2.5:7b sobre ROCm) y TTS, sin depender de un solo servicio externo.

Alrededor, en cada ambiente de la casa, hay un panel de pared (Android reflasheado, corriendo un satélite de voz en Python). Cada panel escucha su propia wake word entrenada desde cero, hace voice-id para saber *quién* está hablando, y le pasa el pedido al Brain por la red local. El Brain lo procesa contra Home Assistant y devuelve la acción y la respuesta hablada. El loop entero — desde que decís "Capitán" hasta que se prende la luz — se cierra adentro de tu casa. La nube no participa en ningún tramo.

Por encima de todo eso hay un orquestador: un coordinador que no ejecuta comandos, sino que decide qué agente (o qué combinación de agentes) resuelve lo que pediste, y arma el plan. Deploy con health-gate y rollback automático, un backoffice para observabilidad, métricas persistidas. Cosas que hace dos años me habrían llevado un año-persona, y ni así.

**Lo que hace, en concreto**

No es un asistente de comando-respuesta. Es una red que colabora:

- **Orquestación de agentes** — un coordinador central rutea cada pedido al agente correcto y compone la respuesta.
- **Agentes que colaboran entre sí** — el de agenda le pregunta al de clima, el de finanzas cruza tu perfil de riesgo con el mercado. No trabajan aislados.
- **Construcción de planes** — un objetivo difuso ("escaparme un finde a la playa el mes que viene, algo tranqui y sin dispararme el presupuesto") se descompone en pasos y se persigue en varios turnos.
- **Objetivos inferidos del usuario** — el sistema identifica qué querés a partir de tu perfil, tu historial y tu pedido, no solo del comando literal.
- **Trabajo en background, sin plazo fijo** — la red entera de agentes sigue colaborando por detrás para cumplir esos objetivos, te avise en cinco minutos o en tres días. Proactividad real, no un cron.

**De dónde sale la velocidad**

La IA generativa no me hizo escribir más rápido. Me cambió el *tamaño del salto* que puedo dar entre "quiero esto" y "esto anda". Antes iteraba a la velocidad de mi capacidad de leer docs, pelearme con un binding de C que no compila en Termux, o entender por qué Ollama descarta la GPU integrada en silencio. Ahora esas fricciones se resuelven en minutos, y el cuello de botella pasó a ser *decidir qué construir*, no cómo. Eso es un cambio de naturaleza, no de grado.

Y ahí está lo escalable de verdad: no es que el sistema aguante más usuarios. Es que **una sola persona, en ratos libres, sostiene la complejidad de lo que antes era un equipo.** El apalancamiento no está en el compute — está en cuánto podés abarcar vos solo antes de perder el hilo.

Un par de cosas que me llevo, sin barniz:

- Local-first es más difícil de lo que se vende, pero cada fricción que resolvés es tuya para siempre. Es sin duda, para mí, siempre el mejor camino.
- El límite ya no es técnico. Es cuántas decisiones buenas por hora podés tomar.
- Lo más desafiante no fue el software: fue construir un producto que mete dispositivos físicos en sus flujos. Cada panel hay que programarlo y customizarlo para su función específica, y antes de eso tenés que evaluar si el hardware da para lo que necesitás — el micrófono, el codec, la CPU, la RAM. Ese trabajo de encaje entre lo físico y lo lógico es, sin dudas, mucho más alcanzable hoy apoyándote en IA.

**El tren está pasando**

Si todavía no te subiste, ya estás tarde. Y no, no es "vibe coding" — es mucho más que eso. Es crear agentes, orquestarlos, levantar productos enteros desde una idea, a una velocidad que te desafía y te cambia el rol. Ya no es tomar un ticket y codear: es pensar el punta a punta y empezar a tomar decisiones a un ritmo al que no estamos acostumbrados.

El músculo nuevo es el criterio: saber dónde meterte a fondo y dónde apoyarte en la experiencia y delegar. Mi regla es simple — **"90/10 al cuadrado"**: el 90% de las veces profundizo un 10%, y el 10% de las veces profundizo un 90%.

No es fácil. Te saca de la zona de confort, te desafía, te expone. Pasás a ser vos el verdadero cuello de botella. Pero cuando empezás a dominarlo, la adrenalina y la dopamina se hacen sentir.

A los que todavía no se animan: métanse. Les aseguro que van a empezar a ver cómo esos *nice-to-have* que nunca se priorizan se cuelan solos en el backlog, sin pedir permiso.

---

👇 El video de arriba lo muestra andando en 90 segundos. Todo local, todo en casa.
