Re-enrolá el embedding de voz (voice-id) de un usuario desde el mic de un NSPanel.

Necesario porque los embeddings enrolados con el mic del laptop NO matchean el audio del
mic del NSPanel (características distintas) → el usuario sale como "guest". Re-enrolar desde
el panel genera el embedding correcto y el voice-id distingue al usuario del TV/charla ajena.

Uso: `/nspanel-enroll-voice <user_id> [N] [IP]`
- user_id: **usuario a enrolar** (REQUERIDO — ej: matias, sabina, valeria). Si no se indica,
  preguntar al usuario para qué persona es; NO asumir matias.
- N: cantidad de frases a grabar (default 5, ~4s c/u)
- IP: panel (default 192.168.68.113 — comedor)

El server (audio_server) computa el embedding y actualiza embeddings/<uid>.npy (promedia
con el previo). El voice-id es server-side; el nodo solo graba y manda audio crudo.

Extraé `user_id`, `N` e `IP` de $ARGUMENTS. Si no hay user_id explícito, pedilo antes de seguir.

Pasos:
1. Lanzar el enrollment de voz detached (UID = el usuario indicado):
```bash
UID="<user_id indicado>"; N="${N:-5}"; IP="${IP:-192.168.68.113}"
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
   Si el usuario da conf > 0.75 (conocido) y el TV < 0.75 (guest), activar el gate:
   `REQUIRE_KNOWN_SPEAKER=true` en el .env del ear del SER9.
