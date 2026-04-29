#!/usr/bin/env python3
"""Panel flotante: agentes disponibles, agente activo y fuente del pedido."""
import json, time, os
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

METRICS_DIR = "/tmp/capitan"
console = Console()

REGISTRY = {
    "haos":        {"name": "Domótica",   "icon": "🏠", "desc": "Luces, temperatura, electrodomésticos"},
    "clima":       {"name": "Clima",      "icon": "🌤", "desc": "Pronóstico del tiempo"},
    "agenda":      {"name": "Agenda",     "icon": "📅", "desc": "Calendario y recordatorios"},
    "inversiones": {"name": "Inversiones","icon": "📈", "desc": "Portfolio y cotizaciones"},
    "viajes":      {"name": "Viajes",     "icon": "✈️",  "desc": "Vuelos y reservas"},
}

SOURCE_ICONS = {
    "mic":      "🎙",
    "whatsapp": "💬",
    "api":      "🔌",
}

def read_json(name, default):
    try:
        with open(os.path.join(METRICS_DIR, name)) as f:
            return json.load(f)
    except Exception:
        return default

def render(active_data, history) -> Panel:
    active_id = active_data.get("agent", "")
    active_ts  = active_data.get("ts", 0)
    age = time.time() - active_ts if active_ts else 9999

    # ── Tabla de agentes ──────────────────────────────────────────────────
    table = Table(box=None, show_header=False, expand=True, padding=(0, 1))
    table.add_column("", width=3, no_wrap=True)
    table.add_column("Agente", style="white", ratio=1)
    table.add_column("", ratio=2, style="dim")

    for agent_id, info in REGISTRY.items():
        is_active = (agent_id == active_id and age < 30)
        if is_active:
            row_style = "bold bright_cyan"
            marker    = "▶"
        else:
            row_style = "dim"
            marker    = " "
        table.add_row(
            Text(marker, style=row_style),
            Text(f"{info['icon']} {info['name']}", style=row_style),
            Text(info["desc"], style="dim"),
        )

    # ── Fuente del último pedido ──────────────────────────────────────────
    source_line = Text()
    if history:
        last = history[-1]
        src  = last.get("source") or {}
        stype = src.get("type", "mic")
        room  = src.get("room", "")
        icon  = SOURCE_ICONS.get(stype, "❓")
        source_line.append(f"\n  {icon}  Origen: ", style="dim")
        source_line.append(f"{stype}", style="white")
        if room:
            source_line.append(f"  /  {room}", style="cyan")
        ts = last.get("ts", "")
        if ts:
            source_line.append(f"  [{ts}]", style="dim")
    else:
        source_line.append("\n  Sin pedidos aún", style="dim italic")

    content = Text()
    content.append_text(source_line)

    title_agent = f"[bold cyan]{REGISTRY[active_id]['name']}[/bold cyan]" if active_id in REGISTRY and age < 30 else "[dim]—[/dim]"
    title = f"[bold]Agentes[/bold]  ·  activo: {title_agent}"

    from rich.console import Group
    return Panel(
        Group(table, content),
        title=title,
        border_style="cyan" if (active_id and age < 30) else "dim",
    )

with Live(console=console, refresh_per_second=2, screen=False) as live:
    while True:
        active  = read_json("active_agent.json", {})
        history = read_json("history.json", [])
        live.update(render(active, history))
        time.sleep(0.5)
