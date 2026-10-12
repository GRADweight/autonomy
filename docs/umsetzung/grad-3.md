# Level 3 — Workflow (Feste Kette, Gate-Freigabe)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/gradautonomy` · **Level 3**
>
> **Achsen** (`schema.py::ALLOWED_AXES[3]`):
> - `(fixed_chain, per_gate)` — **feste Kette**, Freigabe **je Gate**
> - `(model, per_gate)` — Modell im Gate-Modus (Übergang, GB-08/GB-12/GB-13)
> - `(fixed_chain, mandate)` — «Dunkel-Variante» (Kette ohne Gates, erweiterte Leitplanken)
> - `(fixed_chain, exception_only)` — «Dunkel-Variante» mit Exception-Queue
>
> **Referenz-Case:** `examples/gw3-predictive-maintenance.json` (valid,
> `exit 0`, Deckel 3 — `max_level=3`).
>
> Kurz: Eine **feste, nachvollziehbare Kette** von Schritten läuft durch;
> der Mensch gibt **je Gate** frei. **Erste Stufe, an der der Kill-Switch
> und die Automatik-Rollback harte Pflichten sind (GB-12, error).**

---

## 1 · Was Level 3 ist (und was nicht)

**Ja:** Predictive-Maintenance (OPC UA → Historian → Anomalie → Ticket +
Fenstervorschlag), Kreditoren-Workflow (Beleg → Prüfung → Auszahlung),
Produktions-Steuerung (feste Kette) — **alles, was eine
nachvollziehbare, feste Schrittfolge** hat und an klar definierten Gates
freigegeben wird.

**Nein:** keine autonome Selbstplanung (das wäre Level 4+), keine
«dunklen» Aktionen ohne Gates und ohne Erweiterungs-Pflichten.

Der Unterschied zu Level 2: **die Kette ist fest** (deterministische
Schrittfolge), nicht modellspezifisch. Die Freigabe ist **je Gate**,
nicht **je Aktion**.

### «Dunkel-Variante» (GB-08/GB-12/GB-13, README §2)

Eine `fixed_chain` mit `mandate` oder `exception_only` ist die
**«Dunkle-Variante»**: die Kette ohne Gates, **aber** mit den
erweiterten Leitplanken der nächsten Stufe (GB-12/GB-13: Kill-Switch,
Shadow-Run, Sampling-Audit, ...). `validate.py` prüft das als `warn` —
wer die Leiste öffnet, muss die Leitplanken der nächsten Stufe tragen.

---

## 2 · GB-Pflichten auf Level 3 — die **ersten harten Kontrollen**

| Regel | Auswirkung bei Level 3 |
|---|---|
| **GB-01** / **GB-02** | **error** — Schema + Achsen. Bei `fixed_chain`: max. `per_gate`, `mandate`, `exception_only`. Bei `model`: nur `per_gate`. |
| **GB-12** Kill-Switch + Rollback + Neu-Entscheid | **error** — `kill_switch_tested=false` oder `automatic_rollback=false` → «Bei einem Schwellenriss muss die Rückstufung technisch automatisch greifen». **Diese Level-3-Pflicht ist die erste im System.** `decides_new_on_model_prompt_tool_change=false` → `warn`. |
| **GB-14** Messung | **error** — ohne `measurement.method` (`pass^k` oder `shadow`) → «Grad ≥ 3 ohne measurement». |
| **GB-06** Schutzfunktionen | **error**, wenn `safety_critical=true` und Level > 3 (Level 3 ist der Deckel, `warn` bei Level ≤ 3). |
| **GB-04** Deckel | `error` bei `level > ceiling.max_level` (Level 3 ist der Deckel für Schutzfunktionen, Maschinenverordnung). |
| **GB-03** Rule of Two | `warn`, wenn alle 3 zugleich |
| **GB-05** Kundentexte | `warn`, wenn `customer_text_in_decisions=true` |
| **GB-07** Übernahmequote | empfohlen (nicht hard) |
| **GB-15** Datenklasse | **error**, wenn `sensitive_data=true` und `data_class` fehlt |

**Keine** harten GB-11/13 auf Level 3 (die sind erst ab Level 4).

### Warum GB-12 die zentrale Level-3-Regel ist

**Kill-Switch** + **Automatik-Rollback** (GB-12) sind die technischen
Basis für alles, was ab Level 3 autonom wirkt. «Bei einem Schwellenriss
muss die Rückstufung technisch automatisch greifen, **nicht erst nach
einer Sitzung**» (README). Das ist der Unterschied zwischen «der Prozess
kann abgestellt werden» und «der Prozess stellt sich **selbst** ab,
wenn die Grenze verletzt ist».

`decides_new_on_model_prompt_tool_change=true` (GB-12, `warn` bei `false`)
bedeutet: **jeder** Modell-/Prompt-/Toolwechsel ist ein **Neu-Stufen-
Entscheid** — keine stille Upgrade.

---

## 3 · Referenz-Case `gw3-predictive-maintenance.json`

```
level: 3
who_plans: fixed_chain    human_role: per_gate
foreign_input: false      sensitive_data: true
external_action: true     money_effect: false
customer_facing: false    customer_text_in_decisions: false
safety_critical: true     data_class: intern    data_residency: on_prem
ceiling: { max_level: 3,
           reason: "Schutzfunktionen bleiben ausserhalb der KI; Maschinenverordnung + ISO/IEC TR 5469",
           regulation: "EU Machinery Regulation 2023/1230; ISO/IEC TR 5469:2024" }
measurement: { method: shadow }
governance: … kill_switch_tested=TRUE, automatic_rollback=TRUE,
  decides_new_on_model_prompt_tool_change=TRUE,
  shadow_run_first=TRUE, proposal_mode_first=FALSE, …
```

**Lesart:** `safety_critical=true` → **Deckel 2** aktiv (GB-06, `max_level=3`),
die Schutzfunktionen bleiben **ausserhalb** der KI (Maschinenverordnung
2023/1230, ISO/IEC TR 5469). `external_action=true` + `money_effect=false`
→ der Prozess wirkt nach aussen (Ticket + Fenstervorschlag), aber
**kein Geld**. `measurement.method=shadow` → GB-14 erfüllt. `kill_switch_
tested=true` + `automatic_rollback=true` → GB-12 erfüllt. `on_prem`-
Residency → DSG-konsistent bei `data_class=intern` + `safety_critical`.

---

## 4 · Technische Umsetzung im Unternehmen

### 4.1 Was stehen muss (harte Pflichten)

- **Kill-Switch (GB-12)** — ein **dokumentierter, getester** Ablauf, der
  ein laufendes Workflow-System **innerhalb von Minuten** abschaltet.
  Nicht «wir können das theoretisch», sondern **ein Befehl**, den ein
  Verantwortlicher ausführt (CLI, Web-Button, API-Call). `validate.py`
  prüft `kill_switch_tested=true` — die **praktische Prüfung** ist ein
  dokumentierter Test-Fall im Betrieb.
- **Automatik-Rollback (GB-12)** — `gw_core.rollback.RollbackManager`:
  **Snapshot-Registry** (vorher/nachher), **deterministischer
  Reversal-Befehl** aus Template+Snapshot, **Append-only** Ausführung,
  **KPI-Zähler**. Bei einem Schwellenriss (z. B. `anomaly_score > threshold`)
  wird der Zustand **automatisch** zurückgerollt.
- **Neu-Stufen-Entscheid (GB-12)** — ein dokumentierter **Change-Log-Fluss**:
  Wer hat was wann umgestellt (Modell, Prompt, Tool), und welche Konsequenz
  hat das auf den Stufen-Entscheid? `validate.py` prüft `decides_new_on_
  model_prompt_tool_change=true`.
- **Messung (GB-14)** — `measurement.method` ist ein **String** (`pass^k`
  oder `shadow`), aber der **echte Check** ist: ein Testset (bei `pass^k`)
  oder ein Shadow-Run (bei `shadow`) im Betrieb. `gw_core.verify.pruefe_
  antwort` + ein Golden-Set (z. B. 30–50 echte Fälle) = die Basis.
- **Deckel (GB-04/GB-06)** — `ceiling.max_level=3` bei
  `safety_critical=true` (Maschinenverordnung 2023/1230 + ISO/IEC TR 5469).
  Wer «Level 4+ bei Schutzfunktion» will, ist im **Konflikt** mit der
  Maschinenverordnung — der **einzige legale Ausweg** ist, die Schutz-
  funktion **strukturell ausserhalb** der KI zu halten
  (GB-06, `error` bei Level > 3).
- **Gate-Fluss (`per_gate`)** — jede Gate-Entscheidung wird
  **protokolliert** (wer, wann, Entscheidung, Kontext). `gw_core.
  approval.ApprovalQueue` + `gw_core.audit.AuditTrail`.

### 4.2 Bausteine (`gw_core`) — die ersten «echten»

| Baustein | Rolle auf Level 3 |
|---|---|
| `rollback.RollbackManager` | **empfohlen** (Level 3 ist die erste Stufe, an der **Pflicht** wird) — Snapshot, Reversal-Befehl, Append-only, KPI |
| `approval.ApprovalQueue` | **empfohlen** — Gate-Entscheidungen, Freigabe/Anpassen/Zurückstellen |
| `authz.FreigabePolicy` | **empfohlen** — welche Rollen dürfen welche Gates freigeben |
| `verify.pruefe_antwort` | **empfohlen** — VETO gegen Halluzinationen, Quellenprüfung (besonders bei `safety_critical`) |
| `audit.AuditTrail` | **empfohlen** — wer, wann, welche Gate-Entscheidung |
| `tracing.Tracer` | **empfohlen** — LLM-Request-Trace → Messung (GB-14) |
| `exception_queue` | **empfohlen** (Dunkel-Variante, GB-12/13) — Ausnahmen aus der Kette |
| `sampling_audit` | **empfohlen** (Dunkel-Variante, GB-12/13) — systematische Stichprobe |
| `bexio.BexioZielsystemAdapter` | **optional** — wenn die Kette ein Zielsystem (ERP/EDI) schreibend braucht |

### 4.3 Hardware / Infrastruktur

| Schicht | Option |
|---|---|
| Inferenz | 14B–32B (oder MoE), lokal oder CH-Cloud. Bei `safety_critical`/`intern` → **On-Prem bevorzugt** (DSG, Maschinenverordnung). |
| Kette/Orchestrierung | `fixed_chain` = deterministische Schrittfolge (z. B. ein Python-Skript, ein n8n-Flow, ein Airflow-DAG). **Kein** «freies Modell» im Datenpfad. |
| Gate-Queue (Approval) | `gw_core.ApprovalQueue` (SQLite) — lokal, kein Standort-Risiko. |
| Zielsystem (falls `external_action=true`) | ERP/EDI/CMMS — Shadow-Modus + Prod-Modus (bei `safety_critical`: Shadow-Pflicht). |
| Messung | `pass^k` (Golden-Set) oder `shadow` (Shadow-Run) — lokal. |

---

## 5 · Absicherung & Grenzen

- **GB-06** (Schutzfunktionen, `error` bei Level > 3) ist die **härteste
  Level-3-Grenze**: bei `safety_critical=true` ist Level 3 der **Deckel**.
  Wer «Level 4 bei Schutzfunktion» will, ist im **Konflikt** mit der
  Maschinenverordnung 2023/1230 + ISO/IEC TR 5469.
- **GB-12** (Kill-Switch + Rollback) — die **praktische** Prüfung ist
  ein **getester** Ablauf im Betrieb, nicht nur `true` im JSON.
  `validate.py` prüft das Flag; die **Evidenz** ist ein dokumentierter
  Test-Fall (z. B. «Kill-Switch-Test 2026-10-01, Ergebnis: OK,
  Verantwortlicher: X»).
- **GB-14** (Messung) — `measurement.method=true` im JSON ist nur die
  **Selbstaussage**; die **echte Evidenz** ist ein Testset (bei `pass^k`)
  oder ein Shadow-Run (bei `shadow`). Beide sind in `gw_core` +
  `examples/` verankert.
- **GB-04** (Deckel) — der `ceiling` ist eine **politische** Grenze,
  keine technische. Wer den Deckel hebt, ist die **Instanz**, die den
  Deckel verabschiedet hat (nicht der Betrieb).
- **Kein Rechtsrat** — Maschinenverordnung, ISO 42001, DSG sind
  **technische Grenzen** im Validator; die rechtliche Würdigung ist
  eine Rechtsfrage.

---

## 6 · Offene Punkte / Risiken

- **Typischer Fehler:** Level 3 als «Level 2 mit mehr Automatisierung»
  verkaufen. Der Unterschied: **die Kette ist fest** (deterministische
  Schrittfolge), die Freigabe ist **je Gate** (nicht je Aktion), und
  **Kill-Switch + Rollback sind harte Pflichten** (GB-12, `error`).
- **Dunkel-Variante** (`fixed_chain, mandate/exception_only`) — ist
  **legal**, aber mit den **erweiterten Leitplanken** der nächste
  Stufe (GB-12/GB-13: Kill-Switch, Shadow-Run, Sampling-Audit). `validate.py`
  prüft das als `warn` — wer die Leiste öffnet, muss die Leitplanken
  tragen.
- **Kein Mandat-Pflicht** auf Level 3 (erst ab Level 4, GB-08 `error`) —
  eine `fixed_chain` mit `mandate` ist die **Dunkel-Variante**, nicht
  das «Mandat-Modell» (das ist Level 4).
- **Kein Kill-Switch-Pflicht** auf Level 2 (GB-12 ist ab Level 3) —
  aber **auf Level 3 ist der Kill-Switch Pflicht** (GB-12, `error`).
  Der Unterschied: auf Level 2 kann das System «theoretisch abgestellt
  werden» (weil der Mensch je Aktion freigibt), auf Level 3 muss sich
  das System **selbst** abstellen (weil die Kette autonom wirkt).
- **Kein Mandat-/Limit-Engine** — das ist ab Level 4 (GB-08 `error`).
  Auf Level 3 ist die «Limiten-Pflicht» noch nicht da — nur die
  **Kill-Switch + Rollback + Messung**.

---

*Grundlage: `validate.py` (GB-01, 02, 03, 04, 05, 06, 12, 14, 15),
`schema.py::ALLOWED_AXES[3]`, `examples/gw3-predictive-maintenance.json`,
`../unternehmens-implementierung.md` §3, `../technik-eroeffnung.md`
(Mandat-Engine, Kill-Switch-Code). Keine Preise, kein Rechtsrat.*
