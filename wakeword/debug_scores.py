#!/usr/bin/env python3
"""
Muestra el score del wake word en tiempo real.
Hablá "Capitán" repetidamente para ver qué score genera tu voz.
Ctrl+C para salir.
"""
import os, sys, numpy as np, pyaudio, scipy.signal, openwakeword

MIC_DEVICE_IDX = 4
MIC_RATE       = 44100
CHUNK_44K      = int(MIC_RATE * 80 / 1000)  # 80ms
RESAMPLE_UP    = 160
RESAMPLE_DOWN  = 441

oww = openwakeword.Model(
    wakeword_model_paths=[os.path.expanduser("~/.local/share/wakeword/capitan.onnx")],
    vad_threshold=0,
)

pa = pyaudio.PyAudio()
stream = pa.open(format=pyaudio.paInt16, channels=1, rate=MIC_RATE,
                 input=True, input_device_index=MIC_DEVICE_IDX,
                 frames_per_buffer=CHUNK_44K)

print("Escuchando scores... decí 'Capitán' varias veces. Ctrl+C para salir.\n", flush=True)

max_score = 0.0
try:
    while True:
        raw = stream.read(CHUNK_44K, exception_on_overflow=False)
        chunk = np.frombuffer(raw, dtype=np.int16)
        chunk_16k = np.clip(
            scipy.signal.resample_poly(chunk.astype(np.float32), RESAMPLE_UP, RESAMPLE_DOWN),
            -32768, 32767
        ).astype(np.int16)

        pred = oww.predict(chunk_16k)
        score = pred.get("capitan", 0.0)

        if score > 0.05:
            bar = "█" * int(score * 30)
            print(f"  {score:.3f} {bar}", flush=True)
            if score > max_score:
                max_score = score

except KeyboardInterrupt:
    print(f"\nScore máximo observado: {max_score:.3f}")
finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
