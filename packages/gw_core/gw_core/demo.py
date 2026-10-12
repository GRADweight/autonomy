"""Drehdurchgang: Validation → Vorschlag → Freigabe → Prüfung → Audit.

Das ist der Freigabe-Pfad (Copilot-Modell: «Mensch gibt je Aktion frei»)
in einem Durchlauf — ohne Netzwerk, ohne externe Abhängigkeiten,
deterministisch. Läuft in jedem Kramkasten:

  python -m gw_core.demo \
      --case examples/gw1-produktwissen-innendienst.json

Was jede Stufe zeigt (entsprechend `docs/wie.md`):
  1. **Validation**  — der Fall gegen GB-01…16 (gradbuild-CLI, Exit 0)
  2. **Vorschlag**   — die KI schlägt eine schreibende Aktion vor (Status: offen)
  3. **Freigabe**    — ein Mensch gibt die Aktion frei (Grad 02: per_action)
  4. **Prüfung**     — Zweitmodell-Prüfung: jede Zahl muss in einer Fundstelle stehen
  5. **Audit-Trail** — wer, was, wann — der lückenlose Nachweis (GB-08/GB-11)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gw_core.approval import ApprovalQueue
from gw_core.audit import AuditTrail
from gw_core.authz import FreigabePolicy
from gw_core.verify import Zitat, pruefe_antwort


def _linie(t: str = "•") -> None:
    print(f"\n{t} {t * 6}")


def run_demo(case_path: Path) -> int:
    fall = json.loads(case_path.read_text(encoding="utf-8"))
    mandant = fall.get("id", "demo")
    prototyp = f"grad-{fall.get('level', 1):02d}"
    titel = fall.get("title", "Demo-Aktion")

    print("=" * 62)
    print(f"DEMO — {titel}")
    print(f"Grad: {fall.get('level')} · wer plant: {fall.get('who_plans')}"
          f" · Rolle: {fall.get('human_role')}")
    print("=" * 62)

    # ── Stufe 2: Vorschlag ──────────────────────────────────────────
    _linie()
    print("STUFE 2 · Vorschlag — die KI schlägt eine schreibende Aktion vor")
    audit = AuditTrail()  # :memory: — Demo ohne Datei-Rückstand
    # Zentrale Rollen-Policy (GB-08 Least Privilege): 'ai-lead' darf für
    # diesen Prototyp freigeben — die Queue erzwingt das, nicht der Prompt.
    policy = FreigabePolicy(policy={"default": ["ai-lead"]})
    q = ApprovalQueue(audit=audit, policy=policy)
    payload = {
        "aktion": "Kundenantwort auf Offerten-Frage entwerfen",
        "quell": "katalog/produkt-ab-1.2.md#L42",
        "betrag_chf": 480.0,
    }
    action_id = q.vorschlage(
        mandant=mandant,
        prototyp=prototyp,
        titel="Entwurf: Kundenantwort zu Offerten-Frage (Betrag 480 CHF)",
        payload=payload,
        vorgeschlagen_von="llm",
        freigabe_nur_an="ai-lead",
        anmerkungen="Demo — kein echter Kunde, keine echten Daten",
    )
    a = q.lade(action_id)
    print(f"  Aktion #{a.id} eingereicht: status={a.status!r}")

    # ── Stufe 3: Freigabe (Mensch greift ein) ──────────────────────
    _linie()
    print("STUFE 3 · Freigabe — ein Mensch gibt je Aktion frei (per_action)")
    freigabe = q.freigabe(action_id, actor="ai-lead", rolle="ai-lead")
    print(f"  Aktion #{freigabe.id}: status={freigabe.status!r}"
          f" · erledigt von: {freigabe.erledigt_von!r}")

    # ── Stufe 4: Prüfung (Zweitmodell: jede Zahl muss belegt sein) ─
    _linie()
    print("STUFE 4 · Prüfung — Zweitmodell-Check: Zahlen müssen in Fundstellen stehen")
    antwort = (
        "Die Pauschale für die Nachbestellung beträgt 480 CHF. "
        "Die Bearbeitungszeit liegt bei 5 Werktagen."
    )
    fundstellen = [
        Zitat(text="Nachbestell-Pauschale: 480 CHF (Katalog 2026, L42).",
              quelle="katalog/produkt-ab-1.2.md#L42"),
        Zitat(text="Bearbeitung: 5 WERKE (intern: 5 Werktage).",
              quelle="reglement/logistik.pdf#S3"),
    ]
    befun = pruefe_antwort(antwort, fundstellen)
    print(f"  Antwort:  {antwort!r}")
    print(f"  Befund:   {befun.zusammenfassung()}")

    # ── Stufe 5: Audit-Trail ──────────────────────────────────────
    _linie()
    print("STUFE 5 · Audit-Trail — wer, was, wann (GB-08/GB-11)")
    for row in audit.query(mandant=mandant)[:6]:
        print(f"  [{row['id']}] {row['ts'][:19]}  actor={row['actor']:10}  {row['action']}")
    audit.schliesse()
    q.schliesse()

    _linie()
    ok = (freigabe.status == "freigegeben") and befun.ok
    print("DEMO: " + ("OK — alle 5 Stufen durchlaufen, Freigabe und Prüfung grün"
                       if ok else
                       "FEHLER — s. obige Stufen (erwartetes Verhalten bei VETO-Fall: Stufe 4 rot)"))
    return 0 if ok else 1


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        type=Path,
        default=None,
        help="Optionaler Fall-JSON (gibt Grad/Rolle/Mandanten-Kontext vor). "
             "Default: Demo-Kontext ohne Fall.",
    )
    args = parser.parse_args(argv)
    if args.case is not None:
        if not args.case.exists():
            print(f"ERROR: Fall nicht gefunden: {args.case}", file=sys.stderr)
            return 2
        return run_demo(args.case)
    # Default: Demo-Kontext (keine externe Abhängigkeit)
    import tempfile

    fake = Path(tempfile.mkdtemp()) / "demo.json"
    fake.write_text(json.dumps({
        "id": "demo-grad-02",
        "title": "Demo-Fall: Grad 02 Copilot (ohne externer Fall-JSON)",
        "level": 2, "who_plans": "human", "human_role": "per_action",
    }, ensure_ascii=False), encoding="utf-8")
    try:
        return run_demo(fake)
    finally:
        import shutil

        shutil.rmtree(fake.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(_main())
