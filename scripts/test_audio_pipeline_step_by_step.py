# ~/ai-lab/scripts/test_audio_step_by_step.py

import subprocess
import sys

def test_step(name, func):
    print(f"\n{'─'*40}")
    print(f"TEST: {name}")
    print('─'*40)
    try:
        func()
        print(f"✓ OK")
        return True
    except Exception as e:
        print(f"✗ FALLÓ: {e}")
        return False

# ── Test 1: PortAudio disponible en el sistema ──
def test_portaudio_lib():
    import ctypes
    ctypes.cdll.LoadLibrary("libportaudio.so.2")
    print("  libportaudio.so.2 encontrada")

# ── Test 2: sounddevice importa ──
def test_sounddevice_import():
    import sounddevice as sd
    print(f"  sounddevice versión: {sd.__version__}")
    devices = sd.query_devices()
    print(f"  Dispositivos encontrados: {len(devices)}")

# ── Test 3: Listar dispositivos ──
def test_list_devices():
    import sounddevice as sd
    print("\n  Dispositivos de INPUT:")
    for i, dev in enumerate(sd.query_devices()):
        if dev['max_input_channels'] > 0:
            print(f"    [{i}] {dev['name']}")
            print(f"        channels={dev['max_input_channels']}, "
                  f"samplerate={dev['default_samplerate']}")
    
    print("\n  Dispositivos de OUTPUT:")
    for i, dev in enumerate(sd.query_devices()):
        if dev['max_output_channels'] > 0:
            print(f"    [{i}] {dev['name']}")

# ── Test 4: Grabar 2 segundos ──
def test_record():
    import sounddevice as sd
    import numpy as np
    
    duration = 2
    sample_rate = 16000
    
    print(f"  Grabando {duration}s... hablá algo")
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype='int16',
        device=None,  # device por defecto
    )
    sd.wait()
    
    # Verificar que no es silencio
    max_amplitude = np.abs(audio).max()
    rms = np.sqrt(np.mean(audio.astype(float)**2))
    
    print(f"  Amplitud máxima: {max_amplitude}")
    print(f"  RMS: {rms:.1f}")
    
    if max_amplitude < 100:
        print("  ⚠ SEÑAL MUY BAJA - micrófono puede estar mudo o volumen muy bajo")
    elif max_amplitude < 1000:
        print("  ⚠ Señal baja - subir volumen del micrófono")
    else:
        print("  ✓ Señal OK")
    
    return audio, sample_rate

# ── Test 5: Guardar y reproducir ──
def test_record_and_play():
    import sounddevice as sd
    import numpy as np
    import wave, tempfile, os
    
    audio, sr = test_record()
    
    # Guardar
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(tmp.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())
    
    print(f"  Guardado en {tmp.name}")
    print("  Reproduciendo...")
    
    # Reproducir con paplay (no necesita portaudio)
    subprocess.run(['paplay', tmp.name])
    os.unlink(tmp.name)
    print("  ¿Se escuchó tu voz?")

# ── Test 6: Whisper ──
def test_whisper():
    import whisper
    import sounddevice as sd
    import numpy as np
    import tempfile, wave, os
    
    print("  Cargando Whisper tiny (test rápido)...")
    model = whisper.load_model("tiny", device="cpu")
    
    duration = 4
    sr = 16000
    print(f"  Grabando {duration}s - decí algo en español...")
    
    audio = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='int16')
    sd.wait()
    
    # Guardar temporal
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(tmp.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())
    
    result = model.transcribe(tmp.name, language="es", fp16=False)
    os.unlink(tmp.name)
    
    print(f"  Whisper escuchó: '{result['text'].strip()}'")
    print(f"  Idioma detectado: {result['language']}")

# ── Correr todos los tests ──
tests = [
    ("PortAudio library",     test_portaudio_lib),
    ("sounddevice import",    test_sounddevice_import),
    ("Listar dispositivos",   test_list_devices),
    ("Grabar audio",          test_record_and_play),
    ("Whisper STT",           test_whisper),
]

results = []
for name, func in tests:
    ok = test_step(name, func)
    results.append((name, ok))
    if not ok:
        print(f"\n⚠ Falló '{name}', corregir antes de continuar")
        break

print(f"\n{'='*40}")
print("RESUMEN:")
for name, ok in results:
    print(f"  {'✓' if ok else '✗'} {name}")
