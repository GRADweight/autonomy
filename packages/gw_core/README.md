# gw_core — Governance-Bausteine

Acht getestete Bausteine aus dem gemeinsamen GRADweight-Kern — sechs für
Grad 01–02, zwei für Grad ≥ 4 (die fehlenden `exception_queue` und
`sampling_audit` aus der Roadmap). Alle lösen ein und dasselbe Problem:
**eine KI-Aktion ist erst gültig, wenn sie freigegeben, geprüft und
protokolliert wurde.**

| Baustein | Modul | Aufgabe |
|---|---|---|
| Approval-Queue | `approval.py` | Freigabe / Anpassen / Zurückstellen je Aktion, Rechte-Check |
| Audit-Trail | `audit.py` | append-only, wer/was/wann, CSV-Export für Revision |
| Zweitmodell-Prüfung | `verify.py` | Antwort gegen Fundstellen prüfen, VETO bei Abweichung |
| Freigabe-Policy | `authz.py` | Rolle × Kontext, Least Privilege, admin-VETO |
| Tracing | `tracing.py` | LLM-Request-Protokoll (Dauer, Status, Mandant) |
| Zielsystem-Adapter | `bexio.py` | systemseitige Limiten (Betrag, Tagesvolumen), Dry-Run |
| **Exception-Queue** † | `exception_queue.py` | deterministische Schwelle (Geld/sensibel/Fehler); jeder Treffer → Menschen-Queue, Append-only |
| **Stichproben-Audit** † | `sampling_audit.py` | reproduzierbare systematische Stichprobe über den Audit-Trail, Kriterien + Evidenz |

† = für Grad ≥ 4 (GB-11). Schliesst die Lücke aus
`docs/roadmap-grad-03-05.md` §2.2: `exception_queue` und `sampling_audit`
sind hier **im Code**, nicht nur im JSON behauptet.

Alle Bausteine sind **in sich geschlossen**: es gibt kein "vertrauenswürdiger
LLM dahinter" — Input, Freigabe, Prüfung, Logik und Log sind explizite,
testbare Funktionen. Genau das ist der Unterschied zum "Model als Agent".

## Installation

```bash
pip install -e packages/gw_core
```

## Nutzung (Minimalbeispiel)

```python
from gw_core import ApprovalQueue, AuditTrail, FreigabePolicy

audit = AuditTrail()
policy = FreigabePolicy(policies={          # Rolle -> Erlaubte Aktionen
    "fachverantwortung": ["freigabe", "anpassen", "zurueckstellen"],
    "admin": ["freigabe", "anpassen", "zurueckstellen", "veto"],
})
queue = ApprovalQueue(policy=policy, audit=audit)

akt = queue.aufgeben(
    mandant="K1",
    prototyp="rechnungs-extraktion",
    beschreibung="Rechnung R-2026-0042 buchen (CHF 1'240.00)",
    payload={"betrag": 1240.00, "waehrung": "CHF"},
)
# -> eine Person mit der richtigen Rolle muss freigeben:
queue.entscheiden(aktions_id=akt.id, rolle="fachverantwortung",
                  entscheid="freigabe", begruenderung="Plausibel geprüft")
```

Was dabei passiert:
1. Die Aktion liegt in der Queue (Status `offen`).
2. `entscheiden` prüft die Rolle gegen die Policy (`authz.py`).
3. Der Entscheid wird in den Audit-Trail geschrieben (`audit.py`, wer/was/wann).
4. Die Aktion ist fortan `freigegeben` — und nur diese Aktionen dürfen
   ein Zielsystem berühren.

## Tests

```bash
pip install -e packages/gw_core
pytest tests_gwcore -v
```

## Grenzen (bewusst)

- **Kein LLM dahinter.** Diese Bausteine *verarbeiten* keine Prompts, sie
  *verwalten* Freigaben und Belege. Die LLM-Ebene davor ist ein anderes Projekt
  mit anderen Abhängigkeiten.
- **Kein eigenes Auth-Backend.** Die Rolle wird der Funktion übergeben;
  wer diese Rolle besitzen darf, ist Aufgabe des umgebenden Systems /
  des Gateways / des OAuth-Anbieters.
- **DSG / AI Act:** Die Bausteine *dokumentieren* (Log, Freigabe), sie
  *entscheiden* nicht über Rechtsfragen.
