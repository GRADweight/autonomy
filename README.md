# autonomy — wie viel darf eine KI in Ihrem KMU-Prozess, und wer gibt frei?

Ein Grad mehr Autonomie kostet eine definierte Grenze. **5 Grade, 16 Regeln
(GB-01…GB-16), und ein CLI-Validator** — in Sekunden pruft er, ob ein Fall diese
Grenze halt oder nicht:
`python -m gradbuild.cli examples/gw3-predictive-maintenance.json`.

> **Fallbeispiel:** Ein KMU will, dass die KI Bestellungen nachbestellt. Nicht
> „alles oder nichts": bei **Grad 02 (Copilot)** fragt ein Mensch jede Aktion ab;
> ab **Grad 04** verlangt der Validator ein systemseitiges Limit im ERP
> (z. B. max. 500 Stuick pro Bestellung), einen Rollback und Schattenbetrieb —
> fehlt eines davon, sagt der Validator **nein (Exit 1)** mit Begruendung.
> Ein bewusst fehlerhafter Fall (`counterexample.json`) *muss* scheitern.
> Das ist der Punkt.

## Fur wen

- **Nicht-technische Mitarbeitende** — „Darf die KI das allein?" bekommt eine Antwort mit
  Grad, nicht mit „passt schon".
- **IT-Sicherheitsverantwortliche:r** — die **Rule of Two**: fremde Eingaben + sensible
  Daten + Aussenwirkung → bei Grad 03 und hoher muss mindestens einer *strukturell* weg.
- **Technische AI-Lead** — ein maschinenlesbares Modell (JSON), 9 getestete Bausteine,
  eine Roadmap, die sagt, was gebaut ist und was noch nicht.

## Warum jetzt

- **02.12.2027** gilt der EU AI Act fur Hochrisiko-KI; Autonomie-Grade sind der
  Rahmen, den ein Audit verlangt.
- KMUs brauchen **keine** „autonome KI" — sie brauchen einen **abgestuften** Weg
  mit klarer Grenze.
- **Null Runtime-Abhangigkeit, null Netz:** lauft offline, in CI, in jeder Umgebung.

## Architektur

```
 Mensch  01        02        03        04        05
        Assistent Copilot  Workflow  Agent  Multi-Agent
          |          |         |       |          |
          +--- 16 Regeln (GB-01…GB-16) begrenzen jeden Grad ---+
  - 3 harte Grenzen: Rule-of-Two · Schutzfunktionen · Money-Effects -
```

## Schnellstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e packages/gradbuild -e packages/gw_core pytest
python -m gradbuild.cli examples/gw1-produktwissen-innendienst.json
```

Fur den kompletten Freigabe-Pfad (Vorschlag → Freigabe → Zweitmodell → Audit):
`python -m gw_core.demo --case examples/gw1-produktwissen-innendienst.json`.

## Sicherheit & NIST

- **Guardrail-Level:** der Validator + **ExceptionQueue** (fail-closed): jeder Treffer
  auf Geld / sensibel / Fehlerhaufung landet bei einem Menschen, mit Audit-Trail.
- **Risiko-Kategorie (Risiko-Management nach NIST):** *Govern* — Zuständigkeit,
  Grenzziehung, Freigabe. Erganzend ISO 42001; kein Rechtsrat.
- **Datenhaltung:** null Netz, null externe Abhangigkeit im Kern. Die Beispiele sind
  erfundene Referenzdaten — keine echte Kundendaten.

## Status

- ✅ **lauft:** Grad 01 + 02 implementiert und getestet; uber 100 pytest-Tests,
  CI grun (Python 3.11 / 3.12).
- 🔄 **im Aufbau:** Grad 03–05 als *validierte Referenzfalle* (Modell + Regeln);
  der Runtime ab Grad 04 ist Custom Engineering.
- ⏳ **Next Step:** ein lauffahriger Agent-Runtime-Preset fur Grad 04

  (systemseitiges Limit + Rollback + Schattenbetrieb).

- **Lizenz:** MIT (frei nutzbar, s. `LICENSE`)
> **Ehrliche Grenze:** hier endet der Bereich „Antwort wurde erzeugt" und beginnt
> „Aktion wurde freigegeben". Kein LLM-Framework, kein Rechtsrat, kein Produktkatalog.

> Teil von GRADweight — KMU-AI-Architektur-Netzwerk.
> Finde uns: github.com/GRADweight | Frage? Eroffne ein Issue.
