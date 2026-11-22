# Das Autonomiemodell

Ein KI-Anwendungsfall wird nicht mit «KI ja oder nein» beschrieben, sondern mit
zwei Fragen:

1. **Wer plant den Weg?** (`who_plans`): ein Mensch (`human`), eine fest
   programmierte Kette (`fixed_chain`) oder das Modell (`model`).
2. **Wo greift der Mensch ein?** (`human_role`): bei jedem Schritt
   (`full_control`), bei jeder Aktion (`per_action`), an definierten Toren
   (`per_gate`), über ein Mandat mit Grenzen (`mandate`) oder nur noch bei
   Ausnahmen (`exception_only`).

Aus der Kombination folgt der Grad. Strenger freigeben als nötig ist immer
erlaubt (ein Agent im Vorschlagsmodus ist Grad 2); lockerer nicht. Eine feste
Kette ist nie Grad 4 oder 5, weil dort kein Modell den Weg wählt.

| Grad | Name | Kurz | Beispiel im Repo |
|---|---|---|---|
| 0 | Keine KI-Autonomie | Menschen arbeiten, KI liefert höchstens Recherche | `gw0-marktforschung` |
| 1 | Assistent | KI antwortet, Menschen handeln; keine Aussenwirkung | `gw1-produktwissen-innendienst` |
| 2 | Copilot | KI schlägt Aktionen vor, ein Mensch gibt jede frei | `gw2-kreditorenrechnung`, `gw2-bewerbungsvorsortierung` |
| 3 | Workflow | feste Kette mit menschlichen Toren | `gw3-predictive-maintenance` |
| 4 | Agent mit Mandat | Modell handelt innerhalb technisch erzwungener Grenzen | `gw4-c-teile-nachbestellen` |
| 5 | Autonom mit Ausnahmesteuerung | Menschen sehen nur Ausnahmen und Stichproben | `gw5-standardretouren` |

Die genauen zulässigen Kombinationen stehen in der generierten
[Regel-Referenz](regeln.md#zulässige-achsen-je-grad-gb-02).

## Was jeder Grad zusätzlich verlangt

Höhere Grade sind nicht verboten, sie kosten Kontrollen. Der Validator prüft,
dass diese Kontrollen deklariert **und belegt** sind (GB-19).

| Ab | Kontrollen | Regeln |
|---|---|---|
| Grad 1 | keine Aussenwirkung | GB-10 |
| Grad 2 und 3 mit menschlicher Freigabe | Übernahmequote messen (Automation Bias) | GB-07 |
| Grad 3 | Incident-Prozess, automatische Rückstufung, getesteter Notaus, Messung (pass^k oder Schattenbetrieb), Neubeurteilung bei Modellwechsel | GB-12, GB-14 |
| Grad 4 | Audit-Trail, eigene Agenten-Identität, Schattenbetrieb und Vorschlagsphase vor dem Mandat, Mandat im Zielsystem, Betragsgrenze bei Geldwirkung | GB-08, GB-09, GB-11, GB-13 |
| `exception_only` (jeder Grad) | Ausnahme-Queue und Stichproben-Audit | GB-11 |

## Drei harte Grenzen

- **Rule of Two (GB-03).** Fremde Eingaben, sensible Daten und Aussenwirkung
  zugleich sind bis Grad 3 nur mit Warnung zulässig (ein Mensch bricht die
  Kette), ab Grad 4 ein Fehler. Ausweg: eine Eigenschaft strukturell
  entfernen, zum Beispiel nur EDI-Daten statt Freitext verarbeiten. Wer das
  über `foreign_input=false` deklariert, obwohl Kundentexte einfliessen, muss
  die isolierte Vorklassifikation belegen (GB-18).
- **Schutzfunktionen (GB-06).** Bei sicherheitsrelevanten Funktionen bleibt die
  KI beratend; höchstens Grad 3.
- **Geld (GB-09).** Ohne Freigabe je Aktion braucht jede Geldwirkung eine
  bezifferte Grenze, die im Zielsystem durchgesetzt wird – nicht im Prompt.

## Selbstauskunft und Nachweis

Eine Use-Case-Beschreibung ist eine Selbstauskunft. Der Validator kann nicht
prüfen, ob ein Notaus wirklich funktioniert. Er prüft aber:

- ob die Angaben **widerspruchsfrei** sind (GB-17: Geldwirkung ohne
  Aussenwirkung, vertrauliche Daten ohne `sensitive_data` usw.),
- ob jede als umgesetzt deklarierte Kontrolle auf einen **Nachweis passenden
  Typs** verweist (GB-19: ein Notaus verlangt ein Testprotokoll, keine
  Konfigurationsdatei),
- ob Nachweise **gültig datiert, nicht veraltet** und – mit `--check-evidence` –
  als Datei vorhanden und per SHA-256 an die geprüfte Fassung gebunden sind
  (GB-20).

Damit wird aus einer Checkliste ein prüfbares Dossier. Ob die Nachweise
inhaltlich stimmen, bleibt Aufgabe einer menschlichen Prüfung (siehe
[Grenzen](grenzen.md)).

## Vom Grad zur Umsetzung

| Grad | Passende Bausteine (`gradweight_autonomy.*`) |
|---|---|
| 1 | `source_check` (Zahlen- und Quellenabgleich), optional `llm.SecondModelReview` |
| 2 | zusätzlich `approval` (Freigabe-Queue), `authz` (Rollen), `audit` (Hash-Kette), `invoice_checks` als Vorprüfung |
| 3 | zusätzlich `rollback` (Umkehrbefehle), `tracing` |
| 4 | zusätzlich Zielsystem-Adapter mit Limiten (Beispiel `bexio`) in einem eigenen Dienst |
| 5 | zusätzlich `exception_queue` und `sampling_audit` |

Der Ablauf in Phasen (beschreiben, umsetzen, abnehmen, betreiben) steht in
[vorgehen.md](vorgehen.md).
