# Zahlen- und Quellenabgleich

`gradweight_autonomy.source_check.check_numbers` prüft deterministisch, ob jede
Zahl einer Antwort in den Quellen steht. Typischer Einsatz: nach einer
RAG-Antwort oder einer KI-Extraktion, bevor ein Mensch die Antwort sieht oder
eine Aktion vorgeschlagen wird.

```python
from gradweight_autonomy.source_check import Source, check_numbers

quellen = [Source("AGB: Rückgabe innert 30 Tagen.", "agb.pdf")]
ergebnis = check_numbers("Sie können 30 Tage lang zurückgeben [1].", quellen)
ergebnis.passed  # True
```

## Was erkannt wird

| Art | Beispiele | Vergleich |
|---|---|---|
| Beträge | `CHF 1'234.50`, `1’234.–`, `1234,50 EUR`, `1.234,50 €`, `USD 1,234.50` | Wert; Währung muss passen, wenn beide eine haben |
| Zahlen und Prozente | `8.1 %`, `8,1%`, `2.6 Prozent`, `-5 %`, `1.234.567` | Wert und Einheit |
| Daten | `31.07.2026`, `1.7.26`, `2026-07-31`, `31. Juli 2026` | Kalenderdatum |
| Uhrzeiten | `14:30`, `9:05:00` | Uhrzeit |
| Kennungen | IBAN `CH93 0076 …`, QR-Referenz, UID `CHE-…` | Zeichenfolge ohne Leerzeichen |

Nicht als Zahlen gelten: Quellenverweise (`[2]`, `[1, 3]`, `[1-3]`, `[^4]`),
Aufzählungsnummern am Zeilenanfang (`1.`, `2)`) und Ziffern in Bezeichnern
(`A4`, `Q3`, `GB-03`, `v1.2.3`). Ein Jahr wird auch durch ein Datum dieses
Jahres belegt.

## Zitierpflicht

Mit `require_citations=True` muss jeder Satz mit Zahlen einen Verweis
`[n]` tragen, und die Zahl muss in einer der dort zitierten Quellen stehen
(1-basiert auf die Liste `sources`). Gründe für Befunde: «Satz ohne
Quellenverweis», «nicht in [1]», «Verweis auf unbekannte Quelle [7]».

## Grenzen

- Geprüft werden nur Zahlen. Eine falsche Aussage ohne Zahl, eine korrekte
  Zahl im falschen Zusammenhang oder eine Umformulierung bleiben unerkannt.
- Jede Zahl muss belegt sein; auch «in 2 Schritten» führt ohne Beleg zum
  Befund. Das ist gewollt (lieber ein Fehlalarm als eine erfundene Zahl).
- Tausendertrennung mit gewöhnlichem Leerzeichen (`1 234`) wird nicht als eine
  Zahl gelesen (mehrdeutig); geschütztes und schmales Leerzeichen schon.
  `1,234` gilt als Dezimalzahl 1.234.
- Satzgrenzen bei der Zitierpflicht sind heuristisch; Abkürzungen wie «Nr.»
  können einen Satz trennen und so einen (sicheren) Fehlalarm auslösen.

## Optional: Zweitmodell-Prüfung

`gradweight_autonomy.llm.SecondModelReview` fragt ein zweites Modell über eine
OpenAI-kompatible API (`POST {base_url}/chat/completions`), ob die Antwort
durch die Quellen gedeckt ist. Beispiel mit einem lokalen Ollama:

```python
from gradweight_autonomy.llm import ChatClient, ChatConfig, SecondModelReview

client = ChatClient(ChatConfig(base_url="http://localhost:11434/v1", model="qwen2.5:14b"))
urteil = SecondModelReview(client).review(antwort, quellen)
if not urteil.passed:
    ...  # nicht weitergeben
```

Eigenschaften: nur Standardbibliothek, Timeout, Wiederholung mit
exponentiellem Backoff bei Netzfehlern und HTTP 408/429/5xx, strikte Prüfung
der JSON-Antwort (genau die Felder `verdict` und `unsupported_claims`,
widerspruchsfrei). Jeder Fehler ergibt `passed=False`.

Das Zweitmodell ist selbst fehlbar und kann durch präparierte Quellen
beeinflusst werden. Es ergänzt den deterministischen Abgleich, es ersetzt ihn
nicht; fällt der Dienst aus, blockiert die Prüfung (fail-closed).
