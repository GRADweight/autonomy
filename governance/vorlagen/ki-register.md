# KI-Register (Vorlage)

> Das Register beantwortet: Welche KI-Anwendungen sind im Einsatz, auf welchem
> Grad, mit welcher Wirkung, und wer ist verantwortlich? Format: Markdown-Tabelle
> (versionierbar, diffbar); bei Bedarf als CSV exportieren.

## Legende

- **Grad:** 0 bis 5 gemäss [Autonomiemodell](../../docs/autonomiegrade.md)
- **Zustand:** `schatten` / `live` / `zurueckgestuft` / `gestoppt` / `ausser_betrieb`
- **Fall:** Pfad der Use-Case-Beschreibung, die mit `gw-autonomy validate` geprüft ist
- **Abnahme:** Datum und Rolle der letzten Abnahme des Grads

## Register

| Nr. | Anwendung | Zweck | Grad | Zustand | Fremde Eingaben | Sensible Daten | Aussenwirkung | Geld | Datenklasse | Verantwortlich (Rolle) | Fall | Abnahme |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Produktwissen Innendienst | Antworten aus Katalog und Offerten | 1 | live | nein | ja | nein | nein | intern | Leitung Innendienst | `examples/gw1-produktwissen-innendienst.json` | Leitung Innendienst, 2026-09 |
| 2 | Kreditorenrechnungen | Buchungsvorschlag, Freigabe je Buchung | 2 | live | ja | ja | ja | ja | vertraulich | Leitung Finanzen | `examples/gw2-kreditorenrechnung.json` | Leitung Finanzen, 2026-10 |
| 3 | (eigener Eintrag) | | | | | | | | | | | |

## Regeln

1. **Eine Zeile je Anwendung**, unabhängig davon, wie viele Abteilungen sie nutzen.
2. **Eintrag vor dem ersten produktiven Einsatz**, nicht danach.
3. **Grad-Änderung heisst neue Abnahme:** neue Fall-Beschreibung, neue Prüfung,
   neues Datum. Der frühere Stand bleibt in der Versionsgeschichte sichtbar.
4. **Keine Zeile ohne geprüften Fall.** Ein Name ohne Fall-Beschreibung ist ein
   Vorhaben, kein Registereintrag.
5. **Gestoppte und ausser Betrieb genommene Anwendungen bleiben** im Register,
   mit Datum und Begründung.

## CSV-Spalten

```text
nr,anwendung,zweck,grad,zustand,fremde_eingaben,sensible_daten,aussenwirkung,geld,datenklasse,verantwortlich,fall,abnahme
```
