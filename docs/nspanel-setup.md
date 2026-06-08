# NSPanel Pro — Bootstrap de un nodo de voz

Guía completa y probada para dar de alta un NSPanel Pro como:
1. **Dashboard HA** táctil por ambiente (HA Companion App)
2. **Nodo de voz** home-agents (wake word → STT → core → TTS)

Replica exactamente el panel del comedor (192.168.68.113) que quedó funcionando.

---

## Resumen de arquitectura

```
NSPanel Pro (Android 8.1, Termux)            SER9 LXC (capitan-lxc)
  satellite.py                                 audio_server.py (:8766)
  - openWakeWord (capitan.onnx)                - faster-whisper STT
  - graba 5s post-wake-word                    - strip wake word prefix
  - POST /process-audio (WAV)        ──────→   - core /process → LLM
  - reproduce WAV respuesta          ←──────   - Piper TTS → WAV
  + HA Companion (dashboard táctil)
```

Latencia end-to-end: ~5s warm.

---

## Prerequisitos

- NSPanel Pro con firmware eWeLink, en la LAN, IP conocida
- `audio_server` corriendo en el SER9 (`systemctl --user status capitan-audio-server`)
- El modelo `capitan.onnx` + `melspectrogram.onnx` + `embedding_model.onnx` en la laptop
  (en `~/.local/share/wakeword/` y el venv de openwakeword)

---

## Paso 1 — Habilitar ADB

En el panel: **Settings → About → Software Update** → tapear hasta ver un mensaje
de token/permiso. Luego desde la laptop:

```zsh
adb connect <IP>:5555
adb -s <IP>:5555 shell getprop ro.product.model   # debe devolver "px30_evb"
```

---

## Paso 2 — Apps base

```zsh
NSPANEL_IP=<IP> bash scripts/nspanel.sh install-base
```

Instala Termux, Termux:Boot y HA Companion (minimal).

**Además, instalar Termux:API** (provee el permiso `RECORD_AUDIO` — sin esto el
micrófono NO funciona desde Termux):

```zsh
wget -O /tmp/termux-api.apk "https://github.com/termux/termux-api/releases/download/v0.53.0/termux-api-app_v0.53.0%2Bgithub.debug.apk"
adb -s <IP>:5555 install /tmp/termux-api.apk
```

> ⚠ Usar el APK de **GitHub** (no F-Droid) — debe tener la misma firma que el Termux de GitHub.

---

## Paso 3 — Password SSH + dependencias

Setear el password de Termux para SSH (sin tener el panel físicamente):

```zsh
NSPANEL_IP=<IP> bash scripts/nspanel.sh passwd <password>   # vía /nspanel-passwd
```

Conectarse y instalar dependencias del sistema y Python:

```zsh
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa u0_a53@<IP>

# Dentro del NSPanel:
pkg update -y && pkg install -y python portaudio onnxruntime termux-api openssh
pip install sounddevice requests numpy tqdm
pip install openwakeword --no-deps   # --no-deps evita scipy (pesado, innecesario)
```

> El paquete `onnxruntime` se instala vía `pkg` (binario ARM precompilado), NO vía pip.
> `openwakeword` se instala con `--no-deps` porque su dependencia `scipy` no compila
> bien y no es necesaria para inferencia.

### Parche openwakeword (scipy opcional)

El `__init__.py` de openwakeword importa `custom_verifier_model` que requiere scipy.
Hacerlo opcional:

```bash
sed -i 's/^from openwakeword.custom_verifier_model import train_custom_verifier/try:\n    from openwakeword.custom_verifier_model import train_custom_verifier\nexcept ImportError:\n    train_custom_verifier = None/' \
  /data/data/com.termux/files/usr/lib/python3.13/site-packages/openwakeword/__init__.py
```

---

## Paso 4 — Permiso de micrófono

Conceder `RECORD_AUDIO` a Termux:API (vía ADB como root):

```zsh
adb -s <IP>:5555 shell pm grant com.termux.api android.permission.RECORD_AUDIO
```

Verificar:

```zsh
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa u0_a53@<IP> \
  "export PATH=/data/data/com.termux/files/usr/bin:\$PATH && python3.13 -c 'import sounddevice as sd; s=sd.InputStream(samplerate=16000,channels=1); s.start(); print(\"mic OK\"); s.stop()'"
```

---

## Paso 5 — Copiar modelos y satellite

Desde la laptop:

```zsh
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa u0_a53@<IP> "mkdir -p ~/wakeword"

scp -P 8022 -o HostKeyAlgorithms=+ssh-rsa \
  ~/.local/share/wakeword/capitan.onnx \
  ~/home-agents-env/lib/python3.13/site-packages/openwakeword/resources/models/melspectrogram.onnx \
  ~/home-agents-env/lib/python3.13/site-packages/openwakeword/resources/models/embedding_model.onnx \
  u0_a53@<IP>:~/wakeword/

scp -P 8022 -o HostKeyAlgorithms=+ssh-rsa \
  ~/workspace/home-agents/ear/satellite.py u0_a53@<IP>:~/satellite.py
```

Crear `~/.config/satellite.env` en el NSPanel:

```
AUDIO_SERVER_URL=http://192.168.68.132:8766
NODE_ID=nspanel-<ambiente>
ROOM=<ambiente>
WAKEWORD_MODEL=/data/data/com.termux/files/home/wakeword/capitan.onnx
MELSPEC_MODEL=/data/data/com.termux/files/home/wakeword/melspectrogram.onnx
EMBEDDING_MODEL=/data/data/com.termux/files/home/wakeword/embedding_model.onnx
WAKEWORD_THRESH=0.7
COMMAND_SECS=5
SAMPLE_RATE=16000
```

Probar:

```zsh
ssh -p 8022 -o HostKeyAlgorithms=+ssh-rsa u0_a53@<IP> \
  "export PATH=/data/data/com.termux/files/usr/bin:\$PATH && python3.13 satellite.py"
# Decir "Capitán" → debe loguear "Wake word detectado"
```

---

## Paso 5b — Indicador visual (Termux:GUI) — FASE 18.3

Barra fina overlay sobre HA Companion que muestra el estado del pipeline de voz.

```zsh
# APK Termux:GUI (GitHub, 0.1.6)
wget -O /tmp/termux-gui.apk "https://github.com/termux/termux-gui/releases/download/0.1.6/app-release.apk"
adb -s <IP>:5555 install /tmp/termux-gui.apk

# Sacar la app de estado "stopped" (Android no entrega broadcasts a apps recién instaladas)
adb -s <IP>:5555 shell "monkey -p com.termux.gui -c android.intent.category.LAUNCHER 1"

# Permiso de overlay
adb -s <IP>:5555 shell appops set com.termux.gui SYSTEM_ALERT_WINDOW allow
```

Paquete Python en Termux (SSH):
```bash
pip install termuxgui
```

Si tu pantalla no es 750px de ancho, ajustá `UI_SCREEN_WIDTH_PX` en `~/.config/satellite.env`
(obtené el ancho con `adb shell wm size`).

> Si Termux:GUI no está instalado, `satellite.py` corre igual sin indicador (degradación elegante).

---

## Paso 6 — Boot script (HA Companion + sshd + satellite)

Crear `~/.termux/boot/start-ha.sh` en el NSPanel:

```bash
#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:$PATH
sshd
sleep 10
am start -n io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LaunchActivity
sleep 15
nohup python3.13 ~/satellite.py >> ~/.satellite.log 2>&1 &
```

```bash
chmod +x ~/.termux/boot/start-ha.sh
```

Registrar Termux:Boot (una sola vez):

```zsh
adb -s <IP>:5555 shell am start -n com.termux.boot/.BootActivity
```

---

## Paso 7 — Usuario HA y dashboard

En HA (`http://192.168.68.101:8123`):
1. **Settings → People → Add Person** → `nspanel-<ambiente>`
2. En el panel, login en HA Companion con ese usuario
3. Perfil → **Default Dashboard** → dashboard del ambiente

---

## Paso 8 — Verificar

```zsh
adb -s <IP>:5555 shell reboot
# Al arrancar: HA Companion con el dashboard + satellite escuchando "Capitán"
```

---

## Paneles activos

| Ambiente | IP | NODE_ID | Usuario HA |
|---|---|---|---|
| Comedor | 192.168.68.113 | nspanel-comedor | nspanelcomedor |

Actualizar al agregar cada panel.

---

## Mantenimiento de espacio

El NSPanel tiene 3.3GB en `/data`. Termux + apps consumen ~1GB. Vigilar:

```zsh
adb -s <IP>:5555 shell "df -h /data | tail -1"
```

Para liberar espacio:
- `pip cache purge` dentro de Termux
- Eliminar `/data/media/0/temp_update.zip` (updates de firmware eWeLink, ~800MB)
- Desinstalar eWeLink si no se usa: `pm uninstall --user 0 com.eWeLinkControlPanel` (~900MB)

---

## Notas técnicas

- **Android**: 8.1.0 AOSP / Rockchip PX30 (px30_evb), ARM64, 2GB RAM, 3.3GB /data
- **Audio**: codec RK809 — mic + speaker via sounddevice. onnxruntime con
  `NnapiExecutionProvider` + `XnnpackExecutionProvider` (aceleración HW)
- **Micrófono**: requiere Termux:API instalado (GitHub APK) + `pm grant RECORD_AUDIO`.
  OpenSLES NO permite 2 input streams simultáneos → grabar desde el mismo stream del wake word.
- **SSH**: puerto 8022, usuario `u0_a53`, requiere `-o HostKeyAlgorithms=+ssh-rsa`
- **SELinux**: escribir en `~/.termux/` requiere hacerlo como `u0_a53` (vía SSH), no ADB root
- **Wake word**: openWakeWord necesita la cadena melspectrogram → embedding → capitan.onnx,
  todo manejado por `openwakeword.Model` con `inference_framework="onnx"`
