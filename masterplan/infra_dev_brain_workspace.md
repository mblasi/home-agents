# Infraestructura de desarrollo — brain-workspace (Hermes + OpenCode)

Documento de referencia de la infraestructura de desarrollo centralizada en el Brain.
Cubre la migración de Hermes Agent a una VM dedicada 24/7, la instalación de OpenCode
en ambos lados (laptop + Brain), y la arquitectura de sincronización bidireccional
laptop ↔ Brain.

_Última actualización: 2026-08-09_

---

## Motivación

Hermes Agent corría localmente en la laptop de desarrollo (titan). Esto ataba su
disponibilidad al encendido de la laptop: los cron jobs, el bot de Telegram y las
sesiones no sobrevivían a que la laptop se apagara o viajara.

Objetivo: **Hermes disponible 24/7** (Telegram, cron, dashboard) en el Brain, con el
workspace de desarrollo replicado en ambos lados para poder trabajar indistintamente
desde la laptop (viajando) o contra el Brain (en casa, vía SSH), manteniendo los
repositorios y la configuración sincronizados.

Constraint física asumida: con la laptop apagada, sus archivos son inaccesibles. Por
eso el modelo NO es "workspace remoto montado" sino **workspace duplicado** en ambos
lados, con sincronización explícita cuando ambos están online, y verdad canónica en
GitHub para la historia commiteada.

---

## VM brain-workspace (VM 104)

Nueva VM dedicada en el Proxmox del Brain (ver `automation/casa-grande/hardware.md`
para el inventario completo del stack).

| Atributo | Valor |
|----------|-------|
| ID Proxmox | VM 104 |
| Nombre | brain-workspace |
| OS | Ubuntu 24.04.4 LTS |
| Recursos | 2 vCPU · 4 GB RAM · 50 GB disco (48 usable) |
| IP | 192.168.68.140/24 (estática) |
| Acceso | `ssh brain-workspace` (user matias, login por clave) |
| Arranque | onboot=1, startup order=5 (último del stack) |

Aislada del LXC 101 (brain-ai / home-agents + Ollama) a propósito: el workspace de
desarrollo no comparte recursos ni ciclo de vida con los servicios de producción.

---

## Componentes instalados en brain-workspace

### Hermes Agent (desde fork, no upstream)

Se replica **exactamente la versión de desarrollo de la laptop**, que corre desde un
fork con una contribución en curso (PR abierto), no desde la release estable.

- **Fork:** `git@github.com:mblasi/hermes-agent.git`
- **Rama:** `add-vim-search-commands` (soporte vim input, PR abierto contra upstream)
- **Commit fijado:** `88e62ff18`
- **Método:** clone del fork + `uv sync` (venv con lockfile exacto, Python 3.12.3)
- **Ubicación:** `~/hermes-agent`, symlink `~/.local/bin/hermes → .venv/bin/hermes`
- **Nota:** la rama local en la laptop se llama `feat/vim-input-mode` pero está
  pusheada al fork como `add-vim-search-commands` (mismo commit).

### OpenCode (copia literal del binario, ambos lados)

OpenCode corre desde un fork de terceros con soporte vim (opencode-vim / ocv), no
desde el npm estándar. Se replica el binario compilado tal cual.

- **Fork de referencia:** `github.com/leohenon/opencode-vim` (rama `ocv`)
- **Binario:** `~/.local/bin/ocv` (ELF autocontenido, 173 MB) — versión `1.18.8-ocv.4.10`
- **Método:** copia literal del binario laptop → Brain (ELF compatible con glibc de Ubuntu)
- **Wrapper:** `~/.local/bin/oc` — lanza `ocv`, exportando las keys desde la fuente
  única `~/.config/model-keys.env` (adaptado a bash; en la laptop leía de `~/.zshrc`)
- **Fallback:** `~/.local/bin/opencode` (npm opencode-ai estándar)

### Identidad git / GitHub en el Brain

Para que el Brain haga pull/push autónomo (sin depender de la laptop):

- `gh` CLI instalado y autenticado (device flow) contra la cuenta `mblasi`
- Clave SSH propia del Brain generada y registrada en GitHub como `brain-workspace`
- Identidad git: `Matías Blasi <matias@blasi.ar>`

### Shell (zsh)

Se replica el entorno zsh de la laptop con separación común/local (ver más abajo).
zsh + oh-my-zsh + starship, `chsh` a zsh como shell por defecto.

---

## Fuente única de keys de modelos

Las API keys de modelos (NOUS, ANTHROPIC, OPENAI, GEMINI, AVANTE_OPENAI) tenían copias
dispersas (hardcodeadas en `~/.zshrc` y en `~/.hermes/.env`). Se unifican en un único
archivo canónico, sincronizado entre ambas máquinas.

- **Archivo:** `~/.config/model-keys.env` (chmod 600)
- **Formato:** `KEY=valor` **sin** `export` — compatible tanto con `source` (shell)
  como con `EnvironmentFile=` de systemd.
- **Consumidores:**
  - **zsh:** el bootstrap `~/.zshrc` hace `set -a; source model-keys.env; set +a`
    (auto-export al entorno pese a no tener `export`).
  - **OpenCode:** el wrapper `oc` sourcea el archivo con `set -a`.
  - **Hermes (gateway systemd):** `EnvironmentFile=%h/.config/model-keys.env` en el
    service. Por eso el `.env` de Hermes en el Brain **NO** contiene keys de modelo.
- **Política de sync:** last-write-wins (gana la escritura más reciente). No es un
  merge — para secrets, la fuente única evita conflictos.

---

## Split del `~/.zshrc`

El `.zshrc` mezclaba config portable con cosas machine-specific (paths de Gazebo/
dronedojo, tema, gcloud, nvm). Se divide en tres piezas:

| Archivo | Sync | Contenido |
|---------|------|-----------|
| `~/.zshrc` | — (bootstrap idéntico) | Sourcea las 3 piezas en orden |
| `~/.config/model-keys.env` | ✅ (perfil configs) | Keys de modelos (chmod 600) |
| `~/.zshrc.common` | ✅ (perfil configs) | omz, plugins, aliases, completion, `bindkey -v`, starship, PATH |
| `~/.zshrc.local` | ❌ NO sync | Machine-specific: titan (tema gentoo, screenfetch, gcloud, nvm, Gazebo) vs brain (tema simple, sin extras) |

El bootstrap `~/.zshrc` es igual en ambas máquinas; la diferencia vive en `.zshrc.local`.

---

## Arquitectura de sincronización

Dos problemas distintos con soluciones distintas: **configs** (last-write-wins) y
**workspace** (git-aware, porque son repos).

### Principios

- **La laptop es el único orquestador.** Tiene los timers systemd. El Brain no corre
  timers de sync: no hace falta, porque unison (invocado desde la laptop) sincroniza
  en ambos sentidos en una sola pasada, y `git pull` en el Brain habla directo con
  GitHub (no necesita a la laptop).
- **La historia commiteada viaja por git** (push/pull contra GitHub), nunca por unison.
  Sincronizar `.git/` bidireccionalmente corrompe repos.
- **Lo no-commiteado (working tree) viaja por unison**, solo cuando ambos lados están
  en la misma rama y mismo HEAD (base coherente).
- **Ante duda, skip + log.** Nunca se pisan cambios.

### Herramienta: unison

- unison 2.53.x en ambos lados (laptop 2.53.7 / brain 2.53.3, protocolo 2.53 compatible).
- Arquitectura cliente-servidor: la laptop ejecuta unison, que abre SSH al Brain y
  levanta `unison -server` allá; ambos binarios dialogan. **Por eso unison debe estar
  instalado en ambas máquinas** (no alcanza con SSH como rsync).
- **SSH ControlMaster** configurado para `brain-workspace` (reusa una sola conexión;
  ~10× más rápido en operaciones con muchos round-trips).

### Perfil CONFIGS — `~/.unison/configs.prf`

Sincroniza (last-write-wins, `prefer = newer`):
- `~/.config/model-keys.env`
- `~/.zshrc.common`
- `~/.config/opencode/`, `~/.config/starship.toml`
- `~/.hermes/` selectivo: `.env`, `config.yaml`, `skills`, `cron`, `hooks`, `auth.json`

NO sincroniza: `state.db`, `sessions/` (historial local), locks/pids del gateway.

### Perfil WORKSPACE — script `~/.local/bin/worksync`

Script git-aware que itera repo por repo bajo `~/workspace/`. Por cada repo:

1. `git fetch --all --prune` + `git pull --ff-only` en **ambos** lados (nivela la base
   commiteada contra GitHub).
2. Compara rama + HEAD entre laptop y Brain:
   - **Coinciden** → `unison` del working tree (solo el delta no-commiteado).
   - **Difieren** (rama distinta o HEAD distinto) → **SKIP + log**, nunca pisa.
3. unison excluye `.git/` y artefactos regenerables (`node_modules`, `.venv`, `venv`,
   `__pycache__`, `*.pyc`, `dist`, `build`, `.next`, `target`, caches).

Robustez:
- **flock** (`~/.local/share/worksync.lock`) — una sola instancia a la vez (timer +
  runs manuales no se pisan).
- **timeout 120s por repo** — un repo problemático se SKIPea, no traba el batch.
- Log en `~/.local/share/worksync.log`.

### Timers systemd (solo en la laptop)

| Unit | Intervalo | Acción |
|------|-----------|--------|
| `configsync.timer` | cada 30 min | `unison configs` |
| `worksync.timer` | cada 30 min | `~/.local/bin/worksync` |

`OnBootSec` bajo + `OnUnitActiveSec=30min` + `Persistent=true`. Corren solo cuando la
laptop está encendida y el Brain es alcanzable (el script hace no-op si el Brain no
responde).

### Copia inicial del workspace

Copia base laptop → Brain vía rsync excluyendo artefactos regenerables: de 5.9 GB
totales, ~3.4 GB son artefactos (node_modules 2.9 GB, venvs 447 MB, etc.), quedando
~2.0 GB efectivos (35.261 archivos). Los artefactos se regeneran en cada lado con
`npm install` / `pip install`.

---

## Gateway de Hermes (Telegram + dashboard)

Service systemd user en el Brain: `~/.config/systemd/user/hermes-gateway.service`.

- `EnvironmentFile=%h/.config/model-keys.env` (keys desde la fuente única)
- `ExecStart=%h/.local/bin/hermes gateway run`, `Restart=always`
- **linger habilitado** para matias (el service sobrevive sin sesión SSH)
- Reusa el **mismo bot de Telegram** que la laptop (el token se replica en `.env`).

Restricción operativa: **no pueden correr dos gateways con el mismo bot a la vez**
(Telegram rechaza doble polling). El switch consiste en apagar el gateway de la laptop
y encender el del Brain.

### Switch a producción (pendiente al momento de este documento)

1. Apagar el gateway de Hermes en la laptop.
2. En el Brain: `systemctl --user enable --now hermes-gateway`.
3. Verificar: Telegram responde desde el Brain; dashboard web accesible.
4. (Opcional) Desinstalar Hermes de la laptop.

---

## Recuperación ante cortes de energía

La VM brain-workspace hereda la resiliencia del stack del Brain:
- BIOS "Restore AC Power Loss = Power On" (el Brain enciende al volver la corriente).
- onboot=1 + startup order en todos los guests → el stack completo levanta solo.

Con el gateway como systemd service + linger, tras un corte Hermes vuelve a estar
disponible 24/7 sin intervención manual.

---

## Issues conocidos

- **`ai-training`**: unison hace timeout consistente con este repo (chico, 72 archivos,
  idénticos en ambos lados; sin symlinks/nombres raros/mtimes futuros). Se SKIPea por
  el timeout por-repo, sin afectar al resto. Pendiente de diagnóstico de raíz.
