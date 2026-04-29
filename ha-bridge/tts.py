#!/usr/bin/env python3
"""
Síntesis de voz con Piper → reproducción con ffplay.
Voz: es_AR-daniela-high (22050Hz)
"""

import subprocess
import tempfile
import os

PIPER = os.path.expanduser("~/.local/bin/piper/piper")
MODEL = os.path.expanduser("~/.local/share/piper/es_AR-daniela-high.onnx")


def say(text: str) -> None:
    """Sintetiza text y lo reproduce de forma bloqueante."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    try:
        subprocess.run(
            [PIPER, "--model", MODEL, "--output_file", wav_path],
            input=text.encode(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        subprocess.run(
            ["ffplay", "-autoexit", "-nodisp", wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    finally:
        os.unlink(wav_path)


if __name__ == "__main__":
    say("Listo, encendido.")
    say("No encontré ninguna acción para ese comando.")
