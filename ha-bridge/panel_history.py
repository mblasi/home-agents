#!/usr/bin/env python3
"""Panel superior derecho: historial de comandos."""
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

def render(history: list) -> Panel:
    table = Table(box=None, show_header=True, header_style="bold dim",
                  expand=True, padding=(0, 1))
    table.add_column("Hora",      style="dim",          width=8,  no_wrap=True)
    table.add_column("Comando",   style="white",        ratio=2)
    table.add_column("Acción",    style="cyan",         ratio=2)
    table.add_column("Resp.",     style="bright_green", width=16, no_wrap=True)

    for e in reversed(history[-12:]):
        accion = e.get("accion") or "—"
        if accion and "→" in accion:
            accion = accion.split("→")[-1].strip()
        table.add_row(
            e.get("ts", ""),
            e.get("texto", ""),
            accion,
            e.get("respuesta", ""),
        )

    if not history:
        return Panel(
            Text("  Sin comandos aún...", style="dim italic", justify="center"),
            title="[bold]Historial[/bold]",
            border_style="dim",
        )
    return Panel(table, title="[bold]Historial[/bold]", border_style="blue")

with Live(console=console, refresh_per_second=2, screen=False) as live:
    while True:
        live.update(render(read_history()))
        time.sleep(0.5)
