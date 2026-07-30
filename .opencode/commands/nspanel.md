Administrá un NSPanel Pro usando `scripts/nspanel.sh`.

El script soporta múltiples paneles vía `NSPANEL_IP=<ip>` (default: 192.168.68.113).

Comandos disponibles:
- `connect` — conectar ADB over WiFi (puerto 5555)
- `ssh` — abrir shell SSH en Termux (puerto 8022)
- `status` — ver foco actual y estado de audio
- `reboot` — reiniciar el panel
- `open-ha` — lanzar HA Companion App
- `open-termux` — lanzar Termux
- `start-sshd` — iniciar sshd en Termux via ADB
- `boot-script` — ver script de arranque actual
- `update-boot <url>` — cambiar el dashboard que abre al iniciar
- `install-base` — setup completo desde cero (Termux + Boot + HA Companion)
- `packages` — instalar Python + sounddevice en Termux
- `help` — ver ayuda completa

Para dar de alta un panel nuevo: ver `docs/nspanel-setup.md` — guía completa paso a paso.

Si el usuario no especifica qué panel, usá el default (192.168.68.113 — comedor).
Si especifica un ambiente (ej: "dormitorio"), pedí la IP o buscala en CLAUDE.md.

Ejecutar:
```
scripts/nspanel.sh $ARGUMENTS
```

Para comandos que requieren SSH activo, primero corré `start-sshd` si es necesario.
