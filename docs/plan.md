# Phase 1 · Plan — was vorher klar sein muss

Bevor eine Zeile Code geschrieben wird, muss der Autonomie-Fall als
maschinenlesbares JSON stehen und gegen die Regeln GB-01…GB-16 validieren.
Das ist kein Formular. Es ist ein **verifizierbarer Zustand**: `python -m
gradbuild.cli <fall>.json` → Exit 0.

> **Notation:** Die Doku spricht von **Grad 01–05** (Assistent … Multi-Agent).
> Der `gradbuild`-Validator zählt intern **level 0–5**; level 0 ist der reine
> Chat-Fall ohne schreibende Aktionen. Entsprechung: **Grad 01 = level 1**,
> **Grad 02 = level 2** … **Grad 05 = level 5**. Die Beispiele `gw0`…`gw5`
> in `examples/` verwenden die level-Skala.

## Die sechs Pflicht-Fragen (alle Graden)

| Frage | Feld im JSON | Warum |
|---|---|---|
| Wer plant den Weg? Mensch, Feste Kette oder Modell? | `who_plans` | Achse 1 — bestimmt, welche Achse-2-Werte erlaubt sind (GB-02) |
| Wo greift der Mensch ein? | `human_role` | Achse 2 — der Grad selbst |
| Verarbeitet er fremde/unvertrauenswürdige Eingaben? | `foreign_input` | [A] einer der drei Rule-of-Two-Grenzen |
| Greift er auf sensible Daten zu? | `sensitive_data` | [B] Grenze + Datenklasse (GB-15) |
| Hat er Aussenwirkung / Zustandsänderung? | `external_action` | [C] Grenze — ab Grad 01 mit Aussenwirkung: GB-10 greift |
| Berührt er Geld? | `money_effect` | Grad ≥ 04: systemseitige Limits, nicht im Prompt (GB-09) |

## Je Grad: was zusätzlich dazukommt (Quelle: `gradbuild/validate.py`, Stand 2026-10)

| Pflicht | Grad 01 | Grad 02 | Grad 03 | Grad 04 | Grad 05 |
|---|---|---|---|---|---|
| `owner` (benannte Verantwortung) | ✔ | ✔ | ✔ | ✔ | ✔ |
| `incident_log` | ✔ | ✔ | ✔ | ✔ | ✔ |
| Aussenwirkung-Regel (GB-10) | **E** falls [C] | — | — | — | — |
| Übernahmequote beobachtet (GB-07) | — | . | **E** | — | . |
| Rollen-Policy (GB-08) | — | . | — | w | **E** |
| Automatic Rollback (GB-12) | — | . | **E** | **E** | **E** |
| Kill-Switch getestet (GB-12) | — | . | **E** | **E** | **E** |
| Identity + Audit minimal (GB-11) | — | . | — | . | **E** | **E** |
| Schatten-/Vorschlag-Erstes (GB-13) | — | . | — | . | **E** **E** |
| Messung (GB-14) | — | . | — | . | **E** **E** |
| Agent-Identity Least Privilege (GB-11) | — | . | — | **E** | **E** |
| Sampling-Audit + Exception-Queue | — | . | — | — | **E** |
| Rule of Two (GB-03) | . | w | w | **E** | **E** |
| Schutzfunktionen max. Grad 03 (GB-06) | w | w | w | **E** (blockiert) | **E** (blockiert) |

**E** = Error (Validator ablehnt), **w** = Warning, **.** = Information, — = nicht zwingend.

## Plan-Artefakte (was am Ende der Phase vorliegen muss)

1. **Der Prüffall als JSON** — validiert, Exit 0 (oder: die Gründe, warum er
   korrekt abgelehnt ist — das ist auch eine Erkenntnis).
2. **Entscheidungsprotokoll**: Wer ist `owner`, welche Rolle darf was
   freigeben (GB-08), wo wird gemessen (GB-07 ab Grad 03).
3. **Grenzen-Check**: Regel von zwei durchgespielt; bei Grad ≥ 04: welche
   der drei (A/B/C) ist strukturell eliminiert und **wo** ist die Schranke
   (System, nicht Prompt)? Geld-Limits gradweise, wer setzt sie.
4. **Regulatorische Einordnung** (nur die, die relevant sind):
   - EU AI Act: ist der Use Case Hochrisiko (Anhang III, Pflichten ab 02.12.2027)?
     Quelle: Digital Omnibus VO (EU) 2026/1744, in Kraft 27.07.2026.
   - DSG (SR 235.1): Auftragsverarbeitung, Datenfluss, KI-Register-Eintrag.
   - Branche: FINMA 08/2024 (Finanz), Maschinenverordnung (Schutzfunktionen) —
     nur falls zutreffend.

   *Kein Rechtsrat* — diese Einordnung ist die Grundlage für die
   Rechtsberatung, nicht deren Ersatz.

## Anti-Pattern (was wir in der Praxis am häufigsten sehen)

- «Ja nur ein Test» → Fachbereich fängt an, ohne dass Intake, Rollen und
  Grenzen dokumentiert sind. (Das ist der häufigste Grund, warum später
  niemand mehr weiss, wer verantwortlich ist.)
- «Wir machen es erstmal mit GPT-5, die Grenzen kommen später» → die Grenzen
  sind **Architektur**, nicht Konfiguration. Sie müssen jetzt im JSON stehen,
  weil sie die Bausteine im Code bestimmen.
- Aussenwirkung ohne `owner` und ohne `kill_switch_tested` → Validator
  wehrt ab, und richtig so.
