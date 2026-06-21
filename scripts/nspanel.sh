#!/usr/bin/env zsh
# Administración de NSPanel Pro vía ADB y SSH
# Uso: scripts/nspanel.sh <comando> [args]

set -euo pipefail

NSPANEL_IP="${NSPANEL_IP:-192.168.68.113}"
NSPANEL_ADB="${NSPANEL_IP}:5555"
NSPANEL_SSH_PORT=8022
TERMUX_USER="u0_a53"
HA_COMPANION="io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LaunchActivity"
TERMUX_ACTIVITY="com.termux/.HomeActivity"
BOOT_SCRIPT="/data/data/com.termux/files/home/.termux/boot/start-ha.sh"

adb_cmd() { adb -s "$NSPANEL_ADB" "$@"; }

cmd_connect() {
    echo "Conectando ADB a $NSPANEL_ADB..."
    adb connect "$NSPANEL_ADB"
}

cmd_disconnect() {
    adb disconnect "$NSPANEL_ADB"
}

cmd_ssh() {
    echo "Conectando SSH a $NSPANEL_IP:$NSPANEL_SSH_PORT..."
    ssh -p "$NSPANEL_SSH_PORT" "${TERMUX_USER}@${NSPANEL_IP}"
}

cmd_status() {
    echo "=== Foco actual ==="
    adb_cmd shell dumpsys window | grep mCurrentFocus
    echo "\n=== Apps en foreground ==="
    adb_cmd shell dumpsys activity | grep "mResumedActivity"
    echo "\n=== Audio ==="
    adb_cmd shell dumpsys audio | grep -E "STREAM_MUSIC|Devices:" | head -6
}

cmd_reboot() {
    echo "Reiniciando $NSPANEL_IP..."
    # el firmware eWeLink ignora 'adb shell reboot' sin root
    adb_cmd shell "su -c reboot" 2>/dev/null || adb_cmd shell reboot
}

cmd_open_ha() {
    adb_cmd shell am start -n "$HA_COMPANION"
}

cmd_open_termux() {
    adb_cmd shell am start -n "$TERMUX_ACTIVITY"
}

cmd_start_sshd() {
    adb_cmd shell am start -n "$TERMUX_ACTIVITY"
    sleep 2
    adb_cmd shell input keyboard text "sshd"
    adb_cmd shell input keyevent KEYCODE_ENTER
    echo "sshd iniciado. Conectate con: ssh -p $NSPANEL_SSH_PORT ${TERMUX_USER}@${NSPANEL_IP}"
}

cmd_boot_script() {
    echo "=== Boot script actual ==="
    adb_cmd shell su u0_a53 -c "cat $BOOT_SCRIPT" 2>/dev/null || \
        adb_cmd shell cat "$BOOT_SCRIPT" 2>/dev/null || \
        echo "(no se pudo leer — iniciá sshd y usá: ssh -p $NSPANEL_SSH_PORT ${TERMUX_USER}@${NSPANEL_IP} cat ~/.termux/boot/start-ha.sh)"
}

cmd_update_boot() {
    local url="${1:-}"
    if [[ -z "$url" ]]; then
        echo "Uso: nspanel.sh update-boot <url>"
        echo "Ejemplo: nspanel.sh update-boot http://192.168.68.101:8123/dashboard-comedor/0"
        exit 1
    fi
    # Escribe via SSH (única forma confiable por restricciones SELinux)
    echo "Actualizando boot script via SSH..."
    ssh -p "$NSPANEL_SSH_PORT" "${TERMUX_USER}@${NSPANEL_IP}" \
        "cat > ~/.termux/boot/start-ha.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 10
am start -n $HA_COMPANION -d $url
EOF
chmod +x ~/.termux/boot/start-ha.sh && echo 'OK' && cat ~/.termux/boot/start-ha.sh"
}

cmd_install_base() {
    echo "=== Setup inicial NSPanel Pro ==="
    echo "Paso 1: Conectar ADB"
    cmd_connect

    echo "\nPaso 2: Instalar Termux"
    local termux_apk="termux-app_v0.118.3+github-debug_arm64-v8a.apk"
    if [[ ! -f "/tmp/$termux_apk" ]]; then
        wget -O "/tmp/$termux_apk" \
            "https://github.com/termux/termux-app/releases/download/v0.118.3/$termux_apk"
    fi
    adb_cmd install "/tmp/$termux_apk" && echo "Termux instalado"

    echo "\nPaso 3: Instalar Termux:Boot"
    local boot_apk="termux-boot-app_v0.8.1+github.debug.apk"
    if [[ ! -f "/tmp/$boot_apk" ]]; then
        wget -O "/tmp/$boot_apk" \
            "https://github.com/termux/termux-boot/releases/download/v0.8.1/$boot_apk"
    fi
    adb_cmd install "/tmp/$boot_apk" && echo "Termux:Boot instalado"

    echo "\nPaso 4: Instalar HA Companion (minimal)"
    local ha_apk="app-minimal-release.apk"
    if [[ ! -f "/tmp/$ha_apk" ]]; then
        wget -O "/tmp/$ha_apk" \
            "https://github.com/home-assistant/android/releases/latest/download/$ha_apk"
    fi
    adb_cmd install "/tmp/$ha_apk" && echo "HA Companion instalado"

    echo "\nPaso 5: Abrir Termux:Boot para registrarlo"
    adb_cmd shell am start -n "com.termux.boot/.BootActivity"

    echo "\nSetup base completo."
    echo "Siguiente paso: abrir Termux, correr 'pkg update && pkg install python portaudio openssh', setear password con 'passwd', y ejecutar 'nspanel.sh update-boot <url>'"
}

cmd_packages() {
    echo "Instalando paquetes Python en Termux via SSH..."
    ssh -p "$NSPANEL_SSH_PORT" "${TERMUX_USER}@${NSPANEL_IP}" \
        "pkg update -y && pkg install -y python portaudio && pip install sounddevice"
}

ssh_panel() { ssh -p "$NSPANEL_SSH_PORT" -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \
    -o StrictHostKeyChecking=no -o ConnectTimeout=8 "${TERMUX_USER}@${NSPANEL_IP}" "$@"; }
scp_panel() { scp -P "$NSPANEL_SSH_PORT" -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \
    -o StrictHostKeyChecking=no "$@"; }
pkg_installed() { adb_cmd shell pm list packages 2>/dev/null | grep -q "package:$1"; }

# Escritura VERIFICADA de un archivo al panel (16.24/FASE34 T4b): scp + readback de sha256, con
# reintentos. Reemplaza el `ssh "cat > file" <<EOF` ciego, que se truncaba si la conexión se
# cortaba (causa de #602: start-ha.sh quedó en 0 bytes y el panel no arrancaba nada al boot).
put_verified() {
    local lf="$1" rf="$2" n=0 want got
    want="$(sha256sum "$lf" | cut -d' ' -f1)"
    while [ "$n" -lt 3 ]; do
        scp_panel "$lf" "${TERMUX_USER}@${NSPANEL_IP}:$rf" >/dev/null 2>&1
        got="$(ssh_panel "sha256sum '$rf' 2>/dev/null | cut -d' ' -f1" 2>/dev/null)"
        [ "$got" = "$want" ] && return 0
        n=$((n + 1)); echo "    · reintento $n ($rf: checksum no coincide)" >&2; sleep 2
    done
    echo "    ✗ FALLÓ escribir $rf verificado" >&2; return 1
}

# Genera los scripts de arranque del nodo (satellite.env, voice-node.sh, start-ha.sh) en archivos
# LOCALES y los instala VERIFICADOS, con permisos y limpieza de basura (boot.sh viejo). Deja el
# panel en el estado de arranque CANÓNICO. Usado por provision y por converge (idempotente).
# Args: <node_id> <room> <audio_url>
write_node_scripts() {
    local node_id="$1" room="$2" audio_url="$3"
    local tmp; tmp="$(mktemp -d)"
    trap "rm -rf '$tmp'" RETURN

    cat > "$tmp/satellite.env" <<EOF
AUDIO_SERVER_URL=$audio_url
NODE_ID=$node_id
ROOM=$room
WAKEWORD_MODEL=/data/data/com.termux/files/home/wakeword/capitan.onnx
MELSPEC_MODEL=/data/data/com.termux/files/home/wakeword/melspectrogram.onnx
EMBEDDING_MODEL=/data/data/com.termux/files/home/wakeword/embedding_model.onnx
WAKEWORD_THRESH=0.8
WAKEWORD_FRAMES_REQ=2
COMMAND_SECS=5
SAMPLE_RATE=16000
EOF

    cat > "$tmp/voice-node.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Supervisor del nodo de voz: relanza satellite.py si crashea (audio HAL no listo tras boot,
# etc.). Para reiniciar el satélite sin perder el supervisor: pkill -f satellite.py (este script
# no matchea ese patrón). Para frenar todo: pkill -f voice-node.sh primero.
export PATH=/data/data/com.termux/files/usr/bin:$PATH
termux-wake-lock 2>/dev/null
while true; do
  echo "[boot] arrancando satellite $(date)" >> ~/.satellite.log
  python3.13 ~/satellite.py >> ~/.satellite.log 2>&1
  echo "[boot] satellite salió rc=$? — reintento en 5s" >> ~/.satellite.log
  sleep 5
done
EOF

    cat > "$tmp/start-ha.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:$PATH
termux-wake-lock

# SSH para acceso remoto
sshd

# HA Companion (dashboard táctil)
sleep 10
am start -n io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LaunchActivity

# Nodo de voz bajo supervisor (auto-reinicio si crashea). Script aparte para que
# `pkill -f satellite.py` mate solo el python y no al supervisor.
sleep 15
setsid nohup bash ~/voice-node.sh >/dev/null 2>&1 </dev/null &
EOF

    ssh_panel "mkdir -p ~/.config ~/.termux/boot" 2>/dev/null
    put_verified "$tmp/satellite.env"  "/data/data/com.termux/files/home/.config/satellite.env" || return 1
    put_verified "$tmp/voice-node.sh"  "/data/data/com.termux/files/home/voice-node.sh" || return 1
    put_verified "$tmp/start-ha.sh"    "/data/data/com.termux/files/home/.termux/boot/start-ha.sh" || return 1
    # permisos + limpiar boot scripts viejos (boot.sh) que no arrancan el nodo
    ssh_panel "chmod +x ~/voice-node.sh ~/.termux/boot/start-ha.sh; rm -f ~/.termux/boot/boot.sh" 2>/dev/null
    echo "  ✓ scripts de arranque canónicos (verificados por checksum)"
}

# Provisioning completo de un panel nuevo (16.24). Idempotente: saltea lo ya hecho.
# Uso: nspanel.sh provision <name> <room> [ip]
cmd_provision() {
    local name="${1:-}" room="${2:-}" ip="${3:-$NSPANEL_IP}"
    if [[ -z "$name" || -z "$room" ]]; then
        echo "Uso: nspanel.sh provision <name> <room> [ip]"; exit 1
    fi
    NSPANEL_IP="$ip"; NSPANEL_ADB="${ip}:5555"
    local NODE_ID="nspanel-${name}"
    local HA_USER="nspanel${name}"
    local REPO="$(cd "$(dirname "$0")/.." && pwd)"
    local AUDIO_URL="${AUDIO_SERVER_URL:-http://192.168.68.132:8766}"
    # el panel es un satélite: debe apuntar al audio server del Brain, nunca a su propio localhost
    case "$AUDIO_URL" in
        *127.0.0.1*|*localhost*)
            echo "✗ AUDIO_SERVER_URL apunta a localhost ($AUDIO_URL) — debe ser la IP del Brain."
            echo "  Desseteá AUDIO_SERVER_URL del entorno o usá http://192.168.68.132:8766"
            exit 1;;
    esac
    echo "=== Provisioning panel '$name' (room=$room, ip=$ip, node=$NODE_ID) ==="

    echo "\n[1/9] ADB — conectividad"
    if ! adb connect "$NSPANEL_ADB" 2>/dev/null | grep -qE "connected|already"; then
        echo "  ✗ no se pudo conectar ADB a $NSPANEL_ADB."
        echo "  PREREQUISITO FÍSICO: habilitá ADB en el panel (Settings → About → tapear build)."
        exit 1
    fi
    echo "  ✓ ADB conectado"

    echo "\n[2/9] Apps base (Termux, Termux:Boot, HA Companion)"
    pkg_installed com.termux           && echo "  ✓ Termux ya" || { cmd_install_base; }
    # Termux:Boot y HA Companion se chequean por separado: que Termux ya esté
    # instalado NO implica que estos estén (cmd_install_base solo corre si falta Termux).
    if pkg_installed com.termux.boot; then echo "  ✓ Termux:Boot ya"; else
        local boot_apk="termux-boot-app_v0.8.1+github.debug.apk"
        [[ -f "/tmp/$boot_apk" ]] || wget -qO "/tmp/$boot_apk" "https://github.com/termux/termux-boot/releases/download/v0.8.1/$boot_apk"
        adb_cmd install "/tmp/$boot_apk" && echo "  ✓ Termux:Boot"; fi
    if pkg_installed io.homeassistant.companion.android.minimal; then echo "  ✓ HA Companion ya"; else
        local ha_apk="app-minimal-release.apk"
        [[ -f "/tmp/$ha_apk" ]] || wget -qO "/tmp/$ha_apk" "https://github.com/home-assistant/android/releases/latest/download/$ha_apk"
        adb_cmd install "/tmp/$ha_apk" && echo "  ✓ HA Companion"; fi
    echo "\n[3/9] Termux:API + Termux:GUI (mic + overlay)"
    if pkg_installed com.termux.api; then echo "  ✓ Termux:API ya"; else
        wget -qO /tmp/termux-api.apk "https://github.com/termux/termux-api/releases/download/v0.53.0/termux-api-app_v0.53.0%2Bgithub.debug.apk"
        adb_cmd install /tmp/termux-api.apk && echo "  ✓ Termux:API"; fi
    if pkg_installed com.termux.gui; then echo "  ✓ Termux:GUI ya"; else
        wget -qO /tmp/termux-gui.apk "https://github.com/termux/termux-gui/releases/download/0.1.6/app-release.apk"
        adb_cmd install /tmp/termux-gui.apk && echo "  ✓ Termux:GUI"; fi
    adb_cmd shell "monkey -p com.termux.gui -c android.intent.category.LAUNCHER 1" >/dev/null 2>&1
    adb_cmd shell appops set com.termux.gui SYSTEM_ALERT_WINDOW allow 2>/dev/null || true
    adb_cmd shell pm grant com.termux.api android.permission.RECORD_AUDIO 2>/dev/null || true
    echo "  ✓ permisos (overlay + mic)"

    echo "\n[4/9] SSH — key auth (bootstrap vía adb root, idempotente)"
    local HT="/data/data/com.termux/files/home"
    # Empujar SIEMPRE la pubkey local al authorized_keys (append si falta). No condicionar al
    # test de SSH: un panel reimagenado puede traer otra key, el test fallaría y la nuestra
    # nunca se agregaría → password prompt. Preferir ed25519, caer a rsa.
    local PUB; PUB="$(cat "$HOME/.ssh/id_ed25519.pub" 2>/dev/null || cat "$HOME/.ssh/id_rsa.pub" 2>/dev/null || true)"
    if [[ -z "$PUB" ]]; then ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -q; PUB="$(cat "$HOME/.ssh/id_ed25519.pub")"; fi
    adb_cmd shell "su -c \"mkdir -p $HT/.ssh && (grep -qF '$PUB' $HT/.ssh/authorized_keys 2>/dev/null || echo '$PUB' >> $HT/.ssh/authorized_keys) && chown -R $TERMUX_USER:$TERMUX_USER $HT/.ssh && chmod 700 $HT/.ssh && chmod 600 $HT/.ssh/authorized_keys\"" >/dev/null 2>&1 || true
    # arrancar sshd
    adb_cmd shell "am start -n $TERMUX_ACTIVITY" >/dev/null 2>&1; sleep 1
    if ! ssh_panel "echo ok" 2>/dev/null | grep -q ok; then
        adb_cmd shell input keyboard text "sshd" >/dev/null 2>&1; adb_cmd shell input keyevent KEYCODE_ENTER >/dev/null 2>&1; sleep 2
    fi
    if ! ssh_panel "echo ok" 2>/dev/null | grep -q ok; then
        echo "  ✗ SSH sigue sin responder tras el bootstrap de key."
        echo "    Verificá que sshd corra en Termux (panel) y reintentá (idempotente)."
        exit 1
    fi
    echo "  ✓ SSH key-auth OK"

    echo "\n[5/9] Dependencias (pkg + pip) + patch openwakeword"
    # Se corre DETACHED en el panel con wake-lock: instalar deps por una sola sesión SSH
    # la mata a mitad (Android suspende el proceso). Escribimos un script y poleamos su log.
    # Claves aprendidas: numpy/onnxruntime NO andan por pip en Termux → pkg python-numpy y
    # python-onnxruntime (tur-repo). pkg upgrade alinea libicu/clang (si quedó a medias rompe
    # toda compilación pip, ej. cffi→sounddevice). scipy se evita con el patch de openwakeword.
    ssh_panel 'export PATH=/data/data/com.termux/files/usr/bin:$PATH
        termux-wake-lock 2>/dev/null
        cat > ~/.provision_deps.sh <<"SCRIPT"
#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "DEPS-START $(date)"
yes | pkg update 2>&1 | tail -2
yes | pkg upgrade -y 2>&1 | tail -2
yes | pkg install -y tur-repo 2>&1 | tail -2
yes | pkg install -y python python-numpy onnxruntime python-onnxruntime portaudio termux-api openssh 2>&1 | tail -3
pip install --no-input sounddevice requests tqdm termuxgui 2>&1 | tail -3
pip install --no-input --no-deps openwakeword 2>&1 | tail -3
# patch scipy-opcional: el path se resuelve por sysconfig porque "import openwakeword"
# falla justo por este import (no se puede derivar el path importándolo).
SP=$(python3.13 -c "import sysconfig; print(sysconfig.get_path(\"purelib\"))" 2>/dev/null)
INIT="$SP/openwakeword/__init__.py"
[ -f "$INIT" ] && sed -i "s/^from openwakeword.custom_verifier_model import train_custom_verifier/try:\n    from openwakeword.custom_verifier_model import train_custom_verifier\nexcept ImportError:\n    train_custom_verifier = None/" "$INIT"
echo "DEPS-DONE $(date)"
SCRIPT
        chmod +x ~/.provision_deps.sh
        rm -f ~/.provision_deps.log
        nohup ~/.provision_deps.sh > ~/.provision_deps.log 2>&1 &
        echo "deps lanzado"' >/dev/null 2>&1
    echo "  … instalando deps en el panel (pkg upgrade + builds, puede tardar varios minutos)…"
    local _ok=""
    for _i in $(seq 1 50); do
        sleep 12
        if ssh_panel 'grep -q DEPS-DONE ~/.provision_deps.log 2>/dev/null'; then _ok=1; break; fi
    done
    [[ -n "$_ok" ]] || { echo "  ✗ deps no terminaron (timeout). Ver ~/.provision_deps.log en el panel"; exit 1; }
    # Verificar imports REALES (no confiar en rc de pkg/pip)
    local _missing
    _missing="$(ssh_panel 'export PATH=/data/data/com.termux/files/usr/bin:$PATH
        for m in numpy sounddevice requests onnxruntime openwakeword tqdm termuxgui; do
            python3.13 -c "import $m" 2>/dev/null || echo $m
        done' 2>/dev/null)"
    if [[ -n "${_missing//[[:space:]]/}" ]]; then
        echo "  ✗ faltan módulos tras la instalación: $(echo $_missing) — ver ~/.provision_deps.log"
        exit 1
    fi
    echo "  ✓ dependencias verificadas (numpy sounddevice requests onnxruntime openwakeword tqdm termuxgui)"

    echo "\n[6/9] Modelos + satellite.py"
    ssh_panel "mkdir -p ~/wakeword ~/.config ~/assets ~/.termux/boot"
    # modelos estáticos (melspec/embedding) desde el venv del laptop; capitan.onnx lo baja el satellite (16.17)
    local OWW_RES="$HOME/home-agents-env/lib/python3.13/site-packages/openwakeword/resources/models"
    if [[ -f "$OWW_RES/melspectrogram.onnx" ]]; then
        scp_panel "$OWW_RES/melspectrogram.onnx" "$OWW_RES/embedding_model.onnx" "${TERMUX_USER}@${ip}:~/wakeword/" \
            && echo "  ✓ modelos de features" || { echo "  ✗ falló la copia de melspec/embedding"; exit 1; }
    else
        echo "  ✗ no encuentro melspectrogram.onnx en el venv del laptop ($OWW_RES)"; exit 1
    fi
    if [[ -f "$HOME/.local/share/wakeword/capitan.onnx" ]]; then
        scp_panel "$HOME/.local/share/wakeword/capitan.onnx" "${TERMUX_USER}@${ip}:~/wakeword/" \
            && echo "  ✓ capitan.onnx (semilla)" || echo "  · capitan.onnx falló — lo baja el satellite (16.17)"
    else
        echo "  · capitan.onnx no está en el laptop — lo baja el satellite (16.17)"
    fi
    # satellite.py es CRÍTICO: si falla, el panel arranca sin nada. Abortar.
    scp_panel "$REPO/ear/satellite.py" "$REPO/ear/satellite_ui.py" "${TERMUX_USER}@${ip}:~/" \
        && echo "  ✓ satellite.py + ui" || { echo "  ✗ falló la copia de satellite.py — abortando"; exit 1; }
    [[ -f "$REPO/ear/assets/wakeword_ack.wav" ]] && { scp_panel "$REPO/ear/assets/wakeword_ack.wav" "${TERMUX_USER}@${ip}:~/assets/" && echo "  ✓ ack wav"; } || true

    echo "\n[7/9] Scripts de arranque (satellite.env + supervisor + boot, verificados)"
    write_node_scripts "$NODE_ID" "$room" "$AUDIO_URL" || { echo "  ✗ scripts de arranque"; exit 1; }

    echo "\n[8/9] Termux:Boot (arranque automático)"
    adb_cmd shell am start -n "com.termux.boot/.BootActivity" >/dev/null 2>&1
    # Eximir a Termux de la optimización de batería: si Android lo suspende, Termux:Boot no
    # dispara start-ha.sh y el panel arranca sin sshd/satélite (parte de #602).
    adb_cmd shell dumpsys deviceidle whitelist +com.termux >/dev/null 2>&1 || true
    adb_cmd shell su -c 'dumpsys deviceidle whitelist +com.termux' >/dev/null 2>&1 || true
    # El am start de BootActivity deja su UI (docs de Termux:Boot) al frente → volver al dashboard.
    sleep 1; adb_cmd shell am start -n "$HA_COMPANION" >/dev/null 2>&1
    echo "  ✓ Termux:Boot registrado + batería sin optimizar"

    echo "\n[9/9] Registrar el panel en la DB (vía el core)"
    local CORE="${CORE_URL:-http://192.168.68.132:8765}"
    if curl -s -X POST "$CORE/panels" -H 'Content-Type: application/json' \
        -d "{\"name\":\"$name\",\"room\":\"$room\",\"ip\":\"$ip\",\"node_id\":\"$NODE_ID\",\"ha_user\":\"$HA_USER\"}" \
        -o /dev/null -w '%{http_code}' 2>/dev/null | grep -q '^2'; then
        echo "  ✓ registrado en la DB"
    else
        echo "  ⚠ no se pudo registrar en el core ($CORE/panels) — registralo desde el backoffice /panels"
    fi

    echo "\n=== Provisioning de '$name' completo ==="
    echo "FALTA (manual, en HA): crear usuario '$HA_USER' (sin guion) + asignarle el dashboard del ambiente."
    echo "Después reiniciá el panel — satellite + overlay arrancan solos por Termux:Boot:"
    echo "  NSPANEL_IP=$ip bash scripts/nspanel.sh reboot"
}

# Converge un panel YA aprovisionado al estado CANÓNICO (sin reinstalar apps/deps): reescribe el
# código del nodo + los scripts de arranque VERIFICADOS, fija Termux:Boot + batería, y deja el
# panel listo para arrancar todo solo al reboot. Idempotente. Corrige paneles con setup viejo o
# archivos truncados (la causa de #602). Uso: nspanel.sh converge <node_id> <room> [ip]
cmd_converge() {
    local node_id="${1:-}" room="${2:-}" ip="${3:-$NSPANEL_IP}"
    if [[ -z "$node_id" || -z "$room" ]]; then
        echo "Uso: nspanel.sh converge <node_id> <room> [ip]"; exit 1
    fi
    NSPANEL_IP="$ip"; NSPANEL_ADB="${ip}:5555"
    local REPO; REPO="$(cd "$(dirname "$0")/.." && pwd)"
    local AUDIO_URL="${AUDIO_SERVER_URL:-http://192.168.68.132:8766}"
    echo "=== Converge $node_id (room=$room, ip=$ip) al estado canónico ==="
    if ! ssh_panel "echo ok" 2>/dev/null | grep -q ok; then
        echo "  ✗ sin SSH a $ip. Iniciá sshd: NSPANEL_IP=$ip bash scripts/nspanel.sh start-sshd"; exit 1
    fi
    echo "[1/3] código del nodo (satellite.py + ui, verificado)"
    put_verified "$REPO/ear/satellite.py"    "/data/data/com.termux/files/home/satellite.py"    || exit 1
    put_verified "$REPO/ear/satellite_ui.py" "/data/data/com.termux/files/home/satellite_ui.py" || exit 1
    echo "  ✓ satellite.py + ui"
    echo "[2/3] scripts de arranque (verificados)"
    write_node_scripts "$node_id" "$room" "$AUDIO_URL" || exit 1
    echo "[3/3] Termux:Boot + batería"
    adb connect "$NSPANEL_ADB" >/dev/null 2>&1
    adb_cmd shell am start -n "com.termux.boot/.BootActivity" >/dev/null 2>&1
    adb_cmd shell su -c 'dumpsys deviceidle whitelist +com.termux' >/dev/null 2>&1 || true
    # BootActivity deja su UI (docs de Termux:Boot) al frente → volver al dashboard de HA.
    sleep 1; adb_cmd shell am start -n "$HA_COMPANION" >/dev/null 2>&1
    echo "  ✓ listo. Reiniciá para validar el arranque autónomo:"
    echo "     NSPANEL_IP=$ip bash scripts/nspanel.sh reboot"
}

cmd_help() {
    cat << 'EOF'
Uso: scripts/nspanel.sh <comando> [args]

Variables de entorno:
  NSPANEL_IP   IP del panel (default: 192.168.68.113)

Comandos:
  connect          Conectar ADB over WiFi
  disconnect       Desconectar ADB
  ssh              Abrir shell SSH en Termux
  status           Mostrar estado actual (foco, audio)
  reboot           Reiniciar el panel
  open-ha          Lanzar HA Companion App
  open-termux      Lanzar Termux
  start-sshd       Iniciar sshd en Termux (via ADB)
  boot-script      Ver el script de arranque actual
  update-boot <url> Actualizar dashboard de arranque (via SSH)
  install-base     Setup completo desde cero (Termux + Boot + HA Companion)
  packages         Instalar Python + sounddevice en Termux (via SSH)
  provision <name> <room> [ip]  Bootstrap COMPLETO de un panel nuevo (idempotente):
                   apps, deps, modelos, satellite, boot script, registro en panels.yaml.
                   Prereqs físicos: habilitar ADB + setear password SSH (passwd).
  converge <node_id> <room> [ip]  Lleva un panel YA aprovisionado al estado CANÓNICO
                   (sin reinstalar apps/deps): reescribe satellite + scripts de arranque
                   VERIFICADOS por checksum, fija Termux:Boot + batería. Corrige paneles
                   con setup viejo o archivos truncados (#602). Idempotente.
  help             Mostrar esta ayuda

Ejemplos:
  scripts/nspanel.sh provision dormitorio dormitorio 192.168.68.114
  NSPANEL_IP=192.168.68.114 scripts/nspanel.sh connect
  scripts/nspanel.sh update-boot http://192.168.68.101:8123/dashboard-dormitorio/0
  scripts/nspanel.sh ssh
EOF
}

case "${1:-help}" in
    connect)       cmd_connect ;;
    disconnect)    cmd_disconnect ;;
    ssh)           cmd_ssh ;;
    status)        cmd_status ;;
    reboot)        cmd_reboot ;;
    open-ha)       cmd_open_ha ;;
    open-termux)   cmd_open_termux ;;
    start-sshd)    cmd_start_sshd ;;
    boot-script)   cmd_boot_script ;;
    update-boot)   cmd_update_boot "${2:-}" ;;
    install-base)  cmd_install_base ;;
    packages)      cmd_packages ;;
    provision)     cmd_provision "${2:-}" "${3:-}" "${4:-}" ;;
    converge)      cmd_converge "${2:-}" "${3:-}" "${4:-}" ;;
    help|--help|-h) cmd_help ;;
    *)
        echo "Comando desconocido: $1"
        cmd_help
        exit 1
        ;;
esac
