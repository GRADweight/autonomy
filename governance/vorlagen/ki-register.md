# KI-Register (Vorlage) — eine Tabelle, keine Blackbox

> Ein KI-Register ist nicht eine «Datenbank aller KI-Tools». Es ist die
> Beleg-Sammlung für die Frage: «Welche KI-Anwendungen haben Aussenwirkung,
> auf welchem Grad, und wer ist dafür verantwortlich?»
>
> **Format:** Markdown-Tabelle (anpassbar, versionierbar, diffbar).
> Wer ein XLSX braucht: exportieren. Wer beides will: Tabelle als Source
> of Truth, XLSX davon abgeleitet.

## Legende

- **Grad:** 0 = keine schreibende Aktion … 5 = Multi-Agent (Def.: `docs/plan.md`)
- **Zustand:** `shadow` / `live` / `degraded` / `stopp` / `ausserbetrieb`
- **Fall-JSON:** der validierte Autonomie-Fall (Pfad im Repo oder im System)
- **Freigabe:** Datum der letzten Grad-Freigabe + Rolle der Freigabenden

## Das Register

| # | Anwendung | Zweck | Grad | Zustand | Fremde Eingaben | Sensible Daten | Aussenwirkung | Geld | Datenklasse | Owner | Fall-JSON | Freigabe (Rolle, Datum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Beleg: RAG-Interne-Dokumente | Wissenssuche für Fachbereiche | 01 | live | nein | ja (intern) | nein | nein | intern | <name> | `examples/gw1-...json` | fachverantwortlich, 2026-10 |
| 2 | Beleg: Rechnungs-Extraktion | Extraktion + Führung in Buchhaltung | 02 | live | nein | ja (vertraulich) | ja (Buchhaltung) | ja | vertraulich | <name> | `examples/gw2-...json` | fachverantwortlich, 2026-10 |
| 3 | (eigener Eintrag) | | | | | | | | | | | |

## Regeln fürs Register

1. **Eine Zeile pro Anwendung.** Nicht pro Abteilung, nicht pro Dienstleister.
   Eine Anwendung, die in mehreren Abteilungen genutzt wird, hat einen
   Owner und eine Zeile.
2. **Neue Anwendung → neue Zeile VOR dem ersten Live-Tag.** Nicht danach.
   (Die häufigste Ausnahme ist auch die teuerste: die Anwendung existiert
   erst, als jemand sie im Register suchen will.)
3. **Grad-Änderung = neue Freigabe.** Eine Zeile mit «Grad 02 → 04»
   braucht einen neuen validierten Fall-JSON, eine neue Freigabe und ein
   neues Datum. Das alte Datum bleibt sichtbar (Verlaufsbeleg).
4. **Keine Zeile ohne Fall-JSON.** Ein Anwendungs-Name ohne validierten
   Prüffall ist ein Wunsch, kein Register-Eintrag.
5. **`stopp` und `ausserbetrieb` bleiben im Register.** Ein gelochtes
   Register lügt. Gelöschte Anwendungen sind `ausserbetrieb` mit Datum
   und Begründung — die Zeile bleibt, der Zustand wechselt.

## Export-Beispiel (CSV-Spalten, identisch zur Tabelle)

```
nr,anwendung,zweck,grad,zustand,fremde_eingaben,sensible_daten,aussenwirkung,geld,datenklasse,owner,fall_json,freigabe_rolle,freigabe_datum
```
