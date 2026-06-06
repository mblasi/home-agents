# NSPanel Pro — Proceso de alta

Guía para agregar un nuevo NSPanel Pro a la red de home-agents.

## Prerequisitos

- NSPanel Pro con firmware eWeLink (cualquier versión)
- Conectado por cable ethernet o WiFi a la misma LAN
- IP conocida (buscarla en el router)

---

## Paso 1 — Habilitar ADB

En el panel físico:
1. **Settings → About** → tapear 7 veces sobre "os version" (puede no funcionar en todos los firmwares)
2. Si no funciona: **Settings → About → Software Update** → tapear hasta ver un mensaje tipo "allowed ... token"
3. Desde la laptop, verificar:

```zsh
adb connect <IP>:5555
adb -s <IP>:5555 shell getprop ro.product.model   # debe devolver "px30_evb"
```

Si conecta, ADB está habilitado.

---

## Paso 2 — Setup base (automatizado)

```zsh
NSPANEL_IP=<IP> bash scripts/nspanel.sh install-base
```

Instala: **Termux**, **Termux:Boot**, **HA Companion App (minimal)**.

---

## Paso 3 — SSH y Python (en el panel)

Abrí Termux en el panel físicamente y ejecutá:

```bash
pkg update -y && pkg install -y python portaudio openssh
passwd          # setear password para SSH
sshd            # iniciar servidor SSH
```

Desde la laptop, conectate:

```zsh
NSPANEL_IP=<IP> bash scripts/nspanel.sh ssh
```

Desde la sesión SSH, instalá dependencias Python:

```bash
pip install sounddevice
mkdir -p ~/.termux/boot
```

---

## Paso 4 — Boot script (lanza HA Companion al iniciar)

Desde SSH en el panel:

```bash
cat > ~/.termux/boot/start-ha.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 10
am start -n io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LaunchActivity
EOF
chmod +x ~/.termux/boot/start-ha.sh
```

O desde la laptop (requiere SSH activo):

```zsh
NSPANEL_IP=<IP> bash scripts/nspanel.sh update-boot http://192.168.68.101:8123
```

---

## Paso 5 — Abrir Termux:Boot

```zsh
adb -s <IP>:5555 shell am start -n com.termux.boot/.BootActivity
```

Solo se necesita hacer esto una vez para registrar el receptor de boot.

---

## Paso 6 — Usuario HA y dashboard

En HA (`http://192.168.68.101:8123`):
1. **Settings → People → Add Person** → crear usuario `nspanel-<ambiente>` (ej: `nspanel-comedor`)
2. Desde HA Companion en el panel → hacer login con ese usuario
3. En el panel → **foto de perfil → Default Dashboard** → seleccionar el dashboard del ambiente

---

## Paso 7 — Verificar

Reiniciar el panel:

```zsh
adb -s <IP>:5555 shell reboot
```

Al arrancar debe:
- Mostrar HA Companion con el dashboard del ambiente (después de ~15s)
- Responder SSH: `ssh -p 8022 u0_a53@<IP>`

---

## Comandos útiles post-setup

```zsh
# Administrar desde la laptop
NSPANEL_IP=<IP> bash scripts/nspanel.sh status
NSPANEL_IP=<IP> bash scripts/nspanel.sh ssh
NSPANEL_IP=<IP> bash scripts/nspanel.sh reboot
NSPANEL_IP=<IP> bash scripts/nspanel.sh update-boot http://192.168.68.101:8123/dashboard-dormitorio/0
```

---

## Paneles activos

| Ambiente | IP | Usuario HA | Dashboard |
|---|---|---|---|
| Comedor | 192.168.68.113 | nspanelcomedor | dashboard-comedor |

Actualizar esta tabla al agregar cada panel.

---

## Notas técnicas

- **Android**: 8.1.0 AOSP / Rockchip PX30 (px30_evb)
- **Audio**: codec RK809 — mic `pcmC0D0c` + speaker `pcmC0D0p` — accesibles con `sounddevice`
- **ADB**: puerto 5555 (WiFi), root disponible
- **SSH Termux**: puerto 8022, usuario `u0_a53`
- **SELinux**: activo — escribir en `~/.termux/boot/` requiere hacerlo desde SSH como `u0_a53`, no desde ADB root
