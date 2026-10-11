## Was ändert sich?

(1–3 Sätze. Was ist anders als vorher?)

## Warum?

(Nicht: «wir könnten». Sondern: «weil <konkreter Zustand> →
<konkrete Folge>».)

## Falls es an das Modell (GB-xx) ändert:

- Regle-ID:
- Was sich ändert (Text):
- Welche Beispiele in `examples/` betroffen sind (Datei-Namen):
- Welche neuen Tests du geschrieben hast (Datei + Name):

## Prüfung

- [ ] `pytest tests_gradbuild tests_gwcore` → grün
- [ ] `python -m gradbuild.cli examples/...` → Exit 0 (betroffene Fälle)
- [ ] Neue Regel/Baustein ist in `README.md` / `docs/` verlinkt
