#!/usr/bin/env python3
"""
Loop principal del agente Capitán.

Escucha el micrófono continuamente. Cuando detecta la wake word "Capitán",
graba el comando y lo transcribe con faster-whisper.

Uso:
    source ~/ai-env/bin/activate
    python ha-bridge/listen.py
"""

import sys
import os
import time
import numpy as np
import pyaudio
import scipy.signal
from faster_whisper import WhisperModel
import openwakeword

sys.path.insert(0, os.path.dirname(__file__))
import agent
import tts

# ── Configuración ──────────────────────────────────────────────────────────────

MIC_DEVICE_NAME = "ALC256"    # buscar por nombre; fallback a índice 4
MIC_DEVICE_IDX  = 4
MIC_RATE        = 44100       # Única frecuencia soportada por ALC256
CHUNK_MS        = 80          # Chunk para openWakeWord (80ms = 1280 samples a 16kHz)
CHUNK_44K       = int(MIC_RATE * CHUNK_MS / 1000)   # ~3528 samples a 44100Hz
TARGET_RATE     = 16000
RESAMPLE_UP     = 160         # 44100 × 160/441 = 16000
RESAMPLE_DOWN   = 441

WAKEWORD_MODEL  = os.path.expanduser("~/.local/share/wakeword/capitan.onnx")
WAKEWORD_LABEL  = "capitan"
WAKEWORD_THRESH = 0.5

COMMAND_SECS    = 5           # segundos a grabar tras detección
WHISPER_MODEL   = "small"
WHISPER_DEVICE  = "cpu"
WHISPER_COMPUTE = "int8"

# ── Inicialización ─────────────────────────────────────────────────────────────

print("[init] Cargando wake word model...", flush=True)
oww = openwakeword.Model(
    wakeword_model_paths=[WAKEWORD_MODEL],
    vad_threshold=0,
)

print("[init] Cargando Whisper...", flush=True)
whisper = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)

print("[init] Abriendo micrófono...", flush=True)
pa = pyaudio.PyAudio()

def _find_mic(pa, name=MIC_DEVICE_NAME, fallback=MIC_DEVICE_IDX):
    for i in range(pa.get_device_count()):
        d = pa.get_device_info_by_index(i)
        if name in d["name"] and d["maxInputChannels"] > 0:
            print(f"[init]   → device {i}: {d['name']}", flush=True)
            return i
    n = pa.get_device_count()
    if fallback >= n:
        raise RuntimeError(
            f"Micrófono '{name}' no encontrado y fallback={fallback} inválido "
            f"(solo {n} dispositivos). ¿Está el micrófono en uso por otro proceso?"
        )
    print(f"[init]   → '{name}' no encontrado, usando índice {fallback}", flush=True)
    return fallback

mic_idx = _find_mic(pa)
stream = pa.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=MIC_RATE,
    input=True,
    input_device_index=mic_idx,
    frames_per_buffer=CHUNK_44K,
)

print(f"[ok] Escuchando... (umbral={WAKEWORD_THRESH}, di 'Capitán')\n", flush=True)


def resample_chunk(data_int16: np.ndarray) -> np.ndarray:
    """Resamplea de 44100Hz a 16000Hz."""
    f = scipy.signal.resample_poly(data_int16.astype(np.float32), RESAMPLE_UP, RESAMPLE_DOWN)
    return np.clip(f, -32768, 32767).astype(np.int16)


def record_command() -> np.ndarray:
    """Graba COMMAND_SECS segundos a 44100Hz y devuelve audio a 16000Hz."""
    n_chunks = int(COMMAND_SECS * MIC_RATE / CHUNK_44K)
    frames = []
    for _ in range(n_chunks):
        raw = stream.read(CHUNK_44K, exception_on_overflow=False)
        chunk = np.frombuffer(raw, dtype=np.int16)
        frames.append(resample_chunk(chunk))
    return np.concatenate(frames)


def transcribe(audio_16k: np.ndarray) -> str:
    """Transcribe audio int16 16kHz con faster-whisper."""
    audio_f32 = audio_16k.astype(np.float32) / 32768.0
    segments, _ = whisper.transcribe(audio_f32, language="es", beam_size=1)
    return " ".join(s.text.strip() for s in segments).strip()


# ── Loop principal ─────────────────────────────────────────────────────────────

try:
    while True:
        raw = stream.read(CHUNK_44K, exception_on_overflow=False)
        chunk_44k = np.frombuffer(raw, dtype=np.int16)
        chunk_16k = resample_chunk(chunk_44k)

        prediction = oww.predict(chunk_16k)
        score = prediction.get(WAKEWORD_LABEL, 0.0)

        if score > WAKEWORD_THRESH:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] ¡Capitán! (score={score:.2f}) — grabando {COMMAND_SECS}s...")

            audio = record_command()
            texto = transcribe(audio)

            if texto:
                print(f"[{ts}] → \"{texto}\"", flush=True)
                respuesta, accion = agent.process(texto)
                print(f"[{ts}]    acción: {accion}", flush=True)
                print(f"[{ts}]    respuesta: {respuesta}", flush=True)
                tts.say(respuesta)
            else:
                print(f"[{ts}] → (silencio)", flush=True)

            oww.reset()
            print()

except KeyboardInterrupt:
    print("\n[stop] Detenido.")
finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
