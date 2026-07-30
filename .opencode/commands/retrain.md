Dispará el reentrenamiento del modelo de wake word en el Brain y reportá el progreso acá.

El retrain combina las muestras positivas de "Capitán" de todos los usuarios + los negativos
(genéricos + los capturados orgánicamente de los nodos) → un nuevo `capitan.onnx`. Los nodos
lo bajan solos (16.17). Tarda ~30-60s.

Pasos a ejecutar:

1. Mostrar cuántas muestras/negativos hay antes:
```bash
ssh capitan-lxc "echo -n 'positivos reales (matias): '; curl -s http://localhost:8765/users/matias/wakeword/samples 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"count\"))'; echo -n 'negativos del nodo (TV): '; ls ~/workspace/home-agents/ear/wakeword/data/capitán/negative/node_* 2>/dev/null | wc -l"
```

2. Disparar el retrain y monitorear hasta done/error (informar cada estado):
```bash
ssh capitan-lxc "curl -s -X POST http://localhost:8765/wakeword/train 2>/dev/null >/dev/null; for i in \$(seq 1 20); do sleep 12; s=\$(curl -s http://localhost:8765/wakeword/train/status 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"status\"), \"|\", str(d.get(\"error\",\"\"))[:140])'); echo \"[\$i] \$s\"; case \"\$s\" in *error*|*done*) break;; esac; done"
```

3. Si termina en `done`, mostrar las métricas del entrenamiento:
```bash
ssh capitan-lxc "curl -s http://localhost:8765/wakeword/train/status 2>/dev/null | python3 -m json.tool"
```

Reportar al usuario: cantidad de muestras usadas, métricas (n_positive, n_negative, duration),
y recordar que los nodos bajan el modelo nuevo solo en ≤10 min (o al reiniciar el satellite).

Si falla con un módulo faltante (torch, onnxscript, etc.), instalarlo en el venv del Brain
(`~/home-agents-env/bin/pip install <módulo>`) y reintentar — el entorno de training ya quedó
configurado en la sesión donde se implementó esto.
