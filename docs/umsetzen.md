# Phase 2 · Umsetzen — was gebaut wird, je Grad

Grundprinzip: **Das Modell ist keine Blackbox, die man einschaltet. Es ist
die Sache davor (Antwort) und die Sache danach (Aktion). Wir bauen die
Schicht dazwischen — freigegeben, geprüfter und protokollierter Weg von
einer Antwort zu einer Zustand-Änderung.**

## Die Schicht, die alle Grade gemeinsam haben

| Schicht | gw_core-Baustein | Aufgabe |
|---|---|---|
| Input-Prüfung | `verify.pruefe_antwort` | Antwort gegen Fundstellen, VETO bei Abweichung |
| Freigabe | `approval.ApprovalQueue` | je Aktion: freigeben / anpassen / zurückstellen |
| Rechte | `authz.FreigabePolicy` | welche Rolle darf welche Aktion, admin-VETO |
| Protokoll | `audit.AuditTrail` | wer/was/wann, append-only, CSV-Export |
| Beobachtbarkeit | `tracing.Tracer` | LLM-Request-Dauer, Status, Mandant — wer hat was wann gesehen |

Diese fünf Schichten sind **nicht optional** — sie sind die Definition von
«grad 02». Ohne sie ist es grad 01 (Vorschlag) oder ein unbelegtes Risiko.

## Je Grad: was zusätzlich im Code stehen muss

### Grad 01 — Assistent (level 1)

- Alles, was das Modell «vor» und «nach» braucht.
- `verify` + Quellenzitat. Die Antwort geht erst raus, wenn sie geprüft ist.
- Kein schreiben in externe Systeme. `external_action = false` im Fall.
- **Nicht**: Freigabe-Queue, weil es keine schreibende Aktion gibt.
  (Ist die Antwort selbst die Aussenwirkung → GB-10 greift trotzdem.)

### Grad 02 — Copilot (level 2)

- Alle fünf Schichten oben, live.
- Die Freigabe-Queue ist die **einzige** Tür zu einem externen Zustand:
  `ApprovalQueue` → `entscheiden(rolle, "freigabe")` → Zielsystem.
- **Zweitmodell-Prüfung**: `pruefe_antwort(antwort, fundstellen)` →
  `Befund(ok=False, veto=True)` blockiert die Freigabe.
- **KPI (GB-07)**: `adoption_rate_monitored = true` — wie oft nimmt der
  Mensch die Antwort tatsächlich an? Fällt die Quote auf Niveau des
  Automatisch-Korrekten, ist das kein Qualitätssignal mehr, sondern ein
  Gummistempel: der Mensch sieht nur noch grünes. Dann ändern wir Prompt
  und Fundstellen, nicht die Schwelle.

### Grad 03 — Workflow (level 3)

- Feste Kette: `who_plans = fixed_chain`, `human_role = per_gate`.
- Jedes Gate = eine Freigabe-Instanz, mit eigener Rolle und eigenen
  Erfolgskriterien (nicht «Mensch schaut kurz», sondern: «Rolle X prüft
  Kriterium Y an Fundstelle Z»).
- **Systemseitige Limits** (GB-08 / GB-09): Betrag max., Tagesvolumen max.,
  Ziel-System = Buchhaltung/ERP — nicht im Prompt, sondern als Schranke
  im Adapter (`bexio.BexioZielsystemAdapter` mit `limit_betrag()`,
  `limit_tagesvolumen()`).
- **Kill-Switch** (GB-12): eine definierte Aktion, die alle offenen
  Aktionen zurücksetzt. Getestet, nicht nur dokumentiert.
- **KPI-Report** (GB-07) wird ab jetzt Pflicht, nicht optional.

### Grad 04 — Agent (level 4)

- `who_plans = model`, `human_role = mandate`.
- **Das Modell plant** — aber innerhalb eines Mandats, dessen Grenzen
  systemseitig gesetzt sind: `mandate.limits_in_system = true` (GB-11, GB-14).
- **Schattenbetrieb zuerst (GB-13)**: `shadow_run_first = true` — das
  Modell darf «sagen, was es tun würde», wird aber nicht ausgeführt.
  Mindestens eine Messperiode. Erst wenn die Abweichungsrate zur
  Referenz akzeptiert ist, geht es live.
- **Rollback** (GB-12): `automatic_rollback = true` — bei Abweichung wird
  der Zustand zurückgesetzt. Getestet (kein «wenn es klappt»).
- **Least Privilege** (GB-11): `agent_identity_min_privilege = true` —
  der Agent hat nur die Rechte, die der eine Use Case braucht, nicht
  die Rechte der ganzen Rolle.
- **Messung** (GB-14): `measurement.method = "pass^k"` oder `"shadow"` —
  die Methodik muss im Fall stehen.

### Grad 05 — Multi-Agent (level 5)

- `who_plans = model`, `human_role = exception_only`.
- Alles von Grad 04, **plus**:
  - `sampling_audit = true`: nicht jede Aktion wird einzeln geprüft,
    sondern ein definierter Anteil — aber die Auswahl ist deterministisch
    und nachvollziehbar, nicht zufällig.
  - `exception_queue = true`: Ausnahmen (die der Mensch nicht erwartet)
    werden in eine Warteschlange gelegt und müssen von einer benannten
    Rolle abgearbeitet werden.
  - **Kill-Switch** (GB-12) + **Rollback** (GB-12): global, nicht pro Agent.
  - **Wichtig**: GB-06 (Schutzfunktionen) und GB-03 (Rule of Two) sind
    bei Grad 05 **Errors**, keine Warnings. Ein multi-agentes System,
    das auf sensible Daten greift, fremde Eingaben verarbeitet UND
    Aussenwirkung hat, wird vom Validator abgelehnt — und das ist der
    Punkt.

## Was NICHT gebaut wird (bei welchem Grad)

| Grad | Nicht |
|---|---|
| 01–02 | Kein Automatismus. Jede schreibende Aktion ist eine Freigabe-Instanz. |
| 03 | Kein «Modell entscheidet, wer entscheidet» — die Kette ist fest, die Rollen sind benannt. |
| 04 | Kein «Modell darf alles, wir schauen dann» — die Limits sind im System, nicht im Prompt. |
| 05 | Kein «wir schalten das mal ein» — Schattenbetrieb, Messung, Sampling-Audit und Kill-Switch sind Voraussetzungen, nicht Folgen. |

## Abnahmekriterien (Definition of Done, je Grad)

1. `python -m gradbuild.cli <fall>.json` → **Exit 0**.
2. Alle Pflicht-Bausteine (s. Tabelle oben) sind importiert und in der
   Freigabe-Kette verdrahtet — nicht nur «vorhanden im Repo».
3. `pytest tests_gwcore` → **grün**.
4. **Einer** der Testfälle in `tests_gwcore/` entspricht dem Grad, den
   ihr baut (nicht: «wir haben Tests, aber nicht für diesen Fall»).
