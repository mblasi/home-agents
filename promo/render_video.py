#!/usr/bin/env python3
"""Renderiza la animación de promo.py a MP4 (PIL + ffmpeg).

Texto/arte con DejaVuSansMono; emojis con NotoEmoji monocromático teñido.

Modos:
    python promo/render_video.py                 # mudo, 30 fps, 2x
    python promo/render_video.py --audio         # sincroniza la narración Piper
    python promo/render_video.py --fps 24 --scale 3
    python promo/render_video.py --out promo/capitan_promo
    python promo/render_video.py --gif           # también gif (lento)

--audio: lee promo/audio/manifest.json (generado por tts.py), estira cada escena
para que dure lo que su cue, ancla el audio y muxea. Estimar duración con tts.py
primero.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

import promo as P

BG = (12, 14, 20)
LEAD = 0.30   # silencio antes del cue dentro de la escena
TAIL = 0.45   # cola después del cue
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load_font(paths, size):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_blocks(with_audio, source=None):
    """Agrupa el timeline en bloques por escena. Si with_audio, estira el último
    frame de cada escena narrada y devuelve los cues (path, start_abs)."""
    manifest = {}
    if with_audio:
        with open(os.path.join(AUDIO_DIR, "manifest.json")) as f:
            for m in json.load(f):
                manifest[m["scene"]] = m

    blocks = []
    for sid, styled, hold in (source if source is not None else P.timeline()):
        if not blocks or blocks[-1]["sid"] != sid:
            blocks.append({"sid": sid, "frames": []})
        blocks[-1]["frames"].append([styled, hold])

    cues = []
    t = 0.0
    for b in blocks:
        dur = sum(h for _, h in b["frames"])
        cue = manifest.get(b["sid"])
        if cue:
            need = LEAD + cue["dur"] + TAIL
            if dur < need:
                b["frames"][-1][1] += need - dur
                dur = need
            cues.append((os.path.join(AUDIO_DIR, cue["id"] + ".wav"), t + LEAD))
        t += dur
    return blocks, cues, t


def render_audio(cues, total, dst, tmp):
    inputs = []
    for path, _ in cues:
        inputs += ["-i", path]
    filt = []
    for i, (_, start) in enumerate(cues):
        filt.append(f"[{i}:a]adelay={int(start*1000)}:all=1[a{i}]")
    mixins = "".join(f"[a{i}]" for i in range(len(cues)))
    # apad: rellena silencio hasta `total` para que el outro mudo (hardware) no
    # se corte por -shortest cuando el último cue termina antes del final.
    filt.append(f"{mixins}amix=inputs={len(cues)}:normalize=0:"
                f"dropout_transition=0,apad[mix]")
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt),
         "-map", "[mix]", "-t", f"{total:.3f}", "-ar", "22050", dst],
        check=True, stderr=subprocess.DEVNULL)


def main():
    fps = int(arg("--fps", "30"))
    scale = int(arg("--scale", "2"))
    out = arg("--out", "promo/capitan_promo")
    with_audio = "--audio" in sys.argv
    make_gif = "--gif" in sys.argv

    px = 16 * scale
    mono = load_font([
        "/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ], px)
    emoji = load_font([
        "/usr/share/fonts/noto-emoji/NotoEmoji-Bold.ttf",
        "/usr/share/fonts/noto-emoji/NotoEmoji-Medium.ttf",
    ], int(px * 0.92))

    cw = mono.getlength("M")
    bbox = mono.getbbox("Mg")
    ch = (bbox[3] - bbox[1]) + 9 * scale
    cols, rows = 92, 22
    W, H = int(cw * cols), int(ch * rows)

    source = P.proto_timeline() if "--proto" in sys.argv else None
    blocks, cues, total = build_blocks(with_audio and source is None, source)
    tmp = tempfile.mkdtemp(prefix="promo_frames_")
    print(f"render {W}x{H} @ {fps}fps · {total:.1f}s"
          + (f" · {len(cues)} cues" if with_audio else " · mudo"))

    def draw_seg(d, x, y, txt, rgb):
        for c in txt:
            f = emoji if c in P.EMOJI else mono
            d.text((x, y), c, font=f, fill=rgb)
            x += cw
        return x

    idx = 0
    for b in blocks:
        for styled, hold in b["frames"]:
            img = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(img)
            top = (rows - len(styled)) // 2
            for r, segs in enumerate(styled):
                x = (W - P.line_len(segs) * cw) / 2
                y = (top + r) * ch
                for txt, color in segs:
                    x = draw_seg(d, x, y, txt, P.PALETTE[color][1])
            for _ in range(max(1, round(hold * fps))):
                img.save(os.path.join(tmp, f"f{idx:05d}.png"))
                idx += 1
    print(f"{idx} frames")

    mp4 = f"{out}.mp4"
    os.makedirs(os.path.dirname(mp4) or ".", exist_ok=True)

    if with_audio:
        wav = os.path.join(tmp, "master.wav")
        render_audio(cues, total, wav, tmp)
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(fps), "-i",
             os.path.join(tmp, "f%05d.png"), "-i", wav,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-b:a", "192k", "-movflags", "+faststart", "-shortest", mp4],
            check=True, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", str(fps), "-i",
             os.path.join(tmp, "f%05d.png"), "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4],
            check=True, stderr=subprocess.DEVNULL)
    print(f"  {mp4}  ({os.path.getsize(mp4)/1024:.0f} KB)")

    if make_gif:
        gif = f"{out}.gif"
        gfps = min(fps, 15)
        pal = os.path.join(tmp, "pal.png")
        subprocess.run(["ffmpeg", "-y", "-i", mp4, "-vf",
                        f"fps={gfps},scale=iw/2:-1,palettegen", pal],
                       check=True, stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-y", "-i", mp4, "-i", pal, "-lavfi",
                        f"fps={gfps},scale=iw/2:-1[x];[x][1:v]paletteuse", gif],
                       check=True, stderr=subprocess.DEVNULL)
        print(f"  {gif}  ({os.path.getsize(gif)/1024:.0f} KB)")

    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
