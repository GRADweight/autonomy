# Mitmachen

Das ist kein «fork and pray»-Repo. Wir freuen uns über PRs — und wir prüfen
sie, weil sich Leute darauf verlassen.

## Wie du einen Fall beitragen kannst

Jeder Autonomie-Prüffall in `examples/` ist eine JSON-Datei nach dem
Schema in `packages/gradbuild/gradbuild/schema.py`. Wenn du einen Fall
hinzufügen möchtest:

1. **Zuerst die JSON schreiben.** Pflichtfelder: `id`, `title`, `level`,
   `who_plans`, `human_role`, `foreign_input`, `sensitive_data`,
   `external_action`, `money_effect`, `customer_facing`,
   `customer_text_in_decisions`, `safety_critical`, `data_class`,
   und das `governance`-Objekt (12 Felder, Pflicht je nach Grad).
2. **Gegen den Validator validieren:**
   `python -m gradbuild.cli examples/dein-fall.json`
   → muss mit Exit 0 durchgehen.
3. **Testfall-JSON nicht umbenennen.** Die `id` ist die Dateiname-Referenz.
4. **Pull Request öffnen**, mit einem Satz: «Was ist das für ein Grad und
   warum ist das so und nicht anders?»

## Was wir NICHT annehmen (wird im Review abgelehnt)

- Fälle, bei denen `level >= 4` aber die `governance`-Pflichtfelder
  (GB-11, GB-12, GB-13, GB-14) fehlen. Der Validator wehrt das ab —
  aber wenn du die Frage *warum* nicht begründen kannst, fehlt uns etwas.
- Beispiele, die auf «unser LLM ist gut genug» basieren. Das ist kein
  Argument. Die Grenze muss systemseitig sein (GB-09, GB-03, GB-06).
- Doku-Änderungen, die Quellen (DSG Artikel, AI Act Anhang, ISO-Nummer)
  entfernen oder «aktualisiert» schreiben, ohne die Quelle + Datum zu nennen.
- Marketing-Begriffe in Kommentare und Doku: «KI-Magie», «revolutionär»,
  「revolutionär」, «wir sind die besten», «end-to-end KI-Plattform».
  Schreibe, was der Code tut. Nicht, was er «könnte».

## Code-Beiträge

`packages/gw_core/` ist bewusst klein. Neue Bausteine sind willkommen,
wenn sie:

- **null externe Abhängigkeiten** haben (oder: `httpx` — und das ist die
  Ausnahme, die explizit dokumentiert ist),
- **unittest-basierte Tests** haben (keinen neuen Test-Framework-Import),
- **append-only Logik** bevorzugen (einmal geschrieben, nie gelöscht),
- im `__init__.py` exportiert werden.

Branchen-Modell: `feature/<thema>` → Squash-Merge nach `main`.
`main` ist always-green: die CI läuft `pytest` auf beide Pakete und
validiert alle JSON-Dateien in `examples/`.

## Security

Falls du eine Schwachstelle in einem der Bausteine findest: **nicht**
öffentlich in Issues, sondern an `gradweight.ch` oder über
[SECURITY.md](SECURITY.md).
