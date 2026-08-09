#!/usr/bin/env python3
"""Animación ASCII promo de home-agents — libreto completo (mudo).

Modelo de frames reusable: `frames()` produce (styled_lines, hold_seconds).
styled_line = lista de segmentos (texto, color). Lo consumen el player de
terminal (este archivo) y el renderer de video (render_video.py).

Escenas (ver promo/libreto.md):
  0 landing · 1 arquitectura · 2 agentes · 3 caso1 domótica
  4 caso2 agenda+clima · 5 caso3 goal/proactividad · 6 cierre

Uso terminal:
    python promo/promo.py            # loop
    python promo/promo.py --once
    python promo/promo.py --no-color
    python promo/promo.py --fps 14
NOTA: los emojis se ven bien en el VIDEO (fuente NotoEmoji teñida); en la
terminal pueden descentrar por el ancho doble. Validar con render_video.py.
"""
import sys
import time
import math
import shutil

# ---------- paleta (nombre -> ANSI 256, RGB) ----------
PALETTE = {
    "cyan":    (51,  (0, 255, 255)),
    "blue":    (39,  (0, 175, 255)),
    "green":   (48,  (0, 255, 135)),
    "yellow":  (227, (255, 235, 120)),
    "magenta": (201, (220, 120, 255)),
    "orange":  (214, (255, 175, 0)),
    "gray":    (245, (140, 140, 150)),
    "dim":     (240, (90, 92, 100)),
    "white":   (255, (235, 238, 245)),
    "red":     (203, (255, 95, 95)),
    None:      (255, (235, 238, 245)),
}
RESET, CLEAR, HIDE, SHOW = "\033[0m", "\033[2J\033[H", "\033[?25l", "\033[?25h"
EMOJI = set("☀🏠📈📅🛒🗺🎯🌧⏰🔔📍")

# ---------- arte ----------
LOGO = [
    "  _                                          _       ",
    " | |__   ___  _ __ ___   ___        __ _  __ _  ___ _ __ | |_ ___ ",
    " | '_ \\ / _ \\| '_ ` _ \\ / _ \\_____ / _` |/ _` |/ _ \\ '_ \\| __/ __|",
    " | | | | (_) | | | | | |  __/_____| (_| | (_| |  __/ | | | |_\\__ \\",
    " |_| |_|\\___/|_| |_| |_|\\___|      \\__,_|\\__, |\\___|_| |_|\\__|___/",
    "                                         |___/                    ",
]
MIC = ["   .-.   ", "  ( o )  ", "  ( o )  ", "   \\ /   ", "    |    ", "  __|__  "]
BULB_OFF = ["   ___   ", "  /   \\  ", " |     | ", " |     | ", "  \\___/  ", "  |___|  "]
BULB_ON  = ["  \\ | /  ", " - .-. - ", "  /   \\  ", " | ::: | ", "  \\:::/  ", "  |___|  "]

AGENTS = [
    ("☀", "clima", "yellow"),
    ("🏠", "domótica", "cyan"),
    ("📈", "inversiones", "green"),
    ("📅", "agenda", "blue"),
    ("🛒", "compras", "orange"),
    ("🗺", "mapas", "magenta"),
]


# ---------- helpers de frame ----------
def L(text, color=None):
    return [(text, color)]


def art(lines, color):
    return [[(l, color)] for l in lines]


def bar(value, width=28, c="green", track="dim"):
    filled = int(round(value * width))
    return [("█" * filled, c), ("░" * (width - filled), track)]


def line_len(segs):
    return sum(len(t) for t, _ in segs)


_VU_RAMP = ("red", "red", "orange", "orange", "yellow", "yellow", "green", "green")


def vu_segments(width, t, peak=1.0, level=0.0):
    """VU-meter rojo→verde. El color de cada barra depende de su altura y se
    sesga hacia el verde con `level` (score de detección): a más detección, todo
    el meter vira de rojo a verde."""
    glyph = "▁▂▃▄▅▆▇█"
    bias = int(round(level * 4))  # detección alta empuja la paleta a verde
    segs = []
    for i in range(width):
        h = (math.sin(t * 0.9 + i * 0.7) + math.sin(t * 0.4 + i * 0.3)) / 2
        h = max(0.0, min(1.0, (h + 1) / 2 * peak))
        idx = int(round(h * (len(glyph) - 1)))
        c = _VU_RAMP[max(0, min(len(_VU_RAMP) - 1, idx + bias))]
        segs.append((glyph[idx], c))
    return segs


def pad_block(rows):
    """Pad cada row a la longitud máxima → se centran como bloque (left-align)."""
    w = max(line_len(r) for r in rows)
    return [r + [(" " * (w - line_len(r)), None)] for r in rows]


def boxed(inner, color, width=30):
    """inner: lista de segment-lists. Devuelve styled_lines con marco."""
    out = [[("┌" + "─" * (width - 2) + "┐", color)]]
    for segs in inner:
        pad = max(0, width - 3 - line_len(segs))
        out.append([("│ ", color), *segs, (" " * pad, None), ("│", color)])
    out.append([("└" + "─" * (width - 2) + "┘", color)])
    return out


BLANK = []


# =================== escenas ===================
def scene_landing():
    for c, hold in [("dim", 0.18), ("blue", 0.18), ("cyan", 0.22), ("cyan", 0.45)]:
        yield [BLANK, BLANK, *art(LOGO, c), BLANK,
               L("una red de agentes de IA  ·  local-first", "gray")], hold
    tag = "tu voz · tu casa · tu red"
    for i in range(0, len(tag) + 1, 2):
        yield [BLANK, BLANK, *art(LOGO, "cyan"), BLANK,
               L(tag[:i] + "▌", "white")], 0.05
    yield [BLANK, BLANK, *art(LOGO, "cyan"), BLANK, L(tag, "white")], 0.8


def scene_arch():
    head = L("ARQUITECTURA", "gray")
    panels = [("comedor", "cyan"), ("cocina", "yellow"),
              ("dormitorio", "magenta"), ("living", "green")]
    row_names = [[(f"  {n:^10}", c) for n, c in panels][i] for i in range(4)]
    names = [seg for seg in row_names]
    panel_line = [seg for n, c in panels for seg in ((f"  {n:^9}", c),)]
    nspanel_line = [(f"  {'[NSPanel]':^9}", c) for n, c in panels]

    brain = [
        L("[ BRAIN · LAN local ]", "white"),
        L("┌──────────────────────┐", "blue"),
        [("│  ", "blue"), ("HAOS", "green"), ("   ·   ", "dim"),
         ("Ollama", "cyan"), ("  │", "blue")],
        [("│  ", "blue"), ("qwen2.5:7b · core", "gray"), ("   │", "blue")],
        L("└──────────────────────┘", "blue"),
    ]

    # build-up: paneles
    yield [BLANK, head, BLANK, panel_line, nspanel_line], 0.5
    yield [BLANK, head, BLANK, panel_line, nspanel_line,
           L("        \\      |      |      /", "dim")], 0.4
    # aparece el brain
    base = [BLANK, head, BLANK, panel_line, nspanel_line,
            L("        \\      |      |      /", "dim"),
            L("         '----> · <----'", "dim"), BLANK, *brain]
    yield base, 0.6
    # pulso request -> brain -> response
    for col, lbl in [("yellow", "→ pedido"), ("green", "← respuesta")]:
        f = [BLANK, head, BLANK, panel_line, nspanel_line,
             L("        \\      |      |      /", col),
             L("         '----> · <----'", col), BLANK, *brain,
             BLANK, L(lbl + "   ·   nada sale de la red", "gray")]
        yield f, 0.55


def scene_agents():
    yield [BLANK, L("LOS AGENTES", "gray")], 0.4
    grid_rows = [AGENTS[:3], AGENTS[3:]]
    shown = 0
    total = len(AGENTS)
    while shown < total:
        shown += 1
        body = [BLANK, L("LOS AGENTES", "gray"), BLANK]
        k = 0
        for row in grid_rows:
            segs = []
            for emo, name, c in row:
                if k < shown:
                    segs += [(f"  {emo} ", c), (f"{name:<12}", "white")]
                else:
                    segs += [(" " * 16, None)]
                k += 1
            body.append(segs)
            body.append(BLANK)
        yield body, 0.28
    # settle
    body = [BLANK, L("LOS AGENTES", "gray"), BLANK]
    for row in grid_rows:
        segs = []
        for emo, name, c in row:
            segs += [(f"  {emo} ", c), (f"{name:<12}", "white")]
        body.append(segs)
        body.append(BLANK)
    body.append(L("una red · no un asistente", "gray"))
    yield body, 1.0


def scene_wake(score, head_label):
    # VU-meter + score subiendo
    n = 18
    for i in range(n):
        t = i * 0.6
        v = (i / (n - 1)) * score
        peak = 0.4 + 0.6 * (i / (n - 1))
        body = [L(head_label, "dim"), BLANK,
                *art(MIC, "yellow"), BLANK,
                vu_segments(30, t, peak, level=v), BLANK,
                [("WAKE WORD  ", "magenta"), *bar(v, 24, "magenta")],
                L(f"score {v:0.2f}", "gray")]
        if v >= 0.8:
            body.append(L("DETECTADO · Capitán", "green"))
        yield body, 0.05
    yield body, 0.3


def scene_voiceid(extra=None):
    inner = [
        [("usuario   ", "gray"), ("Matías", "white"), ("   ", None), ("✓", "green")],
        [("match     ", "gray"), ("0.78", "cyan"), ("  > 0.60", "dim")],
    ]
    body = [BLANK, *boxed(inner, "green", 30), BLANK, L("voice-id", "gray")]
    if extra:
        body.append(L(extra, "dim"))
    yield body, 0.9


def scene_say(label, text, color="white", hold=0.04):
    for i in range(0, len(text) + 1, 2):
        yield [BLANK, L(label, "dim"), BLANK, L('"' + text[:i] + '"', color)], hold
    yield [BLANK, L(label, "dim"), BLANK, L('"' + text + '"', color)], 0.6


def scene_case1_action():
    for i in range(8):
        on = i % 2 == 0
        body = [L("🏠 domótica", "cyan"), BLANK,
                *art(BULB_ON if on else BULB_OFF, "yellow" if on else "dim"),
                BLANK, L("light.comedor → ON", "green"),
                L("climate.comedor → 23°", "green")]
        yield body, 0.12
    body = [L("🏠 domótica", "cyan"), BLANK, *art(BULB_ON, "yellow"), BLANK,
            L("✓ luz encendida · aire a 23°", "green")]
    yield body, 1.0


def scene_case2_collab():
    # agenda consulta a clima
    for i in range(6):
        lit = i >= 3
        body = [BLANK, L("ORQUESTACIÓN", "gray"), BLANK,
                [("  📅 agenda  ", "blue"),
                 ("──pregunta──▶", "yellow" if i % 2 else "dim"),
                 ("  ☀ clima  ", "yellow" if lit else "dim")]]
        yield body, 0.25
    # clima responde
    body = [BLANK, L("ORQUESTACIÓN", "gray"), BLANK,
            [("  📅 agenda  ", "blue"), ("──▶  ", "dim"), ("☀ clima", "yellow")],
            BLANK,
            [("  mañana 16h  ", "white"), ("🌧 lluvia", "blue")],
            [("  mañana 08h  ", "white"), ("☀ despejado", "yellow")]]
    yield body, 1.4
    # repregunta
    body = [BLANK, L("📅 agenda repregunta", "blue"), BLANK,
            L('"a la tarde dan lluvia.', "white"),
            L(' ¿te la agendo 8am que está despejado?"', "white")]
    yield body, 2.0


def scene_case2_done():
    inner = [
        [("📅 ", "blue"), ("corrida", "white")],
        [("   ", None), ("mañana 08:00", "cyan"), ("  ✓", "green")],
    ]
    body = [BLANK, L("agendado", "gray"), BLANK, *boxed(inner, "green", 30),
            BLANK, L("te aviso si cambia el tiempo", "dim")]
    yield body, 1.6


def scene_case3_goal():
    inner = [
        [("🎯 ", "magenta"), ("finde playa", "white")],
        [("   ", None), ("mes próximo · low-cost", "gray")],
        [("   estado: ", "dim"), ("abierto", "yellow")],
    ]
    yield [BLANK, L("OBJETIVO", "gray"), BLANK, *boxed(inner, "magenta", 32)], 1.6


def scene_case3_orch():
    branches = [
        ("📅 agenda", "blue", "finde libre: 18–19"),
        ("☀ clima", "yellow", "mejor ventana: 18, soleado"),
        ("🗺 mapas", "magenta", "2 destinos < 3h de auto"),
        ("📈 presupuesto", "green", "dentro del tope"),
    ]
    conn = ["┬", "├", "├", "└"]
    for lit in range(0, len(branches) + 1):
        rows = []
        for j, (name, c, res) in enumerate(branches):
            on = j < lit
            head = "  🎯 goal " if j == 0 else "          "
            rows.append([
                (head, "magenta" if j == 0 else None),
                (conn[j] + "─▶ ", "white" if on else "dim"),
                (f"{name:<14}", c if on else "dim"),
                (res, "white" if on else "dim"),
            ])
        body = [BLANK, L("ORQUESTACIÓN MULTI-AGENTE", "gray"), BLANK, *pad_block(rows)]
        yield body, 0.5
    yield body, 1.0


def scene_case3_proactive():
    # salto temporal
    for i in range(4):
        dots = "." * (i + 1)
        yield [BLANK, BLANK, L("⏰  más tarde" + dots, "gray")], 0.3
    # notificación proactiva
    inner = [
        [("🔔 ", "yellow"), ("propuesta proactiva", "white")],
        [("📍 ", "magenta"), ("La Pedrera", "white"), ("  18–19", "cyan")],
        [("☀ soleado   ", "yellow"), ("✓ presupuesto", "green")],
    ]
    body = [BLANK, *boxed(inner, "yellow", 34), BLANK,
            L('"te tengo algo. ¿reservo?"', "white")]
    yield body, 2.2


def scene_case3_done():
    checks = [
        "agenda 18–19 bloqueada",
        "recordatorio creado",
        "ruta guardada",
    ]
    for k in range(len(checks) + 1):
        rows = []
        for j, c in enumerate(checks):
            mark = "✓" if j < k else "·"
            col = "green" if j < k else "dim"
            rows.append([(f"   {mark} ", col), (c, "white" if j < k else "dim")])
        body = [BLANK, L("🎯 objetivo cumplido", "green"), BLANK, *pad_block(rows)]
        yield body, 0.4
    body.append(BLANK)
    body.append(L("todo coordinado · 100% local", "gray"))
    yield body, 1.6


def scene_close():
    for c in ["gray", "cyan", "cyan"]:
        yield [BLANK, BLANK, *art(LOGO, c), BLANK,
               L("entiende · coordina · se adelanta", "white")], 0.4
    yield [BLANK, BLANK, *art(LOGO, "cyan"), BLANK,
           L("tu voz · tu casa · tu red", "white"), BLANK,
           L("nada sale de tu red local", "gray")], 2.2


# =================== canvas 2D (escenas inmersivas) ===================
class Canvas:
    """Grilla de celdas (char,color). Dibujá elementos por coordenada y luego
    `rows()` los convierte en styled_lines (merge de runs del mismo color).
    Todas las filas tienen ancho w → se centran como bloque uniforme."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.g = [[(" ", None) for _ in range(w)] for _ in range(h)]

    def put(self, x, y, ch, color):
        if 0 <= y < self.h and 0 <= x < self.w:
            self.g[y][x] = (ch, color)

    def text(self, x, y, s, color):
        for i, ch in enumerate(s):
            self.put(x + i, y, ch, color)

    def box(self, x, y, w, h, color, title=None, tcol="white"):
        self.text(x, y, "╭" + "─" * (w - 2) + "╮", color)
        self.text(x, y + h - 1, "╰" + "─" * (w - 2) + "╯", color)
        for j in range(1, h - 1):
            self.put(x, y + j, "│", color)
            self.put(x + w - 1, y + j, "│", color)
        if title:
            self.text(x + 3, y, " " + title + " ", tcol)

    def rows(self):
        out = []
        for row in self.g:
            segs, buf, cur, has = [], "", None, False
            for ch, col in row:
                if has and col == cur:
                    buf += ch
                else:
                    if has:
                        segs.append((buf, cur))
                    buf, cur, has = ch, col, True
            if has:
                segs.append((buf, cur))
            out.append(segs)
        return out


def scene_room_case1():
    """Ambiente comedor: usuario + panel + lámpara + aire. El comando enciende
    la luz (ambiente vira de gris a cálido) y el aire (❄ 23°)."""
    temp = "23°"

    def frame(light, ac):
        cv = Canvas(54, 13)
        amb = "yellow" if light else "dim"
        cv.box(0, 0, 54, 13, amb, "comedor", "white" if light else "gray")
        # lámpara colgante (centro-izquierda)
        cv.put(18, 1, "|", amb)
        if light:
            cv.text(15, 2, "╲ ☀ ╱", "yellow")
            cv.text(14, 3, "· · · · ·", "yellow")
        else:
            cv.text(16, 2, "( )", "dim")
        # aire acondicionado (arriba derecha)
        accol = "cyan" if ac else "dim"
        cv.box(36, 1, 14, 3, accol)
        cv.text(38, 2, ("❄ " + temp + "  ≈≈") if ac else "apagado", accol)
        # panel NSPanel (pared izquierda)
        cv.box(3, 6, 12, 4, "cyan", "NSPanel", "cyan")
        cv.text(7, 8, "· ·", "cyan")
        # usuario (derecha)
        cv.text(43, 7, "('-')", "white")
        cv.text(43, 8, "/|\\", "white")
        cv.text(43, 9, "/ \\", "white")
        # mesa
        cv.text(5, 11, "▬▬▬▬▬▬▬▬", "orange" if light else "dim")
        return cv.rows()

    yield [L("caso 1 · domótica", "dim"), BLANK, *frame(False, False)], 1.0
    for _ in range(2):  # flicker de encendido
        yield [L("caso 1 · domótica", "dim"), BLANK, *frame(True, True)], 0.12
        yield [L("caso 1 · domótica", "dim"), BLANK, *frame(False, True)], 0.08
    body = [L("caso 1 · domótica", "dim"), BLANK, *frame(True, True), BLANK,
            L("light.comedor → ON   ·   climate → 23°", "green")]
    yield body, 1.6


def scene_calendar_case2():
    """Calendario del mes: resalta el día de mañana y agenda la corrida."""
    weeks = [
        ["", "", "1", "2", "3", "4", "5"],
        ["6", "7", "8", "9", "10", "11", "12"],
        ["13", "14", "15", "16", "17", "18", "19"],
        ["20", "21", "22", "23", "24", "25", "26"],
        ["27", "28", "29", "30", "31", "", ""],
    ]
    hi = "25"  # mañana (sábado)

    def frame(mark, chip):
        cv = Canvas(44, 11)
        cv.box(0, 0, 44, 11, "blue")
        cv.text(16, 0, " JULIO 2026 ", "white")
        cv.text(4, 2, "Lu Ma Mi Ju Vi Sá Do", "gray")
        for r, wk in enumerate(weeks):
            for c, d in enumerate(wk):
                x, y = 4 + c * 3, 3 + r
                if d == hi and mark:
                    cv.text(x - 1, y, f"[{d}]", "cyan")
                elif d:
                    cv.text(x, y, f"{d:>2}", "white")
        if chip:
            cv.text(4, 9, "✓ corrida · Sá 25 · 08:00", "green")
        return cv.rows()

    yield [L("📅 agenda", "blue"), BLANK, *frame(False, False)], 0.8
    yield [L("📅 agenda", "blue"), BLANK, *frame(True, False)], 1.0
    yield [L("📅 agenda", "blue"), BLANK, *frame(True, True)], 1.8


def scene_weather_case2():
    """Pronóstico de mañana: 08h soleado vs 16h lluvia (gotas animadas)."""
    def frame(i):
        cv = Canvas(46, 9)
        cv.box(0, 0, 46, 9, "gray", "pronóstico · mañana", "white")
        # mañana 08h — sol con rayos
        cv.text(7, 2, "08:00", "gray")
        cv.text(8, 3, "╲ | ╱", "yellow")
        cv.text(7, 4, "─ ☀ ─", "yellow")
        cv.text(8, 5, "╱ | ╲", "yellow")
        cv.text(6, 7, "despejado", "yellow")
        # tarde 16h — nube + lluvia
        cv.text(29, 2, "16:00", "gray")
        cv.text(29, 3, "☁☁☁☁", "blue")
        for dx in range(9):  # cortina de gotas
            yy = 4 + ((i + dx) % 3)
            cv.put(29 + dx, yy, "ʼ", "cyan")
        cv.text(31, 7, "lluvia", "blue")
        return cv.rows()

    for i in range(8):
        yield [L("☀ clima responde", "yellow"), BLANK, *frame(i)], 0.18
    yield [L("☀ clima responde", "yellow"), BLANK, *frame(0), BLANK,
           L("mejor ventana: 08:00", "green")], 1.4


def scene_brain_orbit():
    """El Brain en el centro y los agentes orbitando, encendiéndose por turno
    a medida que ejecutan (pulso de orquestación)."""
    pos = [
        (22, 0, "📅", "agenda", "blue"),
        (42, 2, "☀", "clima", "yellow"),
        (44, 7, "📈", "inversiones", "green"),
        (24, 11, "🛒", "compras", "orange"),
        (2, 7, "🗺", "mapas", "magenta"),
        (2, 2, "🏠", "domótica", "cyan"),
    ]

    bcx, bcy = 30, 7  # centro del brain

    def frame(active):
        cv = Canvas(60, 13)
        for i, (x, y, emo, name, col) in enumerate(pos):
            on = i in active
            if on:  # punto de pulso brain → agente
                cv.put((x + bcx) // 2, (y + bcy) // 2, "·", col)
            cv.text(x, y, f"{emo} {name}", col if on else "dim")
        cv.box(23, 5, 14, 4, "white")
        cv.text(26, 6, "BRAIN", "white")
        cv.text(25, 7, "qwen2.5", "gray")
        return cv.rows()

    for k in range(len(pos) + 1):
        yield [L("EL BRAIN ORQUESTA", "gray"), BLANK, *frame(set(range(k)))], 0.32
    yield [L("EL BRAIN ORQUESTA", "gray"), BLANK, *frame(set(range(len(pos)))),
           BLANK, L("6 agentes · 1 objetivo · 100% local", "gray")], 1.4


def scene_hardware():
    """Sección técnica: hardware + stack + arquitectura (reveal por líneas)."""
    rows = [
        [("HARDWARE", "cyan")],
        [("  Brain    ", "gray"), ("Beelink SER9 · Ryzen 7 255 · 27 GiB", "white")],
        [("           ", "gray"), ("Radeon 780M (RDNA3) · ROCm", "white")],
        [("  Nodos    ", "gray"), ("NSPanel Pro · PX30 · mic+parlante · Termux", "white")],
        [("", None)],
        [("STACK", "magenta")],
        [("  LLM      ", "gray"), ("qwen2.5:7b · Ollama (iGPU/ROCm)", "white")],
        [("  STT      ", "gray"), ("faster-whisper small · int8", "white")],
        [("  TTS      ", "gray"), ("Piper · es_AR-daniela", "white")],
        [("  Wake     ", "gray"), ("openWakeWord (modelo propio)", "white")],
        [("  Home     ", "gray"), ("Home Assistant OS · REST", "white")],
        [("  Core     ", "gray"), ("FastAPI · Python", "white")],
        [("", None)],
        [("ARQUITECTURA", "yellow")],
        [("  ", "gray"), ("panel → Brain (LAN) → HAOS · sin nube", "white")],
    ]
    for k in range(1, len(rows) + 1):
        yield [BLANK, *pad_block(rows[:k])], 0.22
    yield [BLANK, *pad_block(rows)], 1.8


def proto_timeline():
    """Sólo las escenas inmersivas nuevas — para validar el lenguaje visual."""
    protos = [
        ("room", scene_room_case1()),
        ("calendar", scene_calendar_case2()),
        ("weather", scene_weather_case2()),
        ("brain", scene_brain_orbit()),
        ("hardware", scene_hardware()),
    ]
    for sid, gen in protos:
        for styled, hold in gen:
            yield sid, styled, hold * SPEED


# ---------- composición ----------
SPEED = 1.5  # 50% más lento (afecta terminal y video)


def _scenes():
    """Yield (scene_id, generador). El scene_id ancla los cues de audio
    (ver promo/tts.py SCRIPT, columna 'escena')."""
    yield "landing", scene_landing()
    yield "arch", scene_arch()
    yield "agents", scene_agents()
    # CASO 1 — esquema + escena inmersiva (la habitación narra la respuesta)
    yield "c1_wake", scene_wake(0.91, "caso 1 · domótica")
    yield "c1_vid", scene_voiceid()
    yield "c1_say", scene_say("pedido", "Capitán, prendé la luz del comedor y poné el aire en 23")
    yield "c1_action", scene_case1_action()
    yield "room", scene_room_case1()
    # CASO 2 — colab + clima (narra repregunta) + calendario (narra agendado)
    yield "c2_wake", scene_wake(0.93, "caso 2 · agenda + clima")
    yield "c2_vid", scene_voiceid()
    yield "c2_say", scene_say("pedido", "agendame una corrida para mañana a la tarde")
    yield "c2_collab", scene_case2_collab()
    yield "weather", scene_weather_case2()
    yield "c2_ok", scene_say("usuario", "dale", "white")
    yield "c2_done", scene_case2_done()
    yield "calendar", scene_calendar_case2()
    # CASO 3 — grafo + brain-orbit (narra la orquestación)
    yield "c3_wake", scene_wake(0.95, "caso 3 · objetivo complejo")
    yield "c3_vid", scene_voiceid()
    yield "c3_say", scene_say("pedido", "quiero escaparme un finde a la playa el mes que viene, algo tranqui y barato")
    yield "c3_goal", scene_case3_goal()
    yield "c3_orch", scene_case3_orch()
    yield "brain", scene_brain_orbit()
    yield "c3_pro", scene_case3_proactive()
    yield "c3_ok", scene_say("usuario", "reservá", "white")
    yield "c3_done", scene_case3_done()
    # CIERRE
    yield "close", scene_close()
    # OUTRO técnico (ficha hardware + stack + arquitectura)
    yield "hardware", scene_hardware()


def timeline():
    """Yield (scene_id, styled, hold) con SPEED aplicado."""
    for sid, gen in _scenes():
        for styled, hold in gen:
            yield sid, styled, hold * SPEED


def frames():
    for _sid, styled, hold in timeline():
        yield styled, hold


# ---------- player de terminal ----------
def _ansi(segs, no_color):
    out = []
    for txt, color in segs:
        if no_color or color is None:
            out.append(txt)
        else:
            out.append(f"\033[38;5;{PALETTE[color][0]}m{txt}{RESET}")
    return "".join(out)


def play():
    no_color = "--no-color" in sys.argv
    once = "--once" in sys.argv
    fps = 14
    if "--fps" in sys.argv:
        fps = int(sys.argv[sys.argv.index("--fps") + 1])
    width = shutil.get_terminal_size((86, 26)).columns

    if not no_color:
        sys.stdout.write(HIDE)
    try:
        while True:
            for styled, hold in frames():
                buf = [CLEAR if not no_color else "\n"]
                for segs in styled:
                    raw = _ansi(segs, no_color)
                    pad = max(0, (width - line_len(segs)) // 2)
                    buf.append(" " * pad + raw + "\n")
                sys.stdout.write("".join(buf))
                sys.stdout.flush()
                time.sleep(hold)
            if once:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if not no_color:
            sys.stdout.write(SHOW + RESET + "\n")


if __name__ == "__main__":
    play()
