# KI-Richtlinie (Vorlage)

> **Stand:** <Datum> · **Verantwortlich:** <Rolle> · **Beschlossen durch:** <Gremium, Datum>
>
> Kurz gehalten, damit sie gelesen und angewendet wird.

## 1. Geltungsbereich

Diese Richtlinie gilt für alle KI-gestützten Anwendungen, die
a) auf Unternehmensdaten zugreifen, b) nach aussen wirken oder
c) an Entscheiden mitwirken – unabhängig davon, ob sie selbst betrieben,
als Cloud-Dienst bezogen oder von Dritten betrieben werden.

## 2. Autonomiegrade

Jede Anwendung wird einem Grad zugeordnet ([Definition](../../docs/autonomiegrade.md)):

| Grad | Bezeichnung | Freigabe |
|---|---|---|
| 0 | Keine KI-Autonomie | Menschen handeln, KI liefert höchstens Recherche |
| 1 | Assistent | Menschen handeln selbst; keine Aussenwirkung der KI |
| 2 | Copilot | jede schreibende Aktion wird einzeln freigegeben |
| 3 | Workflow | feste Kette, Freigabe an definierten Toren |
| 4 | Agent mit Mandat | Modell handelt innerhalb technisch erzwungener Grenzen |
| 5 | Autonom mit Ausnahmesteuerung | Menschen bearbeiten Ausnahmen und Stichproben |

Eine Anwendung läuft nur auf dem Grad, für den ihre Fall-Beschreibung mit
`gw-autonomy validate --check-evidence` geprüft und abgenommen ist.

## 3. Harte Grenzen

1. **Rule of Two:** Ohne Mensch in der Kette (ab Grad 4) verarbeitet eine
   Anwendung nicht gleichzeitig fremde Eingaben und sensible Daten und wirkt
   nach aussen.
2. **Schutzfunktionen:** KI berät, liegt aber nie in der Sicherheitskette;
   höchstens Grad 3.
3. **Geld:** Ohne Freigabe je Aktion nur mit bezifferter Betragsgrenze, die im
   Zielsystem durchgesetzt wird – nie als Bitte im Prompt.

## 4. Rollen und Freigabe

Siehe [Rollenmodell](rollen.md). Ein Modell hat keine Rolle: Es schlägt vor,
es entscheidet nicht. Wer vorschlägt, gibt nicht selbst frei.

## 5. Nachweise und Protokoll

- Jede als umgesetzt deklarierte Kontrolle verweist auf einen Nachweis
  (Testprotokoll, Konfiguration, Messbericht); Notaus- und Rollback-Tests
  werden mindestens jährlich wiederholt.
- Freigaben, Rückweisungen und Buchungen werden im Audit-Trail mit
  Hash-Kette protokolliert; der Kopf-Hash wird regelmässig ausserhalb der
  Datenbank abgelegt.
- Jeder Wechsel von Modell, Prompt oder Werkzeug löst eine neue Prüfung aus.

## 6. Ausserbetriebnahme

1. Notaus dauerhaft aktiv, keine offenen Aktionen.
2. Zugänge und Rollen des Anwendungsfalls entzogen.
3. Registereintrag auf «ausser Betrieb» mit Datum und Begründung.
4. Audit-Trail exportiert (`gw-autonomy audit export`) und archiviert.

## 7. Was diese Richtlinie nicht ist

Kein Rechtsrat und keine Einstufung nach EU AI Act oder Datenschutzrecht; sie
regelt Freigaben und technische Grenzen und ist Grundlage für diese
Beurteilung.
