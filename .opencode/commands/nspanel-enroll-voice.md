Re-enrolá el embedding de voz (voice-id) de un usuario desde el mic de un NSPanel.

Necesario porque los embeddings enrolados con el mic del laptop NO matchean el audio del
mic del NSPanel (características distintas) → el usuario sale como "guest". Re-enrolar desde
el panel genera el embedding correcto y el voice-id distingue al usuario del TV/charla ajena.

Uso: `/nspanel-enroll-voice <user_id> [N] [panel]`
- user_id: **usuario a enrolar** (REQUERIDO — ej: matias, sabina, valeria). Si no se indica,
  preguntar al usuario para qué persona es; NO asumir matias.
- N: cantidad de frases a grabar (default 5, ~4s c/u)
- panel: nombre/ambiente (ej: `comedor`) o IP cruda. Default: comedor. Se resuelve con
  `python scripts/panels.py resolve <panel>` (registro panels.yaml, 16.23).

El server (audio_server) computa el embedding y actualiza embeddings/<uid>.npy (promedia
con el previo). El voice-id es server-side; el nodo solo graba y manda audio crudo.

Extraé `user_id`, `N` y `panel` de $ARGUMENTS. Si no hay user_id explícito, pedilo antes de seguir.

Pasos:
1. Resolver el panel a IP y lanzar el enrollment detached:
```bash
UID="<user_id indicado>"; N="${N:-5}"; PANEL="${PANEL:-comedor}"
IP=$(python ~/workspace/home-agents/scripts/panels.py resolve "$PANEL" ip 2>/dev/null || echo "$PANEL")
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -o StrictHostKeyChecking=no -o ConnectTimeout=10 u0_a53@$IP \
  "export PATH=/data/data/com.termux/files/usr/bin:\$PATH; pkill -9 python3.13 2>/dev/null; sleep 2; nohup python3.13 \$HOME/satellite.py --enroll-voice $UID $N > ~/.enrollvoice.log 2>&1 < /dev/null & disown; echo lanzado"
```

2. Avisar: "Tras cada beep agudo, hablá normal ~4s (contá, leé algo). Beep grave = siguiente."

3. Tras ~N×5 segundos, verificar el resultado y testear la confianza:
```bash
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -o StrictHostKeyChecking=no u0_a53@${3:-192.168.68.113} "grep -a 'enroll-voice' ~/.enrollvoice.log | tail -3"
```

4. Reiniciar el satellite normal y pedirle al usuario que diga "Capitán, <comando>".
   Revisar el voice-id en el server (debe identificar al usuario, no guest):
```bash
ssh capitan-lxc "journalctl --user -u capitan-audio-server --since '30 seconds ago' --no-pager | grep voice-id | tail -3"
```
   El gate ya está activo (`SPEAKER_THRESHOLD=0.6`, `REQUIRE_KNOWN_SPEAKER=true` en
   ear/.env del Brain). Verificar que el usuario dé conf > 0.6 (conocido) y el TV < 0.6
   (guest). Si la confianza del usuario queda justa, correr el enrollment de nuevo para
   reforzar el embedding (promedia con el previo).
