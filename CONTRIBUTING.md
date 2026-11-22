# Mitwirken

Beiträge sind willkommen: Korrekturen, neue Beispiele, Regeln oder Bausteine.
Bitte vorab ein Issue eröffnen, wenn sich das Verhalten einer Regel ändert.

## Entwicklungsumgebung

```bash
uv sync                       # Python >= 3.10, Entwicklungswerkzeuge aus pyproject.toml
uv run ruff check .
uv run ruff format --check .
uv run mypy                   # --strict auf src/
uv run pytest --cov           # Coverage-Schwelle 90 %
```

Abhängigkeiten werden nicht gesperrt (Bibliothek); die CI nutzt die neuesten
kompatiblen Versionen der Entwicklungswerkzeuge. Der Paketkern bleibt ohne
Laufzeit-Abhängigkeiten.

## Konventionen

- Bezeichner im Code Englisch, Meldungen, Docstrings und Doku Deutsch
  (Schweizer Rechtschreibung mit «ss», echte Umlaute).
- Sicherheitslogik fail-closed: Im Zweifel ablehnen, nie still weiterlaufen.
- Kein Netzwerkzugriff in Tests; externe Dienste über austauschbare
  Transports oder einen lokalen `http.server`.
- Nur erfundene oder öffentliche Daten in Beispielen und Tests.

## Regeln ändern oder ergänzen

1. Regel in `src/gradweight_autonomy/validator/rules.py` anpassen (Metadaten
   und Prüfung), bei neuen Kontrollen auch `model.py` und das JSON Schema.
2. Gezielte Tests in `tests/validator/test_rules.py` ergänzen; betroffene
   Beispiele und die erwarteten Regeln der Negativbeispiele nachführen.
3. Regel-Referenz neu erzeugen:
   `uv run gw-autonomy rules --format markdown > docs/regeln.md`
4. Fachliche Aussagen (Gesetz, Norm, Datum) mit Quelle belegen.
5. Eintrag im [CHANGELOG](CHANGELOG.md) unter «Unreleased».

## Commits und Pull Requests

Kleine, logische Commits mit aussagekräftiger Nachricht. Ein Pull Request ist
bereit, wenn die CI grün ist; die Vorlage listet die Prüfpunkte.

## Sicherheitslücken

Nicht öffentlich melden, sondern wie in [SECURITY.md](SECURITY.md) beschrieben.
