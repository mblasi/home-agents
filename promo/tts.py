#!/usr/bin/env python3
"""Genera los WAV de narración del promo con Piper y reporta duraciones.

Voces:
  daniela = es_AR-daniela-high  (narrador, voz del producto)
  davefx  = es_ES-davefx-medium (usuario)

Cada cue se asocia a una escena (clave SCENE) para el sync posterior.
Salida: promo/audio/<id>.wav  +  promo/audio/manifest.json

Uso:
    python promo/tts.py            # genera los que faltan
    python promo/tts.py --force    # regenera todos
"""
import json
import os
import subprocess
import sys
import wave

HOME = os.path.expanduser("~")
PIPER = f"{HOME}/.local/bin/piper/piper"
VOICES = f"{HOME}/.local/share/piper"
MODELS = {
    "daniela": f"{VOICES}/es_AR-daniela-high.onnx",
    "davefx": f"{VOICES}/es_ES-davefx-medium.onnx",
}
OUT = os.path.join(os.path.dirname(__file__), "audio")

# (id, escena, voz, texto)
SCRIPT = [
    ("00_landing", "landing", "daniela",
     "Una red de agentes de inteligencia artificial, viviendo en tu casa. "
     "Sin nube. Sin que nada salga de tu red."),
    ("01_arch", "arch", "daniela",
     "En cada ambiente, un panel te escucha. Todos hablan con el Brain: un "
     "servidor chico, en tu casa, que corre Home Assistant y los modelos de "
     "lenguaje. La nube no participa."),
    ("02_agents", "agents", "daniela",
     "Adentro vive una red de agentes especializados: clima, domótica, agenda, "
     "inversiones, compras, mapas. Cada uno sabe lo suyo. Y colaboran entre ellos."),
    # caso 1
    ("10_c1_user", "c1_say", "davefx",
     "Capitán, prendé la luz del comedor y poné el aire en veintitrés."),
    ("11_c1_resp", "room", "daniela",
     "Listo. Luz del comedor encendida y aire a veintitrés grados."),
    # caso 2
    ("20_c2_user", "c2_say", "davefx",
     "Agendame una corrida para mañana a la tarde."),
    ("21_c2_ask", "weather", "daniela",
     "Mañana a la tarde dan lluvia. Tenés la mañana despejada, "
     "¿te la agendo a las ocho?"),
    ("22_c2_ok", "c2_ok", "davefx", "Dale."),
    ("23_c2_done", "calendar", "daniela",
     "Listo, corrida mañana a las ocho. Te aviso si cambia el tiempo."),
    # caso 3
    ("30_c3_user", "c3_say", "davefx",
     "Capitán, quiero escaparme un finde a la playa el mes que viene, "
     "algo tranqui y que no se me dispare el presupuesto."),
    ("31_c3_orch", "brain", "daniela",
     "Lo voy resolviendo. Cruzo tu agenda, el pronóstico, las rutas y el presupuesto."),
    ("32_c3_pro", "c3_pro", "daniela",
     "Te tengo algo. El finde del dieciocho está libre y va a estar soleado. "
     "La Pedrera te queda a dos horas y entra en presupuesto. ¿Reservo?"),
    ("33_c3_ok", "c3_ok", "davefx", "Reservá."),
    ("34_c3_done", "c3_done", "daniela",
     "Reservado. Te bloqueé la agenda y te guardé la ruta. Buen finde."),
    # cierre
    ("40_close", "close", "daniela",
     "Una red de agentes que entiende, coordina y se adelanta. En tu casa. Tuya."),
]


def wav_duration(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for cid, scene, voice, text in SCRIPT:
        path = os.path.join(OUT, f"{cid}.wav")
        if force or not os.path.exists(path):
            subprocess.run(
                [PIPER, "--model", MODELS[voice], "--output_file", path],
                input=text.encode("utf-8"), check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        dur = wav_duration(path)
        manifest.append({"id": cid, "scene": scene, "voice": voice,
                         "dur": round(dur, 3), "text": text})
        print(f"  {cid:12} {voice:8} {dur:5.2f}s  {scene}")

    total = sum(m["dur"] for m in manifest)
    print(f"\ntotal narración: {total:.1f}s  ({len(manifest)} cues)")
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
