# Changelog

Alle nennenswerten Änderungen werden hier festgehalten. Format nach
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionierung nach
[Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [2.0.0] – 2026-10-27

Grundlegende Überarbeitung. Inkompatibel zu 1.x (Paketname, Import-Namen,
Schema der Use-Case-Beschreibung).

### Hinzugefügt

- Versioniertes JSON Schema 2.0 für Use-Case-Beschreibungen
  (`gw-autonomy schema`), geprüft mit einem schlanken Validator ohne
  Abhängigkeiten; Übereinstimmung mit `jsonschema` wird differenziell getestet.
- Regeln GB-17 bis GB-22: widerspruchsfreie Risikomerkmale, belegter
  Strukturbruch der Rule of Two, Nachweispflicht mit zulässigen Nachweistypen,
  Nachweisqualität (Datum, Alter, Datei, SHA-256), automatisierte
  Einzelentscheide nach revDSG Art. 21, Hochrisiko nach EU AI Act Art. 12/14.
- Regel-Metadaten (Titel, Prüfgegenstand, Begründung, Referenzen, Behebung,
  Schweregrad je Grad) als einzige Quelle; `docs/regeln.md` und
  `docs/schema.md` werden daraus erzeugt.
- Ausgabe als Text, JSON und SARIF 2.1.0 mit Zeile und Spalte je Befund;
  Composite Action (`action.yml`) für GitHub Code-Scanning.
- Audit-Trail mit Hash-Kette (SHA-256 oder HMAC-SHA-256), `verify()`,
  externer Kopf-Anker, JSONL-/CSV-Export, `gw-autonomy audit verify|export|verify-export`.
- Schweizer Belegprüfung (`invoice_checks`): IBAN CH/LI, QR-IBAN, QR-Referenz,
  Creditor Reference, MWST-Sätze nach Leistungsdatum, UID; als blockierende
  Vorprüfung in der Freigabe-Queue.
- Optionale Zweitmodell-Prüfung über eine OpenAI-kompatible API (`llm`).
- `gw-autonomy demo`: Kreditorenrechnung Grad 2 von der Prüfung bis zur Buchung.
- Beispiele auf Schema 2.0 mit fiktiven Nachweis-Dateien, Negativbeispiele mit
  erwarteten Regeln, neuer Fall `gw2-kreditorenrechnung`.
- CI: ruff, mypy `--strict`, Tests unter Python 3.10/3.12/3.13 mit
  Coverage-Schwelle 90 %, Paketbau mit Installation in frischem venv, gitleaks,
  pip-audit, Validierung der SARIF-Ausgabe gegen das OASIS-Schema; Dependabot.

### Geändert

- Eine Distribution `gradweight-autonomy` (Import `gradweight_autonomy`,
  Python ≥ 3.10) statt der Pakete `gradbuild` und `gw-core`. Begründung:
  gemeinsame Regel-IDs und Begriffe, gemeinsame Versionierung, keine
  Laufzeit-Abhängigkeiten in beiden Teilen.
- Bezeichner durchgehend Englisch, Meldungen und Doku Deutsch.
- «Zweitmodell-Prüfung» heisst jetzt **Zahlen- und Quellenabgleich**
  (`source_check`), weil kein Modell beteiligt ist.
- bexio-Adapter auf `POST /4.0/purchase/bills` mit den Feldern der aktuellen
  API, `urllib` statt `httpx`, Limiten in persistentem Ledger, Belegprüfung
  Pflicht, kein Retry bei Buchungen.
- Freigabe-Queue fail-closed: Rolle Pflicht, Vier-Augen-Prinzip, nur offene
  Aktionen entscheidbar, blockierende Vorprüfungen.
- Freigabe-Policy ohne implizite Superuser-Rolle; fehlende Policy-Datei ist ein
  Fehler.
- Lizenz einheitlich MIT (Root und Paket-Metadaten nach PEP 639).

### Behoben

- Quellenverweise wie `[2]` wurden als Zahlen gewertet und blockierten
  korrekte Antworten.
- GB-10 griff nicht, wenn zusätzlich sensible Daten verarbeitet wurden.
- GB-05 enthielt toten Code und eine fest auf Retouren verdrahtete Begründung.
- Maschinenverordnung: in Kraft seit 19.07.2023, anwendbar ab 20.01.2027
  (vorher: «in Kraft seit 2027»).
- Zeitstempel im Tracing wurden einmal beim Import gesetzt.
- Installiertes Paket `gradbuild` scheiterte beim Laden der Beispiele.
- Verweise auf nicht existierende und private Dokumente entfernt.

### Entfernt

- `packages/gradbuild`, `packages/gw_core`, die Doppelung der Beispiele,
  `governance/checks` (zweite, abweichende Regelquelle), die A2A-Agent-Card
  mit Platzhaltern und Entwurfsdokumente mit nicht belegten Angaben.

### Migration von 1.x

| 1.x | 2.0 |
|---|---|
| `python -m gradbuild.cli fall.json` | `gw-autonomy validate fall.json` |
| `gradbuild.evaluate_case(case)` | `gradweight_autonomy.validator.validate_case(case)` |
| Booleans in `governance` | `controls.<kontrolle>` mit `status` und `evidence` |
| `data_class`, `data_residency` | `data.classification`, `data.residency` |
| `mandate.money_limit` (Text) | `mandate.money_limit` mit `amount`, `currency`, `per` |
| `gw_core.AuditTrail.log(mandant=…, prototyp=…)` | `gradweight_autonomy.audit.AuditTrail.append(tenant=…, use_case=…)` |
| `gw_core.verify.pruefe_antwort` | `gradweight_autonomy.source_check.check_numbers` |
| `ApprovalQueue.vorschlage/freigabe/anpassen/zurueckstellen` | `propose/approve/amend/reject` |

## [1.0.0] – 2026-10-12

Erste öffentliche Fassung: Autonomiemodell, Validator `gradbuild` mit den
Regeln GB-01 bis GB-16, Governance-Bausteine `gw_core`, Beispiele für die
Grade 0 bis 5.

[Unreleased]: https://github.com/GRADweight/autonomy/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/GRADweight/autonomy/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/GRADweight/autonomy/releases/tag/v1.0.0
