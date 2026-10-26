# Phase 3 · Wie — wie der Code konkret greift

Diese Seite zeigt, was «Freigabe-Queue» in der Praxis bedeutet: eine
konkrete Abfolge von Aufrufen, mit den Daten, die am Ende im Log stehen.
Keiner der Beispiele ist «hypothetisch» — sie sind die selben Bausteine,
die in `tests_gwcore/` laufen.

## Der Pfad: Antwort → Freigabe → Prüfung → Zustand → Log

```
  Modell-Antwort (eher: Fundstelle + Entwurf)
        │
        ▼
  1. verify.pruefe_antwort(entwurf, fundstellen)
        │   → Befund(ok=True, zitate=[...])   │ ok=False → VETO, Aktion endet
        ▼
  2. approval.ApprovalQueue.aufgeben(mandant, prototyp, beschreibung, payload)
        │   → Aktion (id, status="offen")
        ▼
  3. Person mit Rolle R entscheidet
        │   → queue.entscheiden(aktions_id, rolle=R, entscheid="freigabe")
        │       intern: authz.FreigabePolicy.pruefe(rolle, aktionstyp)
        │       falls Rolle nicht erlaubt → VETO, wird im Log
        ▼
  4. audit.AuditTrail.log(mandant, aktion, actor, entscheid, begruendung)
        │   → append-only, wer/was/wann
        ▼
  5. (nur wenn grad >= 03) Zielsystem-Adapter
        │   → bexio.ZielsystemAdapter.ausfuehren(payload)
        │       intern: limit_betrag(payload), limit_tagesvolumen(payload)
        │       falls Limit überschritten → blockiert, wird im Log
        ▼
  6. tracing.Tracer.trace(antwort_id, dauer_ms, status, mandant)
             → wer hat das wann gesehen, wie lange dauerte es
```

Das ist die ganze Freigabe-Kette. Was in der Doku «Governance» heisst,
ist in der Praxis: **ein Datenobjekt (die Aktion) durch sechs Funktionen
geprüft**, und jede Funktion kann es stoppen. Es gibt keinen «umgegangenen
Weg» — der Zustand wird nur durch `entscheiden(..., "freigabe")`
erreichbar, und nur durch `ausfuehren(...)` im Zielsystem verändert.

## Der Audit-Trail: was er enthält und was nicht

**Enthält** (append-only, `audit.py`):
- `mandant` — wer (Mandant/Kunde)
- `prototyp` — welcher Use Case
- `actor` — welche Rolle / welche Person (Rolle ist Pflicht, Person optional)
- `aktion` — Freigabe / Anpassen / Zurückstellen / VETO / Limit-Blockade
- `begründung` — freies Feld, Pflicht bei VETO und Anpassen
- `ts` — Zeitstempel (UTC)
- `rid` — fortlaufende Nummer (append-only, nie gelöscht)

**Enthält nicht** (bewusst):
- Das vollständige Modell-Prompt. Das gehört in die LLM-Logs, nicht in
  das Governance-Log. (Sonst wird der Audit-Trail zu einem Prompt-Leck.)
- PII aus dem `payload` — die `payload`-Felder, die in den Log kommen,
  sind die, die **für die Freigabe relevant** sind (Betrag, Ziel, ID),
  nicht «der komplette Datenbankeintrag».
- «Warum das Modell das so entschieden hat» — das ist ein
  Modell-Problem, kein Governance-Problem. Der Log dokumentiert, dass
  **eine freigegebene Aktion ausgeführt wurde**, nicht, warum das
  Modell sie vorschlug.

## Der Kill-Switch: was er ist und was er nicht ist

**Ist**: eine definierte Funktion `stopp(mandant, prototyp)`, die
1. alle offenen Aktionen in der `ApprovalQueue` auf `status="storniert"`
   setzt,
2. den Zielsystem-Adapter auf `dry_run=True` umschaltet (keine echten
   Zustandsänderungen mehr),
3. einen Eintrag in den Audit-Trail schreibt
   (`aktion="kill_switch", actor=<wer>`, `begründung=<warum>`).

**Ist nicht**:
- ein «Modell schweigt» — der Kill-Switch wirkt auf die **Freigabe-Kette**,
  nicht auf das Modell. Das Modell kann weiterhin antworten; es darf
  nur keine Freigabe mehr erzeugen.
- ein «alles löschen» — der Audit-Trail bleibt. Append-only heisst:
  auch Kill-Switch-Ereignisse werden geloggt, aber nichts wird gelöscht.
- ein «wenn was schiefläuft, schalten wir es mal aus» — der Kill-Switch
  muss **getestet** sein (GB-12: `kill_switch_tested = true` ab Grad 03),
  sonst gilt er nicht.

## Tracing: was gemessen wird, was nicht

**Gemessen** (`tracing.Tracer`):
- `antwort_id` — welche Antwort war das (Verknüpfung zu `verify`)
- `dauer_ms` — wie lange dauerte der LLM-Call (nicht die Antwort)
- `status` — ok / refusal / error (wichtig: ein «refusal» ist kein
  Fehler, aber es muss sichtbar sein)
- `mandant` — wer, ohne PII

**Nicht gemessen** (bewusst):
- Der Modell-Inhalt (Prompt, Antwort-Fulltext) — das gehört in die
  LLM-Logs, nicht in das Governance-Trace.
- Latenz-Ziele («unter 200 ms») — das ist ein Performance-Kriterium,
  kein Governance-Kriterium.

## Die Rollen-Policy: was «Least Privilege» hier bedeutet

```python
FreigabePolicy(
    policies={
        "fachverantwortung": ["freigabe", "anpassen", "zurueckstellen"],
        "admin": ["freigabe", "anpassen", "zurueckstellen", "veto"],
        # "modeller":  []   # ein Modell hat keine Rolle — es kann nur vorschlagen,
        # nicht entscheiden. Das ist der Punkt.
    }
)
```

- Die **Rolle** ist die Einheit, nicht die Person. Eine Person hat genau
  eine Rolle in diesem Kontext. (Eine Person mit zwei Rollen in zwei
  unterschiedlichen Use-Cases ist erlaubt — aber die Policies sind
  pro-Use-Case, nicht global.)
- Ein **Modell hat keine Rolle**. Es kann nur eine `Aktion` in die
  Queue legen. Alles andere (Freigabe, VETO) ist `entscheiden(...)`,
  und das erfordert eine Rolle, die in der Policy steht.
- Der **admin** darf `veto` — und das wird in den Audit-Trail geschrieben
  (`actor="admin"`, `aktion="veto"`). Admin ist kein Gott: auch er muss
  eine Begründung liefern (Pflicht bei VETO).

## Was dieser «wie»-Pfad NICHT ist

- Er ist **kein** «das Modell macht es, wir loggen es». Die Reihenfolge
  ist umgekehrt: die Freigabe kommt vor der Zustand-Änderung.
- Er ist **kein** «Prompt-Engineering». Die Schranken sind im Code
  (`approval.py`, `authz.py`, `bexio.py`), nicht in den
  System-Prompts. «Bitte halte dich an die Regeln» ist keine Regelung.
- Er ist **kein** «wir bauen es jetzt mal so». Die Bausteine sind
  getestet (`tests_gwcore/`) und die Regeln sind validiert
  (`gradbuild.cli`).
