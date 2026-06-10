Capturá muestras positivas de la wake word "Capitán" desde el mic de un NSPanel, para
mejorar la detección del wake word vía retrain.

Uso: `/nspanel-enroll <user_id> [N] [IP]`
- user_id: **usuario al que se asocian las muestras** (REQUERIDO — ej: matias, sabina, valeria).
  Si no se indica, preguntar para qué persona es; NO asumir matias.
- N: cantidad de muestras (default 20)
- IP: panel (default 192.168.68.113 — comedor)

Aunque el modelo de wake word es único/compartido (transversal), las muestras se guardan por
usuario (para tracking y métricas). Después hay que reentrenar con `/retrain` para que el
modelo nuevo las use (y los nodos lo bajan solos, 16.17).

Extraé `user_id`, `N` e `IP` de $ARGUMENTS. Si no hay user_id explícito, pedilo antes de seguir.

Pasos:
1. Lanzar el enrollment detached en el NSPanel (UID = el usuario indicado):
```bash
UID="<user_id indicado>"; N="${N:-20}"; IP="${IP:-192.168.68.113}"
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -o StrictHostKeyChecking=no -o ConnectTimeout=10 u0_a53@$IP \
  "export PATH=/data/data/com.termux/files/usr/bin:\$PATH; pkill -9 python3.13 2>/dev/null; sleep 2; nohup python3.13 \$HOME/satellite.py --enroll $UID $N > ~/.enroll.log 2>&1 < /dev/null & disown; echo lanzado"
```

2. Avisar al usuario: "Seguí los beeps: beep agudo → decí 'Capitán' → beep grave. N veces."

3. Tras ~N×3 segundos, verificar cuántas muestras se subieron:
```bash
ssh capitan-lxc "curl -s http://localhost:8765/users/$UID/wakeword/samples 2>/dev/null | python3 -c 'import sys,json; print(\"muestras:\", json.load(sys.stdin).get(\"count\"))'"
```

4. Recordar al usuario que ahora corra `/retrain` y que reinicie el satellite normal cuando
   termine (el enrollment dejó el satellite detenido). Idealmente con el TV/ambiente en
   silencio durante el enrollment para muestras limpias.
