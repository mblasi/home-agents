# test_audio_pipeline.py
# Probar cada componente del audio por separado

import sounddevice as sd
import soundfile as sf
import numpy as np
import time
import subprocess
import tempfile
import os

SAMPLE_RATE = 16000
CHANNELS = 1

def test_recording(duration=3):
    """Test 1: Grabar con sounddevice"""
    print(f"\n[TEST 1] Grabando {duration}s... hablá algo")
    
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16',
    )
    sd.wait()  # esperar que termine
    
    # Verificar que hay señal (no silencio)
    rms = np.sqrt(np.mean(audio.astype(float)**2))
    print(f"  RMS (volumen): {rms:.1f} (mínimo útil: ~200, bueno: >500)")
    
    if rms < 100:
        print("  ⚠ MUY BAJO - revisar volumen del micrófono")
    elif rms < 300:
        print("  ⚠ BAJO - puede afectar transcripción")
    else:
        print("  ✓ Nivel de audio OK")
    
    # Guardar para inspección
    sf.write('/tmp/test_recording.wav', audio, SAMPLE_RATE)
    print(f"  Guardado en /tmp/test_recording.wav")
    return audio, rms

def test_whisper(audio_path='/tmp/test_recording.wav'):
    """Test 2: Transcribir con Whisper"""
    print("\n[TEST 2] Transcribiendo con Whisper...")
    
    import whisper
    
    # Cargar modelo (la primera vez descarga ~244MB para 'small')
    print("  Cargando modelo 'small'...")
    start = time.time()
    model = whisper.load_model("small", device="cpu")
    load_time = time.time() - start
    print(f"  Modelo cargado en {load_time:.1f}s")
    
    start = time.time()
    result = model.transcribe(
        audio_path,
        language="es",
        fp16=False,
        temperature=0.0,
        initial_prompt="Comando para casa inteligente.",
    )
    transcribe_time = time.time() - start
    
    print(f"  Texto: '{result['text'].strip()}'")
    print(f"  Tiempo: {transcribe_time:.1f}s")
    print(f"  Probabilidad de idioma: {result.get('language', '?')}")
    
    return result['text'].strip()

def test_piper(text="Las luces del living están encendidas"):
    """Test 3: TTS con Piper"""
    print(f"\n[TEST 3] TTS con Piper: '{text}'")
    
    piper_bin = os.path.expanduser("~/.local/bin/piper")
    voice_path = os.path.expanduser("~/.local/share/piper/es_ES-mls-high.onnx")
    
    if not os.path.exists(piper_bin):
        print("  ✗ Piper no encontrado")
        return False
    if not os.path.exists(voice_path):
        print("  ✗ Voz no encontrada")
        return False
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp_path = f.name
    
    start = time.time()
    
    # Piper → WAV file
    result = subprocess.run(
        [piper_bin, "--model", voice_path, "--output_file", tmp_path],
        input=text.encode(),
        capture_output=True,
        timeout=30,
    )
    
    gen_time = time.time() - start
    
    if result.returncode != 0:
        print(f"  ✗ Error: {result.stderr.decode()}")
        return False
    
    file_size = os.path.getsize(tmp_path)
    print(f"  Generado en {gen_time:.2f}s ({file_size} bytes)")
    
    # Reproducir con paplay (PulseAudio compat layer de PipeWire)
    subprocess.run(["paplay", tmp_path], check=True)
    os.unlink(tmp_path)
    
    print("  ✓ TTS OK")
    return True

def test_full_pipeline():
    """Test 4: Pipeline completo grab→transcribe→tts"""
    print("\n[TEST 4] Pipeline completo")
    print("  Decí un comando de domótica...")
    
    audio, rms = test_recording(duration=4)
    
    if rms < 100:
        print("  Abortando - nivel de audio demasiado bajo")
        return
    
    text = test_whisper('/tmp/test_recording.wav')
    
    if text:
        response = f"Entendí: {text}"
        test_piper(response)
    else:
        print("  No se detectó texto")

if __name__ == "__main__":
    print("=== Test del Pipeline de Audio ===")
    print(f"Dispositivo input:  {sd.query_devices(sd.default.device[0])['name']}")
    print(f"Dispositivo output: {sd.query_devices(sd.default.device[1])['name']}")
    
    # Correr tests secuencialmente
    audio, rms = test_recording()
    
    if rms > 100:
        text = test_whisper()
        test_piper()
        
        input("\nPresioná Enter para el pipeline completo...")
        test_full_pipeline()
    else:
        print("\nArreglá el volumen del micrófono antes de continuar")
        print("Ejecutar: pavucontrol")
