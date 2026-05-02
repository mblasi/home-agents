#!/usr/bin/env python3
"""
Benchmark del coordinador LLM: compara latencia y accuracy de modelos.

Mide también el clasificador rápido vs el LLM para cuantificar el ganancia
de latencia del enfoque híbrido.

Uso:
    source ~/home-agents-env/bin/activate

    # Benchmark con modelo actual (COORDINATOR_MODEL o qwen2.5:7b por defecto):
    python scripts/benchmark_coordinator.py

    # Con modelo 3b (requiere: ollama pull qwen2.5:3b primero):
    COORDINATOR_MODEL=qwen2.5:3b python scripts/benchmark_coordinator.py

    # Saltar benchmark LLM (solo clasificador):
    python scripts/benchmark_coordinator.py --no-llm

Interpretación de resultados:
    - accuracy: fracción de queries ruteadas al agente esperado
    - lat_p50 / lat_p95: latencias en segundos
    - El clasificador siempre reporta su accuracy para comparar

Decisión sugerida:
    - Si accuracy(3b) >= accuracy(7b) - 0.05 y lat_p50(3b) < lat_p50(7b):
      cambiar COORDINATOR_MODEL=qwen2.5:3b en core/.env
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

# ── Catálogo de prueba ─────────────────────────────────────────────────────────

from coordinator import AgentCard  # noqa: E402

CATALOG = [
    AgentCard(
        "haos", "Domótica",
        "Controla luces, temperatura, electrodomésticos y dispositivos del hogar via Home Assistant.",
        ["prendé la luz del living", "apagá el aire acondicionado",
         "poneme la temperatura a 22", "¿qué electrodomésticos están encendidos?"],
    ),
    AgentCard(
        "weather", "Clima",
        "Pronóstico del tiempo, temperatura, lluvia y viento para cualquier ciudad.",
        ["¿cómo está el clima hoy?", "¿va a llover mañana?",
         "pronóstico para el fin de semana", "temperatura en Buenos Aires"],
    ),
    AgentCard(
        "scheduler", "Agenda",
        "Calendario personal, recordatorios, alarmas y eventos.",
        ["¿qué tengo mañana?", "agendá reunión el viernes a las 10",
         "poneme una alarma para las 8", "¿cuándo es mi próximo evento?"],
    ),
    AgentCard(
        "finance", "Inversiones",
        "Cotizaciones de acciones y criptomonedas, precio del dólar, portfolio.",
        ["¿cómo está el dólar blue hoy?", "¿cuánto vale Bitcoin?",
         "¿cómo van mis acciones?", "cotización del euro"],
    ),
    AgentCard(
        "travel", "Viajes",
        "Planificación de viajes, vuelos, hoteles y requisitos de visa.",
        ["quiero planificar un viaje a Roma en julio",
         "¿qué necesito para viajar a Brasil?",
         "hoteles baratos en París", "vuelos a Mendoza"],
    ),
]

# ── Casos de prueba: (query, agente_esperado) ──────────────────────────────────
# "multi" = se espera un plan con más de un agente
# "clarify" = se espera una pregunta de clarificación
# "unknown" = no corresponde a ningún agente

TEST_CASES: list[tuple[str, str]] = [
    # Domótica
    ("prendé la luz de la cocina",                    "haos"),
    ("apagá todas las luces",                          "haos"),
    ("¿qué electrodomésticos están prendidos?",        "haos"),
    # Clima
    ("¿cómo va a estar el tiempo mañana?",             "weather"),
    ("¿va a llover el sábado?",                        "weather"),
    ("temperatura actual en Montevideo",               "weather"),
    # Agenda
    ("¿qué tengo agendado el martes?",                 "scheduler"),
    ("poneme una alarma para las 7 de la mañana",      "scheduler"),
    ("agendá reunión con Juan el jueves a las 15",     "scheduler"),
    # Inversiones
    ("a cuánto está el dólar blue",                    "finance"),
    ("¿cómo van mis acciones hoy?",                    "finance"),
    ("cotización del bitcoin",                         "finance"),
    # Viajes
    ("quiero viajar a Lisboa en agosto",               "travel"),
    ("¿necesito visa para ir a Colombia?",             "travel"),
    # Desconocido
    ("¿cuánto es 17 por 23?",                          "unknown"),
    ("contame un chiste",                              "unknown"),
    # Multi-agente (esperamos que alguno sea el primario)
    ("prendé la luz y dime el tiempo de mañana",       "haos"),   # primario haos
    ("¿cómo está el dólar y qué tengo en la agenda?",  "finance"),# primario finance
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pct(n: int, total: int) -> str:
    return f"{n}/{total} ({100*n//total}%)"


def _p(vals: list[float], pct: int) -> str:
    return f"{np.percentile(vals, pct):.2f}s"


def run_llm_benchmark(model_name: str) -> dict:
    import coordinator as coord

    # Forzar modelo sin recargar módulo (patch directo)
    orig_model = coord.MODEL
    coord.MODEL = model_name

    results = []
    for text, expected in TEST_CASES:
        t0 = time.time()
        try:
            plan = coord.coordinate(text, CATALOG)
        except Exception as e:
            results.append({"text": text, "expected": expected,
                            "got": "error", "ok": False, "lat": 0.0, "err": str(e)})
            continue
        lat = time.time() - t0
        got    = plan.agent_ids[0] if plan.agent_ids else "unknown"
        clarif = bool(plan.needs_clarification)
        ok     = got == expected or (clarif and expected == "clarify")
        results.append({"text": text, "expected": expected,
                        "got": got, "ok": ok, "lat": lat})

    coord.MODEL = orig_model
    return results


def run_classifier_benchmark(cards: list) -> dict:
    import fast_classifier as fc
    fc.train_from_cards(cards)
    clf = fc.classifier

    results = []
    for text, expected in TEST_CASES:
        t0 = time.time()
        agent, conf = clf.predict(text)
        lat = time.time() - t0
        ok  = agent == expected
        results.append({"text": text, "expected": expected,
                        "got": agent, "conf": conf, "ok": ok, "lat": lat})
    return results


def print_table(results: list[dict], title: str, show_conf: bool = False) -> None:
    hits    = sum(r["ok"] for r in results)
    lats    = [r["lat"] for r in results if r["lat"] > 0]
    print(f"\n{'─'*72}")
    print(f"  {title}")
    print(f"{'─'*72}")
    print(f"  Accuracy : {_pct(hits, len(results))}")
    if lats:
        print(f"  Lat p50  : {_p(lats, 50)}   p95: {_p(lats, 95)}")
    print(f"{'─'*72}")
    hdr = f"  {'Query':<44} {'Esp':<12} {'Got':<12}"
    if show_conf:
        hdr += " Conf"
    print(hdr)
    print(f"  {'─'*44} {'─'*12} {'─'*12}")
    for r in results:
        mark  = "✓" if r["ok"] else "✗"
        query = r["text"][:43]
        line  = f"  {mark} {query:<43} {r['expected']:<12} {r['got']:<12}"
        if show_conf and "conf" in r:
            line += f" {r['conf']:.2f}"
        print(line)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark coordinador LLM + clasificador")
    parser.add_argument("--no-llm", action="store_true", help="Saltear benchmark LLM")
    args = parser.parse_args()

    model = os.environ.get("COORDINATOR_MODEL", "qwen2.5:7b")
    print(f"\n{'═'*72}")
    print(f"  Benchmark coordinador — modelo: {model}")
    print(f"  {len(TEST_CASES)} casos de prueba")
    print(f"{'═'*72}")

    # Clasificador rápido
    print("\n[1/2] Clasificador rápido (TF-IDF + cosine)...")
    clf_results = run_classifier_benchmark(CATALOG)
    print_table(clf_results, f"Clasificador rápido (sklearn TF-IDF)", show_conf=True)

    if not args.no_llm:
        # LLM coordinator
        print(f"\n[2/2] LLM coordinator ({model})...")
        print("      (esto puede tardar ~2min con el modelo 7b)")
        try:
            llm_results = run_llm_benchmark(model)
            print_table(llm_results, f"LLM coordinator ({model})")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print("  Asegurate de que Ollama esté corriendo: ollama serve")
    else:
        print("\n[2/2] LLM benchmark salteado (--no-llm)")

    print(f"\n{'═'*72}")
    print("  Para cambiar de modelo en producción:")
    print("  Editá core/.env → COORDINATOR_MODEL=qwen2.5:3b")
    print("  (requiere ollama pull qwen2.5:3b antes de cambiar)")
    print(f"{'═'*72}\n")


if __name__ == "__main__":
    main()
