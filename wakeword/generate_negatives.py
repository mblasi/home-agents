import subprocess
import os
import shutil

PIPER_BIN  = os.path.expanduser("~/.local/bin/piper/piper")
OUTPUT_DIR = os.path.expanduser("~/ai-lab/wakeword/data/capitán/negative")

VOICES = [
    os.path.expanduser("~/.local/share/piper/es_AR-daniela-high.onnx"),
    os.path.expanduser("~/.local/share/piper/es_MX-claude-high.onnx"),
    os.path.expanduser("~/.local/share/piper/es_ES-davefx-medium.onnx"),
    os.path.expanduser("~/.local/share/piper/es_ES-sharvard-medium.onnx"),
]

# Hard negatives: fonéticamente similares a "Capitán"
PHRASES_HARD = [
    "Capítulo",
    "Capitolio",
    "Capitular",
    "Capitana",
    "Capital",
    "El capitán",
    "Un capitán",
    "Mi capitán",
    "Buen capitán",
    "Ese capitán",
]

# Comandos del hogar que NO son el wake word
PHRASES_COMMANDS = [
    "Encendé las luces",
    "Apagá todo",
    "Qué temperatura hay",
    "Cerrá las persianas",
    "Subí el volumen",
    "Bajá la calefacción",
    "Abrí la puerta",
    "Apagá la tele",
    "Poné música",
    "Cuánto es la temperatura",
]

# Conversación cotidiana
PHRASES_CASUAL = [
    "Buenas tardes",
    "Cómo estás",
    "Qué hora es",
    "Hasta luego",
    "Muchas gracias",
    "Por favor",
    "Está bien",
    "No sé",
    "Claro que sí",
    "Más o menos",
    "Qué tal el día",
    "Todo tranquilo",
    "Voy en un momento",
    "Ya vengo",
    "Esperate un segundo",
]

# Números y datos
PHRASES_DATA = [
    "Son las tres de la tarde",
    "Mañana es martes",
    "Hace veinte grados",
    "Son las ocho y media",
    "El lunes a las diez",
    "Treinta y dos grados",
    "Faltan cinco minutos",
    "Son las doce del mediodía",
    "Ayer fue domingo",
    "Esta semana llueve",
]

# Palabras sueltas y frases cortas (variedad de duración)
PHRASES_SHORT = [
    "Sí",
    "No",
    "Bien",
    "Ahora",
    "Después",
    "Espera",
    "Listo",
    "Dale",
    "Bueno",
    "Vamos",
]

ALL_PHRASES = (
    PHRASES_HARD +
    PHRASES_COMMANDS +
    PHRASES_CASUAL +
    PHRASES_DATA +
    PHRASES_SHORT
)

LENGTH_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]

total = len(VOICES) * len(ALL_PHRASES) * len(LENGTH_SCALES)
print(f"Generando {total} samples negativos en {OUTPUT_DIR}")
print(f"  {len(ALL_PHRASES)} frases × {len(LENGTH_SCALES)} velocidades × {len(VOICES)} voces")
print(f"  Borrando samples anteriores...")

if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

sample_idx = 0
errors = 0

for voice_path in VOICES:
    voice_name = os.path.basename(voice_path).replace(".onnx", "")
    print(f"\n[{voice_name}]")

    for phrase in ALL_PHRASES:
        for length_scale in LENGTH_SCALES:
            output_path = os.path.join(OUTPUT_DIR, f"neg_{sample_idx:04d}.wav")

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
