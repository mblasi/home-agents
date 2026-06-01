Ejecutá `scripts/backlog.py` con los argumentos que siguen al comando.

Activá el entorno primero: `source ~/home-agents-env/bin/activate`

Ejemplos de uso:
- `/backlog show --pending` — tareas pendientes de todas las fases
- `/backlog show --pending --phase 21` — tareas pendientes de una fase
- `/backlog add 21.5 "título"` — crear tarea + issue + registrar en issues.yaml
- `/backlog done 21.5` — marcar completada + lint + sync con GitHub
- `/backlog sync --dry-run` — previsualizar sync con GitHub
- `/backlog sync` — sincronizar estado.md con GitHub Issues

Comando a ejecutar:
```
source ~/home-agents-env/bin/activate && python scripts/backlog.py $ARGUMENTS
```
