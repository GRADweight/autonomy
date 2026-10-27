# governance/ – Vorlagen für Register, Richtlinie und Rollen

Technische Kontrollen wirken nur, wenn Zuständigkeiten geklärt sind. Diese
Vorlagen sind bewusst kurz und für KMU gedacht; sie ergänzen den Validator und
die Bausteine, sie ersetzen keine rechtliche Beratung.

| Datei | Zweck |
|---|---|
| [vorlagen/ki-register.md](vorlagen/ki-register.md) | KI-Register: eine Zeile je Anwendungsfall mit Grad, Zustand, Verantwortung und Verweis auf die geprüfte Fall-Beschreibung |
| [vorlagen/richtlinie.md](vorlagen/richtlinie.md) | KI-Richtlinie: Geltungsbereich, Grade, harte Grenzen, Freigabe, Nachweise |
| [vorlagen/rollen.md](vorlagen/rollen.md) | Rollenmodell: wer darf was – und was nicht; Umsetzung mit `ApprovalPolicy` |

Bezug zum Code:

- Grade und Regeln: [docs/autonomiegrade.md](../docs/autonomiegrade.md),
  [docs/regeln.md](../docs/regeln.md)
- Freigaben und Rollen: `gradweight_autonomy.approval`, `gradweight_autonomy.authz`
- Nachweis und Protokoll: Nachweispflicht (GB-19, GB-20), `gradweight_autonomy.audit`
