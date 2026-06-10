Capturá muestras positivas de la wake word "Capitán" desde el mic de un NSPanel, para
mejorar la detección del wake word vía retrain.

Uso: `/nspanel-enroll [N] [user_id] [IP]`
- N: cantidad de muestras (default 20)
- user_id: usuario al que se asocian (default matias)
- IP: panel (default 192.168.68.113 — comedor)

Las muestras se suman al dataset del usuario. Después hay que reentrenar con `/retrain`
para que el modelo nuevo las use (y los nodos lo bajan solos, 16.17).

Pasos:
1. Lanzar el enrollment detached en el NSPanel (sobrevive caídas de SSH):
```bash
IP="${3:-192.168.68.113}"; N="${1:-20}"; UID="${2:-matias}"
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -o StrictHostKeyChecking=no -o ConnectTimeout=10 u0_a53@$IP \
  "export PATH=/data/data/com.termux/files/usr/bin:\$PATH; pkill -9 python3.13 2>/dev/null; sleep 2; nohup python3.13 \$HOME/satellite.py --enroll $UID $N > ~/.enroll.log 2>&1 < /dev/null & disown; echo lanzado"
```

2. Avisar al usuario: "Seguí los beeps: beep agudo → decí 'Capitán' → beep grave. N veces."

3. Tras ~N×3 segundos, verificar cuántas muestras se subieron:
```bash
ssh capitan-lxc "curl -s http://localhost:8765/users/${2:-matias}/wakeword/samples 2>/dev/null | python3 -c 'import sys,json; print(\"muestras:\", json.load(sys.stdin).get(\"count\"))'"
```

4. Recordar al usuario que ahora corra `/retrain` y que reinicie el satellite normal cuando
   termine (el enrollment dejó el satellite detenido). Idealmente con el TV/ambiente en
   silencio durante el enrollment para muestras limpias.
