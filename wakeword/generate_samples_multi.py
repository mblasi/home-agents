import subprocess
import os
import shutil

PIPER_BIN  = os.path.expanduser("~/.local/bin/piper/piper")
OUTPUT_DIR = os.path.expanduser("~/ai-lab/wakeword/data/capitán/positive")

VOICES = [
    os.path.expanduser("~/.local/share/piper/es_AR-daniela-high.onnx"),
    os.path.expanduser("~/.local/share/piper/es_MX-claude-high.onnx"),
    os.path.expanduser("~/.local/share/piper/es_ES-davefx-medium.onnx"),
    os.path.expanduser("~/.local/share/piper/es_ES-sharvard-medium.onnx"),
]

PHRASES = [
    "Capitán",
    "Capitán.",
    "Capitán!",
    "¡Capitán!",
    "¡Capitán",
    "Eh, Capitán",
    "Oye, Capitán",
    "Hola Capitán",
    "Hey Capitán",
    "Buenas, Capitán",
    "Capitán, encendé las luces",
    "Capitán, qué temperatura hay",
    "Capitán, apagá todo",
    "Capitán, estás ahí",
    "Capitán, necesito ayuda",
]

LENGTH_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]

total = len(VOICES) * len(PHRASES) * len(LENGTH_SCALES)
print(f"Generando {total} samples en {OUTPUT_DIR}")
print(f"Borrando samples anteriores...")
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

sample_idx = 0
errors = 0

for voice_path in VOICES:
    voice_name = os.path.basename(voice_path).replace(".onnx", "")
    print(f"\n[{voice_name}]")

    for phrase in PHRASES:
        for length_scale in LENGTH_SCALES:
            output_path = os.path.join(OUTPUT_DIR, f"sample_{sample_idx:04d}.wav")

            result = subprocess.run(
                [PIPER_BIN, "--model", voice_path,
                 "--output_file", output_path,
                 "--length_scale", str(length_scale)],
                input=phrase.encode("utf-8"),
                capture_output=True,
            )

            if result.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path)
                print(f"  [{sample_idx:04d}] '{phrase}' scale={length_scale} → {size//1024}KB")
            else:
                print(f"  [{sample_idx:04d}] FALLO: '{phrase}' → {result.stderr.decode()[:80]}")
                errors += 1

            sample_idx += 1

print(f"\nCompletado: {sample_idx - errors}/{sample_idx} samples OK en {OUTPUT_DIR}")
