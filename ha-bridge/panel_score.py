#!/usr/bin/env python3
"""Panel izquierdo: score del wake word en tiempo real + estado."""
import json, time, os, sys
from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

METRICS_DIR = "/tmp/capitan"
console = Console()

STATES = {
    "init":       ("⏳", "yellow",  "Inicializando..."),
    "listening":  ("👂", "green",   "Escuchando"),
    "triggered":  ("🎯", "cyan",    "¡Wake word!"),
    "recording":  ("⏺ ", "red",     "Grabando comando..."),
    "processing": ("⚙ ", "yellow",  "Procesando..."),
    "speaking":   ("🔊", "blue",    "Respondiendo..."),
    "stopped":    ("⛔", "dim",     "Detenido"),
}

BAR_WIDTH = 30

def read_json(name, default):
    try:
        with open(os.path.join(METRICS_DIR, name)) as f:
            return json.load(f)
    except Exception:
        return default

def score_bar(score: float) -> Text:
    filled = int(score * BAR_WIDTH)
    empty  = BAR_WIDTH - filled
    color  = "bright_red" if score > 0.8 else "bright_yellow" if score > 0.4 else "bright_black"
    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * empty,  style="bright_black")
    bar.append(f"  {score:.3f}", style="bold " + color)
    return bar

def render(score_data, state_data) -> Panel:
    score  = score_data.get("score", 0.0)
    state  = state_data.get("state", "listening")
    icon, color, label = STATES.get(state, ("?", "white", state))

    content = Text(justify="center")
    content.append(f"\n{icon}  {label}\n\n", style=f"bold {color}")
    content.append("  Wake word score\n", style="dim")
    content.append("  ")
    content.append_text(score_bar(score))
    content.append(f"\n\n  umbral: 0.800\n", style="dim")
    if state == "recording":
        content.append("\n  🎙  grabando...\n", style="bold red blink")
    elif state == "processing":
        content.append("\n  ⚙  STT → LLM → HA...\n", style="bold yellow")
    elif state == "speaking":
        content.append("\n  🔊  reproduciendo TTS...\n", style="bold blue")

    return Panel(
        Align.center(content, vertical="middle"),
        title="[bold cyan]Capitán[/bold cyan]",
        border_style=color,
        height=14,
    )

with Live(console=console, refresh_per_second=12, screen=False) as live:
    while True:
        score_data = read_json("score.json", {"score": 0.0})
        state_data = read_json("state.json", {"state": "listening"})
        live.update(render(score_data, state_data))
        time.sleep(0.08)
