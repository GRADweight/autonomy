# Rollenmodell (Vorlage)

> Befugnisse hängen am Paar (Anwendung, Aktion), nicht an der Person. Dieselbe
> Person kann in zwei Anwendungen unterschiedlich berechtigt sein.

## Kernrollen

| Rolle | Aufgaben | Darf nie |
|---|---|---|
| **Fachverantwortung** (je Anwendung) | Aktionen der eigenen Anwendung freigeben, anpassen, zurückweisen; Übernahmequote verfolgen; Vorfälle melden | den Grad der eigenen Anwendung erhöhen |
| **KI-Verantwortung** (Organisation) | Grade abnehmen, Register und Richtlinie pflegen, Notaus auslösen | im Tagesbetrieb Aktionen freigeben (Funktionstrennung) |
| **Revision** | Stichproben, Prüfung der Audit-Kette, Einsicht in Nachweise | Aktionen freigeben |

## Matrix

| Aktion | Fachverantwortung | KI-Verantwortung | Revision |
|---|---|---|---|
| Aktion freigeben oder anpassen | ja (eigene Anwendung) | nein | nein |
| Aktion zurückweisen | ja | ja | nein |
| Grad erhöhen | nein | ja (mit geprüftem Fall) | nein |
| Notaus auslösen | nein | ja | nein |
| Audit-Kette prüfen | nein | ja | ja |

Die wichtigsten Zellen sind die mit «nein».

## Rollen, die es nicht gibt

- **«Rolle KI»:** Ein Modell schlägt Aktionen vor; Freigabe und Notaus sind
  Menschen vorbehalten. Die Freigabe-Queue verweigert die Freigabe durch den
  Vorschlagenden (Vier-Augen-Prinzip).
- **Stillschweigende Superuser:** Wer für alle Anwendungen freigeben darf,
  steht sichtbar in der Policy (Schlüssel `"*"`).

## Umsetzung mit `ApprovalPolicy`

```python
from gradweight_autonomy.authz import ApprovalPolicy

policy = ApprovalPolicy(
    {
        "kreditoren": ["fachverantwortung-finanzen"],
        "bewerbungen": ["fachverantwortung-hr"],
        "default": [],  # nicht aufgeführte Anwendungen: niemand
    }
)
policy.check(role="fachverantwortung-finanzen", use_case="kreditoren").allowed  # True
```

Die Policy kann auch aus `GW_APPROVAL_POLICY` (JSON) oder
`GW_APPROVAL_POLICY_FILE` geladen werden; eine konfigurierte, aber fehlende
Datei ist ein Fehler. Änderungen an der Policy laufen über einen Review
(Pull Request mit Begründung).
