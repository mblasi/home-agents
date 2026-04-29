#!/usr/bin/env python3
"""Panel inferior derecho: latencias del último comando y promedios de sesión."""
import json, time, os
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

METRICS_DIR = "/tmp/capitan"
console = Console()

def read_history():
    try:
        with open(os.path.join(METRICS_DIR, "history.json")) as f:
            return json.load(f)
    except Exception:
        return []

def lat_style(val: float) -> str:
    if val <= 0:   return "dim"
    if val < 3:    return "bright_green"
    if val < 6:    return "bright_yellow"
    return "bright_red"

def fmt(val: float) -> str:
    return f"{val:.1f}s" if val > 0 else "—"

def render(history: list) -> Panel:
    table = Table(box=None, show_header=False, expand=True, padding=(0, 2))
    table.add_column("Métrica", style="dim",   width=16)
    table.add_column("Último",  justify="right", width=10)
    table.add_column("Promedio", justify="right", width=10)

    if history:
        last   = history[-1]
        valids = [e for e in history if e.get("lat_total", 0) > 0]
        avg    = lambda k: sum(e.get(k,0) for e in valids) / len(valids) if valids else 0

        rows = [
            ("STT (Whisper)",  last.get("lat_stt",0),   avg("lat_stt")),
            ("LLM + HA",       last.get("lat_llm",0),   avg("lat_llm")),
            ("Total",          last.get("lat_total",0),  avg("lat_total")),
        ]
        for label, lval, aval in rows:
            table.add_row(
                label,
                Text(fmt(lval),  style=lat_style(lval)),
                Text(fmt(aval),  style=lat_style(aval)),
            )
        table.add_row("", "", "")
        table.add_row("Comandos", Text(str(len(history)), style="bold white"),
                      Text(f"sesión", style="dim"))
    else:
        table.add_row("Sin datos aún", "—", "—")

    return Panel(
        table,
        title="[bold]Latencias[/bold]",
        subtitle="[dim]último / promedio[/dim]",
        border_style="magenta",
    )

with Live(console=console, refresh_per_second=2, screen=False) as live:
    while True:
        live.update(render(read_history()))
        time.sleep(0.5)
