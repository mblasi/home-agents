Mostrá logs de los servicios de home-agents corriendo en el SER9 (capitan-lxc).

Servicios disponibles: `core`, `backoffice`, `wa` (o `all` para todos).
Opciones: `--follow` para seguir en tiempo real, `--lines N` para N líneas (default 50).

Ejemplos:
- `/logs core` — últimas 50 líneas del core
- `/logs wa --follow` — logs de WA en tiempo real
- `/logs all` — últimas 30 líneas de cada servicio
- `/logs core --lines 100` — últimas 100 líneas del core

Comandos a usar según el argumento:

Para un servicio específico:
```bash
ssh capitan-lxc "journalctl --user -u capitan-$SERVICE -n $LINES --no-pager"
```

Para `--follow`:
```bash
ssh capitan-lxc "journalctl --user -u capitan-$SERVICE -f"
```

Para `all`:
```bash
ssh capitan-lxc "echo '=== CORE ===' && journalctl --user -u capitan-core -n 30 --no-pager | tail -15 && echo '=== BACKOFFICE ===' && journalctl --user -u capitan-backoffice -n 30 --no-pager | tail -10 && echo '=== WA ===' && journalctl --user -u capitan-wa -n 30 --no-pager | tail -10"
```

Ejecutar según $ARGUMENTS.
