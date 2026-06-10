Re-enrolá el embedding de voz (voice-id) de un usuario desde el mic de un NSPanel.

Necesario porque los embeddings enrolados con el mic del laptop NO matchean el audio del
mic del NSPanel (características distintas) → el usuario sale como "guest". Re-enrolar desde
el panel genera el embedding correcto y el voice-id distingue al usuario del TV/charla ajena.

Uso: `/nspanel-enroll-voice [N] [user_id] [IP]`
- N: cantidad de frases a grabar (default 5, ~4s c/u)
- user_id: usuario (default matias)
- IP: panel (default 192.168.68.113 — comedor)

El server (audio_server) computa el embedding y actualiza embeddings/<uid>.npy (promedia
con el previo). El voice-id es server-side; el nodo solo graba y manda audio crudo.

Pasos:
1. Lanzar el enrollment de voz detached:
```bash
IP="${3:-192.168.68.113}"; N="${1:-5}"; UID="${2:-matias}"
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
