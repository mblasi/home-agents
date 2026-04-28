import subprocess
import os

PIPER_BIN   = os.path.expanduser("~/.local/bin/piper/piper")
VOICE_MODEL = os.path.expanduser("~/.local/share/piper/es_AR-daniela-high.onnx")
OUTPUT_DIR  = os.path.expanduser("~/ai-lab/wakeword/data/capitán/positive")

# Variaciones de la palabra en distintos contextos
# Diversidad de contexto = modelo más robusto
PHRASES = [
    # La palabra sola
    "Capitán",
    "Capitán.",
    "Capitán!",
    "¡Capitán!",
    "¡Capitán",

    # Con silencio previo implícito (pausa natural)
    "Eh, Capitán",
    "Oye, Capitán",
    "Hola Capitán",
    "Hey Capitán",
    "Buenas, Capitán",

    # Con algo después (el modelo debe detectar al inicio)
    "Capitán, encendé las luces",
    "Capitán, qué temperatura hay",
    "Capitán, apagá todo",
    "Capitán, estás ahí",
    "Capitán, necesito ayuda",
]

# Velocidades: 0.8=lento, 1.0=normal, 1.2=rápido
# length_scale es inverso de velocidad
LENGTH_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]

os.makedirs(OUTPUT_DIR, exist_ok=True)

sample_idx = 0
total = len(PHRASES) * len(LENGTH_SCALES)
print(f"Generando {total} samples en {OUTPUT_DIR}")

for phrase in PHRASES:
    for length_scale in LENGTH_SCALES:
        output_path = os.path.join(OUTPUT_DIR, f"sample_{sample_idx:04d}.wav")

        result = subprocess.run(
            [
                PIPER_BIN,
                "--model", VOICE_MODEL,
                "--output_file", output_path,
                "--length_scale", str(length_scale),
            ],
            input=phrase.encode("utf-8"),
            capture_output=True,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"  [{sample_idx:03d}] '{phrase}' (scale={length_scale}) → {size/1024:.0f}KB")
        else:
            print(f"  [{sample_idx:03d}] FALLO: '{phrase}' → {result.stderr.decode()}")

        sample_idx += 1

print(f"\nGenerados {sample_idx} samples")
