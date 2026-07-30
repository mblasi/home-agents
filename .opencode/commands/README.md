# Comandos personalizados de home-agents

Este directorio contiene comandos slash personalizados para OpenCode/Claude que facilitan la operación del sistema home-agents.

## Comandos disponibles

### `/deploy [target] [--ref repo=ref]`
Despliega home-agents al Brain (LXC de producción) por target. Soporta deploy de servicios individuales, cloud-bo, o paneles.

### `/status`
Muestra el estado de todos los servicios corriendo en el Brain: systemd, health checks, HAOS, y uso de recursos.

### `/logs <service> [--follow] [--lines N]`
Muestra logs de los servicios en el Brain. Servicios: `core`, `backoffice`, `wa`, o `all`.

### `/retrain`
Dispara el reentrenamiento del modelo de wake word en el Brain y reporta el progreso.

### `/nspanel <command> [args]`
Administra los NSPanel Pro usando `scripts/nspanel.sh`. Comandos: `connect`, `ssh`, `status`, `reboot`, `open-ha`, etc.

### `/nspanel-enroll <user_id> [N] [panel]`
Re-enrola el embedding de voz (voice-id) de un usuario desde el mic de un NSPanel específico.

### `/nspanel-enroll-voice <user_id> [N] [panel]`
Alias de `/nspanel-enroll` para voice-id enrollment desde un panel.

### `/nspanel-passwd [panel]`
Configura la contraseña SSH en Termux de un NSPanel Pro.

### `/backlog <command> [args]`
Gestiona el backlog de tareas. Comandos: `show`, `add`, `done`, `sync`.

## Uso

Todos estos comandos están disponibles escribiendo `/` seguido del nombre del comando en OpenCode o Claude.

Ejemplo:
```
/status
/deploy core
/logs core --follow
/retrain
```

## Migración desde Claude

Estos comandos fueron migrados desde `.claude/commands/` y funcionan tanto en OpenCode como en Claude.
La documentación principal del proyecto está en `AGENTS.md`.
