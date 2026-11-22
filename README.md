# autonomy – Autonomiegrade für KI in KMU-Prozessen

[![CI](https://github.com/GRADweight/autonomy/actions/workflows/ci.yml/badge.svg)](https://github.com/GRADweight/autonomy/actions/workflows/ci.yml)
[![Policy-Gate](https://github.com/GRADweight/autonomy/actions/workflows/policy-gate.yml/badge.svg)](https://github.com/GRADweight/autonomy/actions/workflows/policy-gate.yml)
Lizenz: MIT · Python ≥ 3.10 · keine Laufzeit-Abhängigkeiten

## In English

`autonomy` answers a practical question for small and medium-sized businesses:
how much may an AI system do on its own in a business process, and who
approves what? It defines six autonomy grades (0–5) and ships a
policy-as-code validator that checks machine-readable use-case descriptions
against 22 rules, including cross-field consistency and an evidence
requirement for every claimed control; results are emitted as text, JSON or
SARIF 2.1.0 for CI gates and GitHub code scanning. Building blocks enforce at
runtime what the description promises: an approval queue with four-eyes
principle, a hash-chained audit trail, a number-and-source check for AI
answers, Swiss invoice checks (IBAN, QR reference, VAT, UID) and a bexio
adapter. Everything runs on the Python standard library; documentation is in
German.

## Worum es geht

KI kommt in KMU selten auf einen Schlag, sondern Schritt für Schritt: zuerst
als Assistent, dann mit Vorschlägen, später vielleicht mit eigenem Mandat. Die
entscheidende Frage ist nicht «KI ja oder nein», sondern **wie viel die KI
allein tun darf, wo ein Mensch eingreift und womit das belegt ist**.

Dieses Repo liefert dafür

1. ein **Autonomiemodell** mit sechs Graden und klaren Pflichten je Grad,
2. einen **Validator**, der eine Use-Case-Beschreibung (JSON) gegen 22 Regeln
   prüft – nicht nur Häkchen, sondern Widersprüche und **Nachweise** für jede
   behauptete Kontrolle,
3. **Bausteine**, die im Betrieb erzwingen, was die Beschreibung verspricht.

## Die Autonomiegrade

| Grad | Name | Wer plant? | Wo greift der Mensch ein? | Zusätzliche Pflichten |
|---|---|---|---|---|
| 0 | Keine KI-Autonomie | Mensch | bei jedem Schritt | – |
| 1 | Assistent | Mensch | Mensch handelt selbst | keine Aussenwirkung |
| 2 | Copilot | Mensch oder Modell | Freigabe je Aktion | Übernahmequote messen |
| 3 | Workflow | feste Kette | Freigabe an Toren | Notaus getestet, Rollback, Incident-Prozess, Messung |
| 4 | Agent mit Mandat | Modell | Mandat mit Grenzen im Zielsystem | Audit-Trail, eigene Identität, Schattenbetrieb, Vorschlagsphase, Betragsgrenze |
| 5 | Autonom mit Ausnahmesteuerung | Modell | nur Ausnahmen | Ausnahme-Queue, Stichproben-Audit |

Dazu drei harte Grenzen: **Rule of Two** (fremde Eingaben, sensible Daten und
Aussenwirkung nie zugleich ohne Mensch in der Kette), **Schutzfunktionen**
bleiben ausserhalb des Modells, **Geld** nur mit Betragsgrenze im Zielsystem.
Mehr in [docs/autonomiegrade.md](docs/autonomiegrade.md); alle Regeln mit
Begründung und Quellen in der generierten [Regel-Referenz](docs/regeln.md).

## Schnellstart

Das Paket ist nicht auf PyPI; installiert wird aus dem Repository.

<!-- quickstart:start -->
```bash
git clone https://github.com/GRADweight/autonomy.git
cd autonomy
python3 -m venv .venv
. .venv/bin/activate
pip install .
gw-autonomy validate examples/
gw-autonomy demo
```
<!-- quickstart:end -->

`gw-autonomy demo` spielt eine Lieferantenrechnung auf Grad 2 durch: Fall
prüfen, KI-Extraktion gegen den Beleg abgleichen, Belegprüfung, Freigabe mit
Rolle und Vier-Augen-Prinzip, Buchung über den bexio-Adapter (simuliert, kein
Netzwerk), Rollback-Pfad, Prüfung der Audit-Kette und eine erkannte
Manipulation.

## Beispiel: Beschreibung und Prüfergebnis

Auszug aus [examples/gw2-kreditorenrechnung.json](examples/gw2-kreditorenrechnung.json):

<!-- excerpt:examples/gw2-kreditorenrechnung.json -->
```json
{
  "level": 2,
  "who_plans": "model",
  "human_role": "per_action",
  "risk": {
    "foreign_input": true,
    "sensitive_data": true,
    "external_action": true,
    "money_effect": true
  },
  "controls": {
    "adoption_rate_monitoring": {"status": "implemented", "evidence": ["kred-uebernahmequote"]}
  },
  "evidence": [
    {
      "id": "kred-uebernahmequote",
      "type": "measurement",
      "ref": "evidence/gw2-kreditorenrechnung/uebernahmequote-2026-09.md",
      "date": "2026-10-02"
    }
  ]
}
```

Prüfung (mit festem Stichtag, damit das Alter der Nachweise reproduzierbar ist):

<!-- console -->
```console
$ gw-autonomy validate --as-of 2026-10-26 examples/gw2-kreditorenrechnung.json
examples/gw2-kreditorenrechnung.json  [gw2-kreditorenrechnung, Grad 2 (Copilot)]
  10:11  Warnung  GB-03  Fremde Eingaben, sensible Daten und Aussenwirkung zugleich: nur zulässig, weil bei Grad 2 ein Mensch jede Wirkung freigibt. Prüfen, ob das wirklich an jedem wirksamen Punkt gilt.
  Ergebnis: bestanden (0 Fehler, 1 Warnung, 0 Hinweise)

1 Datei geprüft, 0 nicht bestanden (0 Fehler, 1 Warnung, 0 Hinweise). Exit-Code 0.
```

Ein Fall, der die Rule of Two nur auf dem Papier erfüllt – Kundentexte fliessen
in Entscheide, `foreign_input` ist trotzdem `false`, die Isolation ist aber nur
geplant:

<!-- console -->
```console
$ gw-autonomy validate --as-of 2026-10-26 examples/negativ/n4-isolation-nur-behauptet.json
examples/negativ/n4-isolation-nur-behauptet.json  [n4-isolation-nur-behauptet, Grad 2 (Copilot)]
  28:33  Fehler   GB-07  Kontrolle «Überwachung der Übernahmequote» (adoption_rate_monitoring) ist erst geplant; bei Freigabe durch Menschen (Grad 2) Pflicht gegen Automation Bias.
  25:24  Fehler   GB-18  Kontrolle «Isolierte Vorklassifikation fremder Texte» (input_isolation) ist erst geplant; nur mit belegter Isolation fremder Texte darf foreign_input=false gesetzt werden.
  Ergebnis: nicht bestanden (2 Fehler, 0 Warnungen, 0 Hinweise)

1 Datei geprüft, 1 nicht bestanden (2 Fehler, 0 Warnungen, 0 Hinweise). Exit-Code 1.
```

Das Feldformat ist ein versioniertes JSON Schema
(`gw-autonomy schema`, Feldreferenz in [docs/schema.md](docs/schema.md)). Mit
`--check-evidence` prüft der Validator zusätzlich, ob die referenzierten
Nachweis-Dateien existieren und dem angegebenen SHA-256 entsprechen.

## In der CI: Policy-Gate und SARIF

| Exit-Code | Bedeutung |
|---|---|
| 0 | keine Befunde ab der Schwelle `--fail-on` (Standard: Fehler) |
| 1 | mindestens ein Befund ab der Schwelle |
| 2 | Aufruf- oder Eingabefehler (Datei fehlt, ungültige Option) |

`--format sarif` liefert SARIF 2.1.0 mit Zeile und Spalte je Befund. Die
Composite Action dieses Repos lässt sich direkt einbinden; die Befunde
erscheinen dann in GitHub Code-Scanning:

```yaml
- id: gate
  uses: GRADweight/autonomy@<COMMIT-SHA>   # auf einen Release-Commit fixieren
  with:
    paths: ki-faelle
- uses: github/codeql-action/upload-sarif@9b3254085494b55a0f7c4c2b3d2d52cc712ce370 # v4.39.1
  if: always()
  with:
    sarif_file: ${{ steps.gate.outputs.sarif-file }}
```

Vollständiges Beispiel, Eingaben und JSON-Bericht:
[docs/ci-integration.md](docs/ci-integration.md). Der Workflow
`policy-gate.yml` testet die Action in diesem Repo; die SARIF-Ausgabe wird in
der CI gegen das OASIS-Schema 2.1.0 validiert.

## Bausteine

Alle Module liegen im Paket `gradweight_autonomy` und nutzen nur die
Standardbibliothek.

| Modul | Zweck | Wichtigste Eigenschaft |
|---|---|---|
| `validator` | Use-Case-Beschreibung gegen Schema und Regeln prüfen | Nachweispflicht, SARIF |
| `approval` | Freigabe-Queue je Aktion | Rolle Pflicht, Vier-Augen-Prinzip, blockierende Vorprüfungen |
| `authz` | Freigabe-Policy (Rolle x Anwendungsfall) | deny by default, kein impliziter Superuser |
| `audit` | Audit-Trail in SQLite | Hash-Kette (SHA-256/HMAC), `verify()`, Export ([Details](docs/audit-trail.md)) |
| `source_check` | Zahlen- und Quellenabgleich für KI-Antworten | Schweizer Zahlenformate, Quellenverweise ([Details](docs/zahlenabgleich.md)) |
| `llm` | optionale Zweitmodell-Prüfung über OpenAI-kompatible API | fail-closed, strikte JSON-Prüfung |
| `invoice_checks` | Schweizer Belegprüfung | IBAN, QR-Referenz, SCOR, MWST, UID ([Details](docs/belegpruefung.md)) |
| `bexio` | Lieferantenrechnung in bexio anlegen | nur mit bestandener Belegprüfung, persistente Limiten |
| `exception_queue` | Ausnahmen deterministisch an Menschen | feste Schwellen, finale Entscheide |
| `sampling_audit` | reproduzierbare Stichproben über den Audit-Trail | Bericht wird selbst protokolliert |
| `rollback` | Umkehrbefehle registrieren | nicht umkehrbare Aktionen werden ausdrücklich markiert |
| `tracing` | Metadaten von Modellaufrufen | keine Prompt-Inhalte |

Belegprüfung als Vorprüfung vor der Freigabe:

<!-- doctest -->
```python
>>> from datetime import date
>>> from decimal import Decimal
>>> from gradweight_autonomy.approval import ApprovalQueue
>>> from gradweight_autonomy.audit import AuditTrail
>>> from gradweight_autonomy.authz import ApprovalPolicy
>>> from gradweight_autonomy.invoice_checks import InvoiceFacts, VatLine, check_invoice
>>> beleg = check_invoice(InvoiceFacts(
...     iban="CH44 3199 9123 0008 8901 2", reference="21 00000 00003 13947 14300 09017",
...     supplier_uid="CHE-100.155.212 MWST", supply_date=date(2026, 9, 30), currency="CHF",
...     gross=Decimal("1081.00"),
...     vat_lines=(VatLine(Decimal("8.1"), Decimal("1000.00"), Decimal("81.00")),)))
>>> beleg.passed
True
>>> audit = AuditTrail()
>>> queue = ApprovalQueue(audit=audit, policy=ApprovalPolicy({"kreditoren": ["buchhaltung"]}))
>>> aktion = queue.propose(tenant="muster-ag", use_case="kreditoren", title="RE-2026-0042 buchen",
...                        payload={"betrag": "1081.00"}, checks=[beleg.to_check_outcome()])
>>> queue.approve(aktion, actor="a.beispiel", role="buchhaltung").status
'approved'
>>> audit.verify().ok
True
```

## Grenzen

Der Validator prüft Widerspruchsfreiheit und Nachweise, nicht die Wahrheit der
Nachweise; eine falsche Beschreibung mit plausiblen Nachweisen besteht. Der
Audit-Trail erkennt Manipulationen, verhindert sie nicht, und braucht für
Kürzungen am Ende einen externen Anker. Die Bausteine sind keine Laufzeit für
Agenten, keine Authentisierung und kein Ersatz für eine Revision. Der
bexio-Adapter ist gegen die öffentliche API-Dokumentation gebaut, aber nicht
gegen ein echtes Konto getestet. Vollständige Liste:
[docs/grenzen.md](docs/grenzen.md).

## Regulatorische Einordnung

Kein Rechtsrat. Die Regeln verweisen auf die jeweiligen Grundlagen, unter
anderem:

| Grundlage | Bezug |
|---|---|
| revDSG (SR 235.1) Art. 21 | automatisierte Einzelentscheide: Überprüfung durch eine Person (GB-21) |
| EU AI Act Art. 14 Abs. 4 | Automation Bias (GB-07), Übersteuern und Anhalten (GB-12), Hochrisiko-Aufsicht (GB-22) |
| EU AI Act Art. 12 | Protokollierung (Audit-Trail, GB-22) |
| VO (EU) 2023/1230 | Schutzfunktionen ausserhalb des Modells (GB-06) |
| ISO/IEC 42001:2023 Abschnitt 7.5 | dokumentierte Information (Nachweispflicht GB-19/GB-20) |
| OWASP LLM06:2025, Meta «Agents Rule of Two» | Grenzen im System statt im Prompt, Rule of Two (GB-03, GB-08, GB-09) |

Daten, Geltungsbereich und weitere Quellen (FINMA-Aufsichtsmitteilung 08/2024,
NIST AI RMF): [docs/regulatorik.md](docs/regulatorik.md).

## Entwicklung

Eine Distribution `gradweight-autonomy` im src-Layout: Validator und Bausteine
teilen Regel-IDs und Begriffe, werden gemeinsam versioniert und haben keine
Laufzeit-Abhängigkeiten. Entwicklungswerkzeuge kommen über `uv`:

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest --cov
```

Beiträge: [CONTRIBUTING.md](CONTRIBUTING.md) · Sicherheitslücken:
[SECURITY.md](SECURITY.md) · Änderungen: [CHANGELOG.md](CHANGELOG.md) ·
Vorlagen für Register, Richtlinie und Rollen: [governance/](governance/README.md)

## Lizenz und Kontakt

MIT, © 2026 GRADweight GmbH, siehe [LICENSE](LICENSE). Alle Beispiele und
Nachweise im Repo sind erfunden. Kontakt: mail@gradweight.ch
