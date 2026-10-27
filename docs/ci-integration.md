# CI-Integration: Policy-Gate und Code-Scanning

`gw-autonomy validate` eignet sich als Gate in jeder CI: Exit-Code für die
Entscheidung, SARIF 2.1.0 für die Anzeige der Befunde an der richtigen
Zeile.

## Exit-Codes

| Code | Bedeutung |
|---|---|
| 0 | keine Befunde ab der Schwelle `--fail-on` (Standard: `error`) |
| 1 | mindestens ein Befund ab der Schwelle |
| 2 | Aufruf- oder Eingabefehler: Datei fehlt, Verzeichnis ohne `.json`, ungültige Option. Kein Prüfergebnis. |

Syntaxfehler, doppelte Schlüssel und Schemaverletzungen in einer Datei sind
Befunde (GB-01, Exit-Code 1) mit Zeile und Spalte, keine Aufruffehler.

`--fail-on warning` macht auch Warnungen blockierend, `--fail-on never`
erzeugt nur den Bericht.

## GitHub Actions mit Code-Scanning

Das Repo enthält eine Composite Action (`action.yml`). Sie installiert den
Validator in ein eigenes venv und schreibt eine SARIF-Datei. Das Hochladen
übernimmt die Action von GitHub:

```yaml
name: KI-Policy
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  autonomy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      security-events: write   # für den SARIF-Upload
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - id: gate
        # Auf den Commit-SHA eines Release-Tags von GRADweight/autonomy fixieren.
        uses: GRADweight/autonomy@<COMMIT-SHA>
        with:
          paths: ki-faelle
          fail-on: error
          check-evidence: "true"
      - uses: github/codeql-action/upload-sarif@9b3254085494b55a0f7c4c2b3d2d52cc712ce370 # v4.39.1
        if: always()
        with:
          sarif_file: ${{ steps.gate.outputs.sarif-file }}
          category: gw-autonomy
```

`if: always()` lädt die Befunde auch dann hoch, wenn das Gate scheitert. Die
Regeln erscheinen in Code-Scanning mit Titel, Begründung, Behebung und Link
auf die [Regel-Referenz](regeln.md).

Eingaben der Action:

| Eingabe | Standard | Bedeutung |
|---|---|---|
| `paths` | – | Dateien oder Verzeichnisse, durch Leerzeichen getrennt |
| `fail-on` | `error` | Schwelle für den Exit-Code |
| `sarif-file` | `gw-autonomy.sarif` | Ausgabedatei (auch als Output `sarif-file`) |
| `check-evidence` | `true` | lokale Nachweis-Dateien und SHA-256 prüfen |
| `python-version` | `3.12` | Python für den Validator |

In diesem Repo testet der Workflow `.github/workflows/policy-gate.yml` die
Action: Die Beispiele müssen bestehen, die Negativbeispiele müssen scheitern,
und beide SARIF-Dateien werden gegen das OASIS-Schema 2.1.0 validiert.

## Andere CI-Systeme

Ohne Action genügt eine Installation aus dem Repository:

```bash
python -m venv .gw && .gw/bin/pip install "git+https://github.com/GRADweight/autonomy@<COMMIT-SHA>"
.gw/bin/gw-autonomy validate --format json --output gw-autonomy.json --check-evidence ki-faelle
```

Der JSON-Bericht (`report_version` 1) enthält je Datei Fall-ID, Grad,
Ergebnis und alle Befunde mit Regel, Schweregrad, Meldung, JSON Pointer,
Zeile und Spalte.

## Stichtag

Das Alter von Nachweisen (GB-20) bezieht sich auf das heutige Datum. Für
reproduzierbare Läufe kann ein Stichtag gesetzt werden: `--as-of 2026-10-26`
oder die Umgebungsvariable `GW_AUTONOMY_AS_OF`.
