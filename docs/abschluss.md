# Phase 4 · Abschluss — Kill-Kriterien und Abnahme

«Abschluss» heisst hier nicht «das Projekt ist zu, wir feiern». Es heisst:
**wir haben einen definierten Moment, an dem wir entweder weitergehen oder
ehrlich aufhören — und wir wissen im Vorhinein, wie der Moment aussieht.**

## Die drei Entscheide (alle Graden)

Nach Abschluss der Umsetzung steht genau einer von dreien:

| Entscheid | Bedingung | Konsequenz |
|---|---|---|
| **Weiter** | Alle Abnahmekriterien erfüllt, Messwerte im Zielbereich | Inbetriebnahme (Phase 5) |
| **Umbauen** | Abnahmekriterien nicht erfüllt, aber das Ziel erreichtbar ist | Neuer Plan (Phase 1), neuer Fall, neuer Grad (evtl.) |
| **Aufhören** | Ziel nicht erreichbar oder das Ziel war falsch | Beendigung mit Protokoll — kein «das schauen wir im Q3 nochmal» |

Der dritte Entscheid ist der wichtigste und der am seltensten genommene.
**Ein PoC, der «weil schon investiert» weiterläuft, ist ein Betriebskosten-
Risiko, kein Asset.** (GB-06-Logik: die Kosten der Weiterführung sind
Teil der Abnahme, nicht eine Ausrede.)

## Abnahmekriterien je Grad (Checkliste)

### Grad 01 — Assistent
- [ ] `python -m gradbuild.cli <fall>.json` → Exit 0
- [ ] `verify.pruefe_antwort` — VETO bei Abweichung funktioniert (Testfall vorhanden)
- [ ] Quellenangabe bei jeder Antwort (kein «Zusammenfassung ohne Fundstelle»)
- [ ] `pytest tests_gwcore` → grün

### Grad 02 — Copilot
- [ ] Alle Grad-01-Kriterien
- [ ] `ApprovalQueue` live: jede schreibende Aktion läuft durch `entscheiden(...)`
- [ ] `FreigabePolicy` — nicht erlaubte Rollen werden abgelehnt (Testfall vorhanden)
- [ ] `AuditTrail` — CSV-Export funktioniert, fortlaufende RID, append-only
- [ ] **Adoption-Rate** (GB-07, `adoption_rate_monitored`) — gemessen,
  nicht nur «verfügbar». Ein konkreter Wert wird notiert.

### Grad 03 — Workflow
- [ ] Alle Grad-02-Kriterien
- [ ] Fixed-Chain dokumentiert: welche Rolle entscheidet an welchem Gate,
  mit welchen Erfolgskriterien (nicht «der Chef schaut mal»)
- [ ] Systemseitige Limits (GB-08/GB-09): `limit_betrag`,
  `limit_tagesvolumen` — überschrittene Limits werden **blockiert**,
  Testfall vorhanden
- [ ] **Kill-Switch getestet** (GB-12): `stopp(mandant, prototyp)`
  setzt alle offenen Aktionen zurück, Adapter auf Dry-Run, Log-Eintrag
  ist im Audit-Trail
- [ ] **Rollback getestet**: Zustand-Änderung wird bei Abweichung zurückgesetzt

### Grad 04 — Agent
- [ ] Alle Grad-03-Kriterien
- [ ] `mandate.limits_in_system = true` — die Grenzen sind im System,
  nicht im Prompt. Konkreter Nachweis: das Limit wird im Adapter
  erzwungen, nicht im Systemprompt erwähnt
- [ ] **Schattenbetrieb abgeschlossen** (GB-13): `shadow_run_first`
  Phase abgeschlossen, Abweichungsrate zur Referenz dokumentiert,
  Entscheidung aufgezeichnet (wer hat das Freigaben gegeben)
- [ ] **Least Privilege** (GB-11): `agent_identity_min_privilege = true` —
  der Agent hat genau die Rechte des Use-Cases, nicht der ganzen Rolle.
  Konkreter Nachweis: ein Test, der zeigt, dass der Agent eine Aktion
  ausserhalb seines Use-Cases **nicht** ausführen kann
- [ ] **Messung definiert** (GB-14): `measurement.method` ist gesetzt
  (`pass^k` oder `shadow`), die Methodik ist dokumentiert, nicht nur
  «wir messen das»

### Grad 05 — Multi-Agent
- [ ] Alle Grad-04-Kriterien
- [ ] **Sampling-Audit** (GB-11): der Anteil ist definiert, die Auswahl
  ist deterministisch und nachvollziehbar (nicht zufällig), Testfall
  zeigt, dass die ausgewählten Aktionen im Log sind
- [ ] **Exception-Queue** (GB-15): unerwartete Aktionen landen in der
  Queue, werden von einer benannten Rolle abgearbeitet, Testfall vorhanden
- [ ] **Globaler Kill-Switch**: `stopp(mandant)` wirkt auf alle Agenten
  dieses Mandanten, Testfall vorhanden
- [ ] **Globales Rollback**: Zustand-Änderungen aller Agenten werden
  bei Abweichung zurückgesetzt
- [ ] **Rule of Two** (GB-03): bei Grad 05 mit `sensitive_data` +
  `foreign_input` + `external_action` → der Validator wehrt ab. Wenn der
  Fall trotzdem Exit 0 hat, ist einer der drei Flags falsch gesetzt
  (falsch!) oder die Architektur entspricht dem Fall nicht. Prüfen.

## Was «kein Abschluss» ist

- «Das läuft schon, wir schauen im nächsten Quarter nochmal» → das ist
  **Betrieb ohne Abnahme**. Das ist der teuerste Fehler, den ein KMU
  machen kann.
- «Die Zahlen sind fast im Ziel, die letzten 5 % holen wir im Live-Betrieb»
  → die letzten 5 % sind der Grund, warum das Modell live läuft. Entweder
  sind sie im Ziel oder nicht.
- «Das System funktioniert, aber wir haben kein Kill-Switch-Test» →
  das System ist ab Grad 03 nicht abnahmefähig. Punkt.
- «Die Freigabe-Kette ist da, aber die Rollen-Policy ist noch offen» →
  offene Rollen-Policy = offene Rechte = offener Sicherheitsbefund.

## Das Abschluss-Protokoll (was am Ende vorliegen muss)

1. **Der Prüffall (JSON)** — finaler Stand, gültig gegen GB-01…GB-16
2. **Der Messbericht** — konkrete Zahlen (Adoption-Rate, VETO-Rate,
   Kill-Switch-Test-Datum, Rollback-Test-Datum), nicht «es läuft»
3. **Der Audit-Trail-Auszug** — die letzten 10 Aktionen, mit RID, Zeitstempel,
   Rolle und Begründung. (Append-only: kein Auswählen von «den schönen»,
   alle zehn, die es sind.)
4. **Die Entscheidung** — Weiter / Umbauen / Aufhören, mit Begründung
   und Unterschrift (Rolle, nicht Name)
5. **Die Übergabe** (falls Weiter): Runbooks, Kill-Switch-Dokumentation,
   Rollback-Anleitung, Zugang (wer darf was, im System)
