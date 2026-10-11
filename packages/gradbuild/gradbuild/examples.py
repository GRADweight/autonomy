"""Beispiel-Fälle (Grad 0–5) aus der Original-Matrix (3 Bereiche × 6 Grade).

Single Source of Truth: die JSON-Dateien in `examples/`.
Dieses Modul lädt sie — dadurch können CLI, Tests und Doku exakt dieselben
Fälle referenzieren, ohne dass Python-Werte und JSON-Dateien auseinanderlaufen.

Die Fälle sind bewusst *referenzkonform*: Der Validator muss sie als konsistent
durchgehen lassen (keine error; warn/info erlaubt).
Der bewusst gescheiterte Fall liegt in `examples/counterexample.json`.
"""
from __future__ import annotations

import json
from pathlib import Path

_EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "examples"

# Stabile Reihenfolge: Grad 0 … Grad 5
ORDERED_IDS = (
    "gw0-marktforschung",
    "gw1-produktwissen-innendienst",
    "gw2-bewerbungsvorsortierung",
    "gw3-predictive-maintenance",
    "gw4-c-teile-nachbestellen",
    "gw5-standardretouren",
)


def load(example_dir: Path | str | None = None) -> dict[str, dict]:
    """Alle Beispiel-Fälle laden. Rückgabe {case_id: case} in stabiler Reihenfolge."""
    d = Path(example_dir) if example_dir else _EXAMPLE_DIR
    out: dict[str, dict] = {}
    for cid in ORDERED_IDS:
        with open(d / f"{cid}.json", encoding="utf-8") as f:
            out[cid] = json.load(f)
    return out


def load_counterexample(example_dir: Path | str | None = None) -> dict:
    """Den bewusst fehlerhaften Fall laden (für Doku/Demo)."""
    d = Path(example_dir) if example_dir else _EXAMPLE_DIR
    with open(d / "counterexample.json", encoding="utf-8") as f:
        return json.load(f)


# Bequem für `from gradbuild import examples; examples.EXAMPLES[...]`
EXAMPLES: dict[str, dict] = load()

if __name__ == "__main__":
    from .validate import evaluate_case

    for cid, case in EXAMPLES.items():
        rep = evaluate_case(case)
        errors = [f for f in rep.findings if f.severity == "error"]
        warns = [f for f in rep.findings if f.severity == "warn"]
        status = "OK " if not errors else "BROKEN"
        print(f"[{status}] {cid}: {len(errors)} error(s), {len(warns)} warn(s)")
        for f in rep.findings:
            print(f"   - {f.severity.upper():5s} {f.rule}: {f.message}")
