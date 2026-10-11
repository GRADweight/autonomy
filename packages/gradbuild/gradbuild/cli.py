"""gradBuild-KI: prüft Use-Case-Dateien (JSON/JSONL) gegen die Regeln GB-01…GB-16.

Nutzung:
    python -m gradbuild.cli usecase.json [...]
    cat *.json | python -m gradbuild.cli --stdin

Exit-Code: 0 = keine Fehler, 1 = mind. ein error, 2 = Schemafehler.
"""
from __future__ import annotations

import json
import sys

from .validate import evaluate_case, Finding


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        # Liste von Cases → erster Case? Nein: jeder Entry wird geprüft.
        raise ValueError("Liste im JSON — erwartet wurde ein einzelnes Case-Objekt (nutze --stdin für mehrere).")
    return data


def _fmt(f: Finding) -> str:
    icon = {"error": "✗ ERROR", "warn": "⚠ WARN ", "info": "· info "}
    return f"  {icon.get(f.severity, '      ')}  {f.rule}  Grad {f.level}  {f.message}"


def run(cases: list, case_ids: list) -> int:
    worst = 0
    failed = 0
    for case, cid in zip(cases, case_ids):
        report = evaluate_case(case)
        print(f"== {cid or case.get('id', '?')} ==")
        if not report.findings:
            print("  ✓ keine Befunde — Konfiguration konsistent.")
        for f in report.findings:
            print(_fmt(f))
            if f.detail:
                print(f"      ↳ {f.detail}")
        if any(f.severity == "error" for f in report.findings):
            failed += 1
            worst = max(worst, 1)
    print()
    print(f"{len(cases)} Case(s), {failed} mit Fehlern.")
    return worst


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    paths = [a for a in args if not a.startswith("--")]
    stdin = "--stdin" in args

    if stdin:
        raw = sys.stdin.read()
        # JSONL (eine Zeile = ein Case) oder ein JSON-Array akzeptieren.
        lines = [l for l in raw.splitlines() if l.strip()]
        cases = []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                cases = data
            else:
                cases = [data]
        except json.JSONDecodeError:
            for l in lines:
                try:
                    cases.append(json.loads(l))
                except json.JSONDecodeError as e:
                    print(f"✗ JSONL-Zeile ungültig: {e}", file=sys.stderr)
                    return 2
        ids = [f"stdin[{i}]" for i in range(len(cases))]
        return run(cases, ids)

    if not paths:
        print(__doc__)
        return 2

    cases, ids = [], []
    for p in paths:
        try:
            c = _load(p)
            cases.append(c)
            ids.append(c.get("id", p))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"✗ {p}: {e}", file=sys.stderr)
            return 2

    return run(cases, ids)


if __name__ == "__main__":
    sys.exit(main())
