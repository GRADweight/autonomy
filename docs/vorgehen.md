# Vorgehen: beschreiben, umsetzen, abnehmen, betreiben

## 1. Beschreiben

Der Anwendungsfall wird als JSON nach dem [Schema 2.0](schema.md) beschrieben,
bevor gebaut wird: Grad, Achsen, Risikomerkmale, Daten, Kontrollen. Kontrollen,
die es noch nicht gibt, erhalten `"status": "planned"` – der Validator zeigt
dann genau, was für den gewünschten Grad fehlt.

```bash
gw-autonomy validate mein-fall.json
```

Die Fehlermeldungen sind die Arbeitsliste. Warnungen sind bewusst zu
entscheiden und zu dokumentieren (z. B. die Rule-of-Two-Warnung bei Grad 2).

## 2. Umsetzen

Die Kontrollen werden technisch umgesetzt, nicht nur beschrieben. Die
[Bausteine](../README.md#bausteine) decken die häufigsten ab. Für jede Kontrolle
entsteht ein Nachweis (Testprotokoll, Konfiguration, Messbericht) und wird in
`evidence` erfasst.

## 3. Abnehmen

Abgenommen wird ein Grad, wenn

1. `gw-autonomy validate --check-evidence` mit Exit-Code 0 endet,
2. eine verantwortliche Person die Nachweise inhaltlich geprüft hat
   (`approved_by` am Nachweis),
3. die Entscheidung «weiter», «umbauen» oder «aufhören» festgehalten ist.

«Aufhören» ist ein gültiges Ergebnis: Ein Anwendungsfall, der seine
Kontrollen nicht erfüllt, läuft nicht «vorläufig» weiter.

## 4. Betreiben

| Zustand | Bedeutung |
|---|---|
| Schatten | System läuft mit, ohne zu wirken; Abweichungen werden gemessen |
| Live | Freigabe-Kette aktiv, Audit-Trail läuft, Kennzahlen werden erhoben |
| Zurückgestuft | Nach Schwellenriss eine Stufe tiefer (z. B. Mandat -> Freigabe je Aktion) |
| Gestoppt | Notaus aktiv, keine Wirkung mehr, Audit-Trail bleibt |

Regelmässig zu erheben: Übernahmequote (`ApprovalQueue.summary()`),
Ausnahmen (`ExceptionQueue.summary()`), Stichproben (`SamplingAudit.run()`),
Fehlerquote der Modellaufrufe (`Tracer.summary()`), Alter der Nachweise
(GB-20). Der Kopf-Hash des Audit-Trails wird ausserhalb der Datenbank
verankert (siehe [Audit-Trail](audit-trail.md)).

Jeder Wechsel von Modell, Prompt oder Werkzeug ist eine Änderung des Falls:
neu beschreiben, neu validieren, neu abnehmen (Kontrolle `change_management`).

Bei Ausserbetriebnahme bleiben Fall-Beschreibung, Nachweise und Audit-Export
erhalten; das KI-Register (Vorlage in [governance/](../governance/README.md))
erhält den Zustand «ausser Betrieb» mit Datum.
