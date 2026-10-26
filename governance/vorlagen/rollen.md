# Rollenmodell (Vorlage) — wer darf was, je Grad

> Rollen sind **Kontext-gebunden**: dieselbe Person ist in zwei Use-Cases
> unterschiedlich befugt. Die Befugnis steht nicht an der Person, sondern
> am (Anwendung × Aktion)-Paar. Das ist der ganze Zweck eines
> Rollenmodells, das «Least Privilege» ernst meint.

## Die drei Kernrollen (Pflicht in jedem KI-Projekt)

| Rolle | Mindest-Pflichten | Kann NIE |
|---|---|---|
| **Fachverantwortlicher** (je Anwendung) | Freigabe der Aktionen seiner Anwendung; Adoption-Rate lesen; Incident melden | Anwendungen auf höheren Grad versetzen; Rollen ändern |
| **KI-Verantwortlicher** (organisatorisch) | Grad-Freigabe; Register pflegen; Richtlinie pflegen; Kill-Switch auslösen | Aktionen einer bestimmten Anwendung freigeben (separation of duties) |
| **Admin** | VETO über jede Freigabe; Rollen-Mutation; Systemzugang | Fachentscheide (VETO muss begründet werden, Begründung landet im Audit-Trail) |

## Wer darf was — Matrix (Aktion × Rolle)

| Aktion | Fachverantwortl. | KI-Verantw. | Admin |
|---|---|---|---|
| Aktion freigeben (Grad 02/03) | ja (eigene Anwendung) | nein | ja (VETO) |
| Aktion anpassen | ja (eigene Anwendung) | nein | ja |
| Aktion zurückstellen | ja | ja | ja |
| **VETO** (jeden Fall) | — | ja | ja |
| Grad erhöhen (z.B. 02 → 04) | nein | ja (mit validiertem Fall-JSON) | ja (VETO) |
| Kill-Switch auslösen | nein | ja | ja |
| Register-Eintrag anlegen/ändern | nein | ja | nein (nur VETO) |
| Rollen ändern | — | ja (eigene Anwendungen) | ja |

**Merksatz:** Die zwei wichtigsten Zellen in der Matrix sind die, in
denen «nein» steht. (Fachverantwortlicher darf nicht selbst auf den
nächsten Grad gehen, und der KI-Verantwortliche soll nicht im Tagesbetrieb
freigeben.)

## Die Rollen, die es NICHT gibt

- **«Modelle/Rolle KI»** — ein Modell hat keine Rolle, keine Freigabe-
  Befugnis, kein Veto. Es erzeugt `Aktion`-Objekte in der Queue. Ende.
- **«Junior-/Senior-Freigeber»** — Freigabe ist ein Ja/Nein mit Begründung
  (bei VETO). Hierarchie ersetzt keine Kompetenz; die Befugnis ist an
  die Anwendung gebunden, nicht an die Stufe.
- **«Gast»** — ein Gast-Zugang auf eine live-App grad ≥ 02 ist ein
  Befund, keine Rolle.

## So veränderst du die Rollen-Policy (Praxis, `gw_core.authz`)

```python
from gw_core import FreigabePolicy

policy = FreigabePolicy(
    policies={
        "fachverantwortung": ["freigabe", "anpassen", "zurueckstellen"],
        "ki_verantwortlicher": ["freigabe", "zurueckstellen", "veto", "kill_switch"],
        "admin": ["freigabe", "anpassen", "zurueckstellen", "veto"],
    }
)
```

- Rolle-Änderung = Code-Änderung = PR mit Begründung (nicht: «wir machen
  das schnell in der Config»).
- Jede Rollen-Änderung wird im Audit-Trail protokolliert (wer hat die
  Policy geändert, wann, warum).
