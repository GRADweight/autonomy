# Phase 5 · Inbetriebnahme — Rollout, Betrieb, Rollback, Ausserbetriebnahme

«Inbetriebnahme» ist kein Moment. Es ist ein Zustand, den wir erreichen
und den wir halten. Diese Seite beschreibt, was «halten» konkret heisst.

## Die vier Betriebszustände

| Zustand | Was das heisst | Wer ist zuständig |
|---|---|---|
| **Shadow** | Das System läuft, aber es darf keine schreibende Aktion ausführen. Alle Antworten werden geloggt, keine Freigabe erteilt. | Betreiber |
| **Live** | Freigabe-Kette aktiv, rollenbasiertes Entscheiden, Audit-Trail läuft | Betreiber + fachverantwortliche Rolle |
| **Degraded** | Ein Baustein streikt (LLM-Timeout, Zielsystem-Ausfall). Das System fällt auf den nächst-niedrigeren Grad zurück: keine Freigabe, nur Vorschlag. | Betreiber |
| **Stopp** | Kill-Switch aktiv. Keine Freigabe, kein Zielsystem, nur Log. | Betreiber + admin |

Der Übergang Shadow → Live ist die **einzige** Freigabe, die nicht
pro-Aktion erteilt wird. Er erfordert:
- Abschluss-Protokoll (Phase 4, alle Kriterien erfüllt)
- Eintrag im KI-Register: `zustand="produktiv"`
- Benachrichtigung der betroffenen Rollen (welche Rolle darf jetzt was
  freigeben — das steht in der `FreigabePolicy`, nicht in einem Intranet-Post)

## Betrieb: was gemessen wird, wie oft, von wem

| Metrik | Frequenz | Wer | Wo sichtbar |
|---|---|---|---|
| Adoption-Rate (GB-07) | wöchentlich | fachverantwortliche Rolle | KPI-Dashboard oder CSV (keine Blackbox) |
| VETO-Rate (wie oft `verify` ablehnt) | wöchentlich | Betreiber | Audit-Trail-Auswertung |
| Kill-Switch-Bereitschaft (getestet?) | monatlich | Betreiber | Protokoll + Datum des letzten Tests |
| Rollback-Bereitschaft (getestet?) | monatlich | Betreiber | Protokoll + Datum des letzten Tests |
| Sampling-Audit-Abdeckung (Grad 05) | täglich | admin | Audit-Trail, nicht «irgendwo» |
| Exception-Queue-Backlog (Grad 05) | täglich | fachverantwortliche Rolle | Queue, nicht «irgendwo» |

**Die wichtigste Regel:** Es gibt kein «wir messen das im Hintergrund».
Jede Metrik hat einen Namen, eine Frequenz, eine zuständige Rolle und
einen Ort. Wenn eine der vier fehlt, ist die Metrik nicht gemessen.

## Betrieb: was passiert, wenn etwas schiefläuft

| Ereignis | Reaktion (sofort) | Wer | Danach |
|---|---|---|---|
| Modell liefert Antwort ohne Fundstelle | `verify` → VETO, Aktion nicht freigeben | System | VETO wird geloggt, Begründung ist Pflicht |
| Rolle versucht Aktion, die sie nicht darf | `FreigabePolicy` → VETO, Log-Eintrag | System | admin wird informiert (nicht «schon mal geloggt») |
| Kill-Switch-Test fehlschlägt | Zustand → Stopp, keine Freigabe mehr | Betreiber | Neuer Kill-Switch-Test, Protokoll, Erst dann wieder Live |
| Zielsystem-Limit überschritten | `ZielsystemAdapter` → blockiert, Log | System | fachverantwortliche Rolle prüft: ist das Limit falsch oder die Aktion? |
| Datenleck (Payload im Log, Prompt-Leck) | Zustand → Stopp, Audit-Trail sichern | admin | Incident-Log, Rechtsberatung (nur die klärt, ob Anzeige nötig) |

**Wichtig:** «Wir beobachten das im Monitoring» ist keine Reaktion.
Jede Zeile in dieser Tabelle hat einen konkreten Akteur und eine
konkrete Folge. Das ist der Unterschied zwischen «Betrieb» und «Wir hoffen».

## Rollback: was er ist und wie er getestet wird

**Ist**: der Zustand vorher. Ein Rollback in diesem Modell bedeutet:
- Alle Zustandsänderungen seit dem letzten «sauberen Punkt» werden
  zurückgesetzt (im Zielsystem, nicht nur im Log).
- Der «saubere Punkt» ist ein definierter Moment: z.B. der Zeitpunkt
  des letzten Kill-Switch-Tests, der letzte `zustand="live"`-Übergang,
  oder ein definierter Snapshot-Punkt.
- Der Rollback wird **getestet** (GB-12: `automatic_rollback = true`
  ab Grad 03). Test = der Rollback wird ausgeführt, der Zustand ist
  wieder da wie vorher, der Audit-Trail enthält beide Richtungen
  (Zustandsänderung + Rollback).

**Ist nicht**:
- `git revert` — das ist für Code, nicht für Zustandsänderungen in
  einem Buchhaltungssystem.
- «Wir fangen es manuell wieder ein» — das ist Rollback ohne Test.
- «Das Zielsystem hat ja ein Backup» — ein Backup ist ein
  Wiederherstellungs-Mechanismus, kein Rollback. Der Unterschied:
  Rollback kennt den «sauberen Punkt», Backup kennt nur die Datei.

## Ausserbetriebnahme: was am Ende stehen bleibt

Wenn der Use Case beendet wird (nicht «pausiert», beendet):

1. **Kill-Switch → Stopp** (dauerhaft, nicht «mal kurz» — das Protokoll
   dokumentiert, dass es dauerhaft ist)
2. **Zielsystem-Zugang widerrufen** (der Use-Case darf keine schreibenden
   Aktionen mehr erzeugen — die Rolle wird aus der `FreigabePolicy`
   entfernt, nicht nur «deaktiviert»)
3. **Datensicherung**: der Audit-Trail wird exportiert (CSV) und
   archiviert. (Append-only: er bleibt. Das ist der ganze Punkt.)
4. **KI-Register-Eintrag**: `zustand="ausserbetrieb"` mit Datum und
   Begründung (nicht «irgendwann beendet»)
5. **Löschprotokoll** (nur, wenn Daten gelöscht werden): was wurde gelöscht,
   wann, von wem. (Nur wenn — nicht immer. Die Frage ist: müssen wir
   die Daten behalten? Wenn ja: Archiv. Wenn nein: Löschprotokoll.
   Beides ist anders als «das ist so». )
6. **Incident-Log**: alle VETO-Ereignisse, Kill-Switch-Tests,
   Rollback-Tests — bleibt. (Das ist der Nachweis, dass der Use Case
   kontrolliert war, auch wenn er jetzt nicht mehr läuft.)

## Was «Inbetriebnahme» NICHT ist

- «Wir schalten es ein am Montag» → das ist ein Termin, kein Zustand.
  Der Zustand «Live» erfordert die vier Bedingungen oben (Abschluss,
  Register, Rollen, Log).
- «Das läuft im Hintergrund, wir rufen es mal auf» → das ist Shadow,
  nicht Live. Shadow hat andere Freigaben als Live.
- «Die Rollen-Policy ist noch offen, aber wir schalten es mal ein» →
  offene Rollen-Policy + Live = jeder kann alles freigeben. Das ist
  nicht Inbetriebnahme, das ist ein Befund.
- «Der Kill-Switch ist da, aber wir haben ihn noch nicht getestet» →
  ab Grad 03 ist der Kill-Switch ein Abnahmekriterium, kein «hätte
  man mal».
