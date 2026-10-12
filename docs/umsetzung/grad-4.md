# Level 4 — Delegiert (Modell plant, Mandat mit Limits im Zielsystem)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/grad-autonomy` · **Level 4**
>
> **Achsen** (`schema.py::ALLOWED_AXES[4]`):
> - `(model, mandate)` — **Modell plant**, Mensch gibt **Mandat** mit
>   **systemseitigen Limits**
> - `(model, exception_only)` — Modell plant, Ausnahmen gehen in
>   **Exception-Queue** (Level-4-Variante, erweiterte Leitplanken,
>   GB-08 `warn`)
>
> **Referenz-Case:** `examples/gw4-c-teile-nachbestellen.json` (valid,
> `exit 0`, Mandat `CHF 2'000 pro Bestellung` im ERP).
>
> Kurz: Das **Modell plant und führt aus**, **innerhalb eines Mandats
> mit systemseitigen Limits** (Berechtigung, Schnittstelle, Zahl-Limite).
> **Der Mensch tritt nur bei Ausnahmen + Stichprobe ein.**
> **Erste Stufe, an der GB-08 (Mandat), GB-11 (Identität/Audit) und
> GB-13 (Shadow/Vorschlag-First) harte Pflichten sind (alle `error`).**

---

## 1 · Was Level 4 ist (und was nicht)

**Ja:** C-Teile nachbestellen (Mandat bis CHF 2'000 pro Bestellung,
nur EDI/ERP), Konten-Abstimmung (Umbuchungen bis Schwelle), Beleg-Auslösung
(Gutschrift bis Limite) — **alles, was ein Mandat mit systemseitigen
Limits trägt und das Modell autonom ausführt.**

**Nein:** keine «Freitext-Mandate» ( Limits im **Prompt** — das ist
**GB-08 `error`**), keine «dunklen» Aktionen ohne Shadow-Run (GB-13),
keine «keine Identität» (GB-11).

Der Unterschied zu Level 3: **das Modell plant** (nicht die Kette), und
**der Mensch tritt nur bei Ausnahmen ein**. Die **Limits** sind
**im Zielsystem** (ERP/EDI), **nicht im Prompt**.

---

## 2 · GB-Pflichten auf Level 4 — die **eigentlichen** autonomen Kontrollen

| Regel | Auswirkung bei Level 4 |
|---|---|
| **GB-01** / **GB-02** | **error** — Schema + Achsen `(model, mandate)` oder `(model, exception_only)`. |
| **GB-08** Mandat mit Limits im System | **error** — `human_role='mandate'` **und** `mandate.limits_in_system=false` → «Limiten (Betrag, Empfängerkreis, Zeitraum) gehören in das Zielsystem (Berechtigung, Schnittstelle, Zahlungslimite) — **NICHT in den Prompt**». **Die zentrale Level-4-Pflicht.** |
| **GB-11** Identität + Audit-Log | **error** — `agent_identity_min_privilege=false` oder `audit_log=false` → «jeder Agent braucht eine eigene Identität mit minimalen Rechten» (Singapur MGF: 'identity management and access controls for agents'). |
| **GB-13** Shadow-Run + Vorschlag-First | **error** — `shadow_run_first=false` oder `proposal_mode_first=false` → «der neue Grad muss zuerst im Schattenbetrieb mitlaufen; erst Vorschlagsmodus, dann Mandat». |
| **GB-03** Rule of Two | **error**, wenn alle 3 zugleich (`foreign_input=true` + `sensitive_data=true` + `external_action=true`) → «bei Grad ≥ 4 nicht zulässig, auch nicht mit Mandat». |
| **GB-09** Geldwirkung + Money-Limit | **warn** — `money_effect=true` ohne `mandate.money_limit` → «Mandat mit Betrag, Empfängerkreis, Zeitraum definiert». |
| **GB-12** Kill-Switch + Rollback + Neu-Entscheid | **error** (wie auf Level 3) |
| **GB-14** Messung | **error** (wie auf Level 3) |
| **GB-15** Datenklasse | **error**, wenn `sensitive_data=true` und `data_class` fehlt; **`geheim`** → `error` (on-prem ohne Netz, oder keine KI) |

### Warum GB-08 die zentrale Level-4-Regel ist

**Mandat mit systemseitigen Limits** (GB-08) ist die **eigentliche
Autonomie-Grenze** auf Level 4. Das Modell darf **nicht** «frei» handeln,
sondern **innerhalb eines Mandats**, das **im Zielsystem** (Berechtigung,
Schnittstelle, Zahl-Limite) **systemseitig durchgesetzt** wird.

`mandate.limits_in_system=true` bedeutet:
- **Betrag** — die Zahlungslimite **im ERP** (nicht im Prompt),
  z. B. `CHF 2'000 pro Bestellung`.
- **Empfängerkreis** — nur auf bestimmte Lieferanten/Konten
  (Berechtigung **im ERP**, nicht im Prompt).
- **Zeitraum** — nur innerhalb bestimmter Zeitfenster
  (Berechtigung **im ERP**, nicht im Prompt).

`validate.py` prüft **einfach**: `limits_in_system=true` ist **Pflicht**.
Die **praktische Durchsetzung** ist im **Zielsystem** (ERP/EDI) —
`gw_core.bexio.BexioZielsystemAdapter` ist die **Referenz** für
diese Schicht.

---

## 3 · Referenz-Case `gw4-c-teile-nachbestellen.json`

```
level: 4
who_plans: model            human_role: mandate
foreign_input: false        sensitive_data: true
external_action: true       money_effect: true
customer_facing: false      customer_text_in_decisions: false
safety_critical: false      data_class: intern    data_residency: ch
mandate: { limits_in_system: true,
           money_limit: "CHF 2000 pro Bestellung (ERP-Freigabestrategie)" }
measurement: { method: pass^k }
governance: … agent_identity_min_privilege=TRUE, audit_log=TRUE,
  kill_switch_tested=TRUE, shadow_run_first=TRUE, proposal_mode_first=TRUE, …
```

**Lesart:** `money_effect=true` + `mandate.money_limit="CHF 2000"` →
GB-08/GB-09 erfüllt. `foreign_input=false` → **GB-03 nicht ausgelöst**
(2 von 3: [B]+[C], [A] fehlt). `data_class=intern` + `residency=ch` →
DSG-konsistent. `shadow_run_first=true` + `proposal_mode_first=true` →
GB-13 erfüllt. `agent_identity_min_privilege=true` + `audit_log=true` →
GB-11 erfüllt. `measurement.method=pass^k` → GB-14 erfüllt.

**Wichtig:** `foreign_input=false` ist der **einzige legale Ausweg**
aus der Rule-of-Two-Kette (GB-03) auf Level 4 — das Modell bestellt
C-Teile **ohne fremde Eingaben** (nur EDI/ERP, keine Freitext-Eingaben).
Das ist die **Struktur-Brücke**: eine der 3-Kategorien ist **strukturiell
auf false**, nicht «umgangen».

---

## 4 · Technische Umsetzung im Unternehmen

### 4.1 Was stehen muss (harte Pflichten)

- **Mandat mit systemseitigen Limits (GB-08)** — ein **dediziertes
  Servicekonto** (nicht das «allgemeine ERP-Konto») mit **genau den**
  Endpunkten, die das Modell braucht (Least Privilege, GB-11). Die
  **Zahlungslimite** sind **im ERP** (Berechtigung, Schnittstelle,
  Zahl-Limite). `gw_core.bexio.BexioZielsystemAdapter` ist die **Referenz**
  für diese Schicht (systemseitige Limits, Dry-Run).
- **Agenten-Identität (GB-11)** — ein **eigener Service-Identität**
  (z. B. Entra Agent ID, Azure AD Service-Principal, OAuth2 Client
  Credentials), **nicht** eine «allgemeine» API-Key. `agent_identity_
  min_privilege=true` im JSON = **Selbstaussage**; die **Evidenz** ist
  eine dokumentierte Service-Identität im Deployment (z. B. «Service
  Principal `gw4-agent`, Scope: `ERP.C-Teile.Read`, `ERP.C-Teile.Write`,
  Limit: `CHF 2000 pro Bestellung`, erstellt 2026-10-01, Verantwortlicher: X»).
- **Audit-Log (GB-11)** — `gw_core.audit.AuditTrail` (Append-only) +
  `gw_core.tracing.Tracer` (LLM-Request-Trace). Wer, wann, welche
  Aktion, welche Identität, welches Mandat, welche Grenze — **alles
  protokolliert**.
- **Shadow-Run (GB-13)** — der **neue Grad** muss **zuerst** im
  **Schattenbetrieb** mitlaufen (das Modell trifft Entscheidungen, aber
  **keine realen Aktionen**). `validate.py` prüft `shadow_run_first=true`;
  die **praktische Prüfung** ist ein dokumentierter Shadow-Run (z. B.
  «Shadow-Run 2026-09-15, 1'000 Fälle, 95% korrekt, 5% Fehlklassifikation,
  kein reales Geld bewegt, Verantwortlicher: X»).
- **Vorschlag-First (GB-13)** — erst **Vorschlagsmodus** (das Modell
  vorschlägt, der Mensch bestätigt), dann **Mandat** (das Modell führt
  aus, innerhalb des Mandats). `validate.py` prüft `proposal_mode_first=true`.
- **Kill-Switch + Rollback (GB-12)** — wie auf Level 3 (GB-12 `error`).
- **Messung (GB-14)** — `pass^k` (Golden-Set) oder `shadow` (Shadow-Run).
- **Mandats-Limits im Zielsystem (GB-08/GB-09)** — die Limits sind
  **im ERP**, nicht im Prompt. `gw_core.bexio.BexioZielsystemAdapter`
  ist die **Referenz** für diese Schicht.

### 4.2 Bausteine (`gw_core`) — die Level-4-Komplett-Ausstattung

| Baustein | Rolle auf Level 4 |
|---|---|
| `rollback.RollbackManager` | **Pflicht** (GB-12) — Snapshot, Reversal-Befehl, Append-only, KPI |
| `audit.AuditTrail` | **Pflicht** (GB-11) — wer, wann, welche Aktion, welche Identität |
| `authz.FreigabePolicy` | **Pflicht** (GB-11) — die Service-Identität, die Limiten |
| `tracing.Tracer` | **Pflicht** (GB-11) — LLM-Request-Trace |
| `approval.ApprovalQueue` | **empfohlen** — die Ausnahmen (bei `exception_only`) |
| `verify.pruefe_antwort` | **empfohlen** — VETO gegen Halluzinationen (Geld-Mandate!) |
| `exception_queue.ExceptionQueue` | **empfohlen** (bei `exception_only`; Pflicht auf Level 5) |
| `sampling_audit.SamplingAudit` | **empfohlen** (bei `exception_only`; Pflicht auf Level 5) |
| `bexio.BexioZielsystemAdapter` | **Pflicht** (GB-08) — die Limiten im Zielsystem, Dry-Run |

### 4.3 Hardware / Infrastruktur

| Schicht | Option |
|---|---|
| Inferenz | 32B–70B (oder MoE), CH-Cloud (z. B. Exoscale CH-GVA-2 A30) oder On-Prem. Bei `data_class=intern` → CH-zonal empfohlen. |
| Mandats-Engine (Zielsystem) | ERP/EDI — Shadow-Modus + Prod-Modus. Die Limiten sind **im ERP**, nicht im Prompt. |
| Identität | Service-Principal / OAuth2 Client Credentials — `agent_identity_min_privilege`. |
| Control-Plane | `gw_core` (SQLite) — lokal oder CH. |
| Messung | `pass^k` (Golden-Set) oder `shadow` (Shadow-Run) — lokal. |
| Belegkette | `AuditTrail` + `RollbackManager` (Snapshot vorher/nachher) — lokal. |

---

## 5 · Absicherung & Grenzen

- **GB-08** (Mandat mit systemseitigen Limits) ist die **härteste
  Level-4-Grenze**: ein Mandat ohne `limits_in_system=true` ist
  **inkonsistent** (GB-08 `error`). Ein Mandat **im Prompt** (statt
  im Zielsystem) ist **kein** Mandat — das ist der Punkt, an dem der
  Validator ehrlich bleibt.
- **GB-11** (Identität + Audit) — die **praktische** Prüfung ist eine
  **dokumentierte** Service-Identität im Deployment + ein **auditiertes**
  Log. `validate.py` prüft die **Flag**-Selbstaussage; die **Evidenz**
  ist im Betrieb.
- **GB-13** (Shadow-Run + Vorschlag-First) — die **praktische** Prüfung
  ist ein **dokumentierter** Shadow-Run (z. B. «Shadow-Run 2026-09-15,
  1'000 Fälle, 95% korrekt» + «Proposal-Modus-Test 2026-09-20, 200
  Vorschläge, 150 akzeptiert»). `validate.py` prüft die **Flag**-Selbstaussage.
- **GB-03** (Rule of Two, `error` bei Level ≥ 4) — der **einzige legale
  Ausweg** ist, eine der 3-Kategorien **strukturell** auf `false` zu
  setzen (z. B. `foreign_input=false` bei `gw4`). Das ist **nicht**
  «umgangen», sondern **durch Struktur erfüllt** (EDI/ERP statt
  Freitext-Eingaben).
- **Kein Rechtsrat** — DSG, AI Act, Maschinenverordnung sind
  **technische Grenzen** im Validator; die rechtliche Würdigung ist
  eine Rechtsfrage.

---

## 6 · Offene Punkte / Risiken

- **Typischer Fehler:** Level 4 als «Level 3 mit mehr Modell» verkaufen.
  Der Unterschied: **das Modell plant** (nicht die Kette), **der Mensch
  tritt nur bei Ausnahmen ein** (nicht je Gate), und **Mandat + Identität
  + Shadow-Run + Vorschlag-First sind harte Pflichten** (GB-08/GB-11/GB-13,
  alle `error`).
- **Kein Mandat ohne Limits im System** — das ist der **eigentliche
  Unterschied** zu Level 3: auf Level 4 sind die Limits **im ERP**
  (Berechtigung, Schnittstelle, Zahl-Limite), **nicht im Prompt**.
  Ein «Mandat im Prompt» ist **kein** Mandat (GB-08 `error`).
- **Keine anonyme Identität** — `agent_identity_min_privilege=true`
  bedeutet **Service-Principal / OAuth2**, nicht eine «allgemeine»
  API-Key. (GB-11 `error` ohne die Identität.)
- **Kein Shadow-Run** — `shadow_run_first=true` bedeutet ein
  **dokumentierter** Shadow-Run im Betrieb (z. B. «Shadow-Run 2026-09-15,
  1'000 Fälle, 95% korrekt»), nicht nur `true` im JSON.
- **Kein Money-Limit** — `money_effect=true` auf Level 4 ohne
  `mandate.money_limit` ist ein **warn**, aber ein **Versprechen,
  keine Grenze** (GB-09). Ein «Mandat ohne Betrag» ist ein
  **unvollständiges** Mandat.
- **Kein Mandat-Engine (Code)** — die **Enforcement** der Limits ist
  im **Zielsystem** (ERP/EDI), nicht im `gw_core`-Code.
  `gw_core.bexio.BexioZielsystemAdapter` ist die **Referenz**
  für diese Schicht; die **praktische** Implementation ist eine
  **Mandanten-Aufgabe** (README §9 Punkt 5, `bexio.py` = Referenz-Adapter).

---

*Grundlage: `validate.py` (GB-01, 02, 03, 08, 09, 11, 12, 13, 14, 15),
`schema.py::ALLOWED_AXES[4]`, `examples/gw4-c-teile-nachbestellen.json`,
`../unternehmens-implementierung.md` §3, `../technik-eroeffnung.md`
(Mandat-Engine, Kill-Switch-Code, A2A/MCP). Keine Preise, kein Rechtsrat.*
