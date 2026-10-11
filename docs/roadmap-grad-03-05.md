# Roadmap Grad 03–05 — von «valides Modell» zu «liefern»

Diese Seite zeichnet die Linie ein, an der dieses Repo ehrlich bleibt:
Was wir **liefern** (Code, Tests, Validator), wo wir ein **valides
Modell** zeigen (JSON-Befund, der die Regeln erfüllt), und was noch
**nicht** gebaut ist (Runtime-Bausteine für Agent, Multi-Agent und die
Kontrollen, die Grad ≥ 4 erzwingen).

Nichts hier ist Marketing. Jede Zeile verweist auf Datei, Regel oder
einen konkreten Befund, den du im Repo nachprüfst.

---

## 0 · Die drei Kategorien (kurze Definition)

| Kategorie | Was es ist | Wie du es im Repo siehst |
|---|---|---|
| **Geliefert** | Lauffähiger Code mit Tests, der ein Verhalten erzwingt | `packages/gw_core/*.py` + grüne Tests |
| **Valides Modell** | Ein Fall, dessen JSON die Regeln GB-01…16 erfüllt — also der *Soll*-Zustand definiert, aber die Umsetzung nicht ist | `examples/gw*.json` + `gradbuild.cli` → «0 mit Fehlern» |
| **Nicht gebaut** | Eine Kontrolle, die im JSON als `true` behauptet wird, aber keinen Code hat | `exception_queue=true`, `sampling_audit=true`, … (nur in `validate.py` abgefragt) |

Die ganze Roadmap ist die Frage: **Welche «nicht gebaut»-Kontrollen
müssten zu Code werden, damit Grad X geliefert statt nur modelliert ist.**

---

## 1 · Was ist heute im Code (Grad 01–02 = geliefert)

`gw_core` liefert sechs Bausteine. Sie sind es, die einen Assistenten
(Grad 1) und einen Copiloten (Grad 2) technisch möglich machen:

| Baustein | Was er erzwingt | Grad, den er trägt |
|---|---|---|
| `pruefe_antwort` (Zweitmodell) | Antwort muss aus Quillen zitiert werden; Halluzination → Befund | 01, 02 |
| `ApprovalQueue` | Jede Ausführung braucht einen Freigabe-Entscheid (menschlich) | 01, 02 |
| `FreigabePolicy` (AuthZ) | Wer darf welche Aktion freigeben; Rollenvorgabe, nicht Modell | 01, 02 |
| `AuditTrail` | Wer/was/wann, append-only, exportierbar | 01–05 (Fundament) |
| `Tracer` | Ereignisfolge, nachvollziehbar | 01–05 (Beobachtbarkeit) |
| `BexioZielsystemAdapter` | Zielsystem-Call **vor** dem Auslösen; `pre_check` = Betrag-Limit + Währung + Pflichtfelder | 02 (Money-Gate), Grundstein für 04 |

> **Schlusssatz Grad 01–02:** Hier ist der Mensch **in** der Kette —
> jede wirkungsvolle Aktion läuft durch FreigabeQueue oder Gate. Das ist
> im Code und mit Tests gedeckt (`tests_gwcore/`, 49 grün).

---

## 2 · Was das Modell verlangt (Grad 03–05 = valid, aber «liefern» fehlt)

Der Validator (`packages/gradbuild/gradbuild/validate.py`) kennt für
jeden Grad die Pflicht-Controls. Die Beispiele `gw3`, `gw4`, `gw5`
setzen alle zu `true`. **Aber** — dieser Abschnitt ist der ehrliche
Kern der Roadmap:

### 2.1 Die drei offenen WARN-Befunde (nach `gradbuild.cli`)

Jeder der drei Fälle gilt (0 Fehler), aber jeder wirft genau eine
**offene WARNUNG** — und jede zeigt eine echte Lücke, keine Kosmetik:

| Fall | Befund | Was es heisst |
|---|---|---|
| **gw3** (Grad 3, predictive maintenance) | `WARN GB-06` — safety_critical=true | Deckel 2: Schutzfunktion ist **gedeckelt** auf Grad 3. Das Modell *darf* sie nicht darüber heben. Korrektes Verhalten, aber: der Fall bleibt **nie** ein Grad-4-Kandidat. |
| **gw4** (Grad 4, C-Teile nachbestellen) | `WARN GB-14` — `pass^k ohne steps` | Der Grad-4-Fall verlangt einen **messbaren Test-Satz** (pass^k), hat aber keine `steps`. Die Messung ist deklariert, nicht ausbuchstabiert. |
| **gw5** (Grad 5, Standardretouren) | `WARN GB-05` — `customer_text_in_decisions=true` | Fremde Inhalte fliessen in die Entscheidung ein. Das Modell löst das (nach Regel GB-05/Rule-of-Two) damit, dass ein **separates Tool-freies Modell** vorher klassifiziert — **dieser Klassifikator ist nicht im Repo.** |

### 2.2 Die Kontrollen: was Code hat, was noch nicht

Die Beispiele setzen diese Flags auf `true`. Zwei davon hat die Lücke
zwischen «Modelle» und «liefern» **geschlossen** — die restlichen
offen:

| Kontrolle | Im JSON | Im Code | Status |
|---|---|---|---|
| `exception_queue` | ✅ `true` (gw3/4/5) | ✅ **`gw_core.exception_queue.ExceptionQueue`** + 13 Tests | **Geliefert** — deterministische Policy, Append-only, KPI-Einseiter |
| `sampling_audit` | ✅ `true` | ✅ **`gw_core.sampling_audit.SamplingAudit`** + 8 Tests | **Geliefert** — reproduzierbare systematische Stichprobentechnik + Kriterien + Evidenz |
| `automatic_rollback` | ✅ `true` | ✅ **`gw_core.rollback.RollbackManager`** + 14 Tests | **Geliefert** — Snapshot-Registry, deterministischer Rollback-Befehl, Append-only Ausführung, KPI |
| `shadow_run_first` | ✅ `true` | ⚠️ **indirekt** — die `shadow`-Messmethode + Shadow-Betrieb ist Teil des Modells; der **parallele Lauf ohne Wirkung** ist keine einzelne Baustein, sondern eine **Betriebs-Konfiguration** | **Offen als Code-Baustein**, aber als **Betriebs-Konfiguration** vorhanden |
| `agent_identity_min_privilege` | ✅ `true` | ⚠️ `FreigabePolicy` deckt Rollen ab, **keine** Agent-ID/Servicekonto | **Offen** — eine pro-Agent-Identität mit minimalen Rechten (Entra Agent ID / Servicekonto) |
| `decides_new_on_model_prompt_tool_change` | ✅ `true` | ❌ nur abgefragt | **Offen** — ein Stufen-Entscheid-Trigger, der bei jedem Modell-/Prompt-/Toolwechsel zwingend neu läuft |

> **Der Unterschied in einem Satz:** Grad 01–02 = die Bausteine **sind**
> die Kontrolle. Grad 03–05 = die Bausteine **müssen dazukommen** —
> `exception_queue`, `sampling_audit` und `automatic_rollback`
> **haben** diesen Stand; die restlichen drei sind noch «Modelle»,
> nicht «geliefert».

### 2.3 Was für jeden einzelnen Grad konkret fehlt

**Grad 03 (Workflow, gw3):**
- ✅ Modell: `fixed_chain` + `per_gate`, Schutzfunktion gedeckelt — korrekt validiert.
- ⬜ Geliefert werden muss noch: die **Gate-Kette** als ausführbare Pipeline
  (heute ist ein Gate nur «eine Freigabe-Queue-Aufruf pro Schritt» — die
  **Sequenz** mehrerer Gates mit Zuständen ist nicht gebündelt).
- ⬜ `kill_switch_tested`: ein **geprobt**er Notaus mit Test — heute nur ein
  Flag im JSON.

**Grad 04 (Agent, gw4):**
- ✅ Modell: `model` + `mandate`, `limits_in_system=true` (Limit im Zielsystem,
  nicht im Prompt) — korrekt validiert.
- ⬜ **`steps` definieren** (GB-14-Warnung): der konkrete Schrittplan mit
  `planned_by`/`human_role` je Schritt, damit der Validator die Achsen je
  Schritt prüfen kann.
- ✅ **ExceptionQueue + SamplingAudit** als Code (siehe 2.2) — der
  deterministische Entlastungs- und Audit-Pfad für Grad 4 ist **geliefert**.
- ✅ **Automatic-Rollback** (GB-12): `RollbackManager` — Snapshot-Registry
  (Vorher/Nachher), deterministischer Reversal-Befehl aus Template+
  Snapshot, Append-only Ausführung mit `on_behalf_of`. Ist **geliefert**;
  der Aufruf an das Zielsystem verbleibt beim Deployment.
- ⬜ **Agent-Identität** (Servicekonto), die nur die ERP-Schnittstelle
  erreicht — nicht die ganze Datenbank.
- ⬜ **pass^k-Testset** (30–50 echte CH-Belege), gegen das der Agent
  wiederholbar gemessen wird.

**Grad 05 (Multi-Agent, gw5):**
- ✅ Modell: `model` + `exception_only`, Mandat mit Limit, Shadow-Messung —
  korrekt validiert.
- ✅ **ExceptionQueue** (GB-11): der Entlastungs-Pfad, der bei Schwellenriss
  Fälle deterministisch ausgliedert, ist **geliefert** (siehe 2.2). Das ist
  der zentrale Grad-5-Baustein neben dem Text-Klassifikator.
- ⬜ **Text-Klassifikator** (GB-05-Warnung): ein separates, **tool-freies**
  Modell, das Kundentexte **vor** der Entscheidung klassifiziert, damit der
  Entscheid-Agent nur strukturierte Daten sieht. **Dies ist der
  wichtigste fehlende Baustein für Grad 5** (Rule of Two).
- ⬜ **Orchestrator**: `gw_core` kennt einen `BexioZielsystemAdapter` als
  einzelnes Ziel — eine **Multi-Ziel-Planung** (mehrere Agents,
  gemeinsame Mandate, koordinierte Freigabe) ist nicht gebaut.
- ⬜ **Deterministische Policy-Schicht** für Geld und Daten (Grad-5-Pflicht
  nach GB-08/GB-09) als separate, prüfbare Komponente — `ExceptionPolicy`
  ist der Grundstein, noch nicht die vollständige Multi-System-Komponente.

---

## 3 · Die ehrliche Abgrenzung (Was wir **nicht** tun — und warum)

Damit «valides Modell» nicht zu «wir liefern alles» verkommt:

1. **Wir liefern Grad 01–02 als Code.** Das ist der Beitrag, der
   verifizierbar ist: `gw_core` + Tests + 9 Bausteine.
2. **Wir liefern drei der fünf Grad-4/05-Kontrollen als Code.** Konkret
   `exception_queue`, `sampling_audit` und `automatic_rollback` (die drei
   wichtigsten Grad-4 Pflicht-Controls nach GB-11/12). Das schliesst die
   Lücke zwischen «im JSON behauptet» und «im System erzwingt» für diese
   drei Punkte.
3. **Wir liefern die restlichen Grad-4/5-Kontrollen als validiertes Modell.**
   Das JSON mit allen Pflicht-Controls und die Doku, die sagt, was jeder
   braucht. Das ist der Beitrag, der ein Projekt **rahmen** kann —
   aber noch nicht **ausführt**.
4. **Die verbleibende Gap (2.2/2.3) ist der eigentliche Auftrag** für
   Custom-Engineering pro Kunde. Sie ist **bewusst nicht** in diesem
   Open-Source-Repo, weil sie Kundendaten, Zielsysteme und Compliance-
   Kontext braucht, die wir hier nicht haben.

> **Was «grad 03–05 aufzeigen» hier heisst:** das Modell zeigen, die
> Grenzen zeigen, drei der fünf fehlenden Bausteine **schon geliefert**
> (2.2), die restlichen **benennen** (2.2/2.3) — und dem Betreiber ein
> **validiertes JSON in die Hand** geben, gegen das er sein eigenes
> Projekt validieren kann. Nicht: den Orchestrator oder den
> Text-Klassifikator für ihn bauen.

---

## 4 · Wie du es validierst (3 Befehle)

```bash
# 1. Alle Beispiele laufen (Grad 01–05) — alle Exit 0:
for f in examples/gw*.json; do python -m gradbuild.cli "$f" >/dev/null && echo "OK  $f"; done

# 2. Die 3 offenen WARN-Lücken (GB-05/06/14) sichtbar machen:
python -m gradbuild.cli examples/gw3-*.json examples/gw4-*.json examples/gw5-*.json

# 3. Beweis, dass exception_queue + sampling_audit + automatic_rollback
#    IM CODE sind (und nicht nur im JSON), und dass Orchestrator +
#    Text-Klassifikator NICHT sind:
python -c "
from gw_core import ExceptionQueue, SamplingAudit, RollbackManager
print('OK  ExceptionQueue + SamplingAudit + RollbackManager sind importierbar')
"
grep -rn "class TextKlassif\|class Orchestrat" packages/gw_core/gw_core/*.py  # → 0 Zeilen: fehlt
```

Wenn Schritt 3 **geliefert** meldet, ist der Befund korrekt: **Drei der
fünf fehlenden Kontrollen sind im Code, die restlichen sind im Modell.**
Das ist der ehrliche Stand, den diese Roadmap ausweist.

---

*Stand: 2026-10-11 · Quelle: `packages/gradbuild/gradbuild/validate.py`
(GB-01…16), `packages/gw_core/`, `examples/`, `docs/`. Kein Rechtsrat.*
