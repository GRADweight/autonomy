# KI-Richtlinie (Vorlage) — minimal, anpassbar

> **Stand:** 2026-10 · **Verantwortlich:** <name/Rolle> · **Freigabe:** <GK, Datum>
>
> Diese Vorlage ist bewusst klein. Eine Richtlinie mit 40 Seiten wird von
> niemandem gelesen und von niemandem verstanden. Diese hier ist so
> geschrieben, dass ein Fachverantwortlicher sie in 20 Minuten lesen und
> anwenden kann.

## 1 · Geltungsbund

Diese Richtlinie gilt für alle KI-gestützten Anwendungen, die
a) auf Unternehmensdaten zugreifen, b) Aussenwirkung haben, oder
c) in Entscheidungen mitwirken. Das gilt unabhängig davon, ob die
Anwendung intern, extern (SaaS) oder von einem Dienstleister betrieben wird.

## 2 · Autonomiegrade (verbindliche Definition)

Jede Anwendung wird genau einem Grad zugeordnet (Definition:
`docs/plan.md` in diesem Repo):

| Grad | Bezeichnung | Freigabe-Muster |
|---|---|---|
| 01 | Assistent | Mensch kontrolliert jede Ausgabe; keine schreibende Aussenwirkung |
| 02 | Copilot | Jeder schreibende Schritt wird einzeln freigegeben (Approval) |
| 03 | Workflow | Feste Kette; Freigabe je Gate; systemseitige Limits |
| 04 | Agent | Modell plant; Mandat mit systemseitigen Limits; Schattenbetrieb vor Go-live |
| 05 | Multi-Agent | Modell orchestriert; nur Ausnahmen an den Menschen; Sampling-Audit |

**Regel:** Eine Anwendung läuft nur auf dem Grad, der im Autonomie-Fall
validiert wurde (gradBuild-Validator, `examples/` als Referenz). Höhere
Grade erfordern ein neues, validiertes Fall-JSON und eine neue Freigabe.

## 3 · Harte Grenzen (gelten ohne Ausnahme)

1. **Rule of Two:** Eine Anwendung mit Aussenwirkung verarbeitet nicht
   gleichzeitig fremde, unvertrauenswürdige Eingaben und sensible Daten —
   bei Grad ≥ 04 muss einer der drei Faktoren strukturell weg sein.
2. **Schutzfunktionen:** KI ist max. Grad 03 und nie in der Schutzkette
   (Qualität, Maintenance, Sicherheit).
3. **Geld:** Grad ≥ 04 mit Geldwirkung nur mit systemseitigen Limits
   im Zielsystem (Buchhaltung/ERP) — nie im Prompt, nie als «bitte nicht
   über 5'000 CHF».

## 4 · Rollen und Freigabe

| Rolle | Kann |
|---|---|
| Fachverantwortlicher (je Anwendung) | Freigabe, Anpassen, Zurückstellen der Aktionen seiner Anwendung |
| KI-Verantwortlicher (organisatorisch) | Grad-Freigabe, Register, Richtlinienpflege, Kill-Switch-Freigabe |
| Admin | VETO über alle Freigaben (Begründungspflicht) |

Ein Modell hat keine Rolle. Es kann Aktionen vorschlagen, nicht entscheiden.

## 5 · Audit und Nachweis

- Jede freigegebene und jede zurückgestellte Aktion landet im
  append-only-Audit-Trail (wer/was/wann, CSV-Export möglich).
- Der Trail wird bei Ausserbetriebnahme archiviert, nicht gelöscht.
- VETO und Kill-Switch-Ereignisse sind Teil des Trails und werden
  mindestens einmal pro Quartal geprüft (KI-Verantwortlicher).

## 6 · Ausserbetriebnahme

Eine Anwendung kann nur ausserbetriebgenommen werden, wenn:
1. Kill-Switch aktiv für ≥ 72h (keine offenen Aktionen),
2. Zugangsrechte für den Use-Case entzogen,
3. Register-Eintrag auf `ausserbetrieb` mit Datum und Begründung,
4. Audit-Trail exportiert und archiviert.

## 7 · Was diese Richtlinie nicht ist

- Kein Rechtsrat. Klassifizierung (AI Act), Haftung und Vertragsklauseln
  klärt die Rechtsberatung. Diese Richtlinie dokumentiert den
  Freigabe-Prozess und die technischen Schranken — sie ersetzt keine
  juristische Einordnung.
- Kein Verbot von KI. Sie setzt Schranken je Grad, statt pauschal zu
  verbieten. (Pauschale Verbote werden umgangen; Grade werden überwacht.)
