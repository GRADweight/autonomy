# Level 5 — Eigentlich (Modell plant, Ausnahme-Queue + Stichprobe)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/grad-autonomy` · **Level 5**
>
> **Achsen** (`schema.py::ALLOWED_AXES[5]`):
> - `(model, exception_only)` — **Modell plant**, Ausnahmen gehen in
>   **Exception-Queue**, **Stichprobe** (Sampling-Audit) im Betrieb.
>
> **Referenz-Case:** `examples/gw5-standardretouren.json` (valid,
> `exit 0`, isoliertes Vision-Modell, `foreign_input=false` für den
> Entscheid-Agenten).
>
> Kurz: Das **Modell plant und führt aus**, **ohne menschliches
> Vorschlags-Eintreten** — **ausser** bei Ausnahmen (Exception-Queue)
> und Stichproben (Sampling-Audit). **Die höchste Stufe im System.**
> **Alles, was auf Level 4 Pflicht ist, ist auf Level 5 Pflicht — plus:
> `exception_queue` + `sampling_audit` als System-Pflicht (GB-11, error).**

---

## 1 · Was Level 5 ist (und was nicht)

**Ja:** Standardretouren Ende-zu-Ende (Zustand per Vision-Modell,
Gutschrift bis Limite, ohne menschliches Vorschlags-Eintreten),
Konten-Abstimmung (Umbuchungen bis Schwelle, darüber Vorschlag),
Kunden-Self-Service (Ende-zu-Ende, nur Ausnahmen + Stichprobe).

**Nein:** keine «Kein Mandat» (GB-08, `error`), keine «Keine Identität»
(GB-11, `error`), keine «Kein Shadow-Run» (GB-13, `error`), keine
«Keine Exception-Queue + Sampling-Audit» (GB-11, `error`).

Der Unterschied zu Level 4: **der Mensch tritt nicht in den Vorschlag
ein** (nicht `mandate`, sondern `exception_only`). **Ausser** bei
**Ausnahmen** (Exception-Queue) und **Stichproben** (Sampling-Audit).

### Isolation (`terminology.isoliert`, README §7)

Level 5 ist **isoliert**:
- **Kein Tool-Zugriff** für den **Klassifikator** (tool-frei, GB-05)
- **Keine fremden Eingaben** als **Trigger** für den **Entscheid-Agenten**
  (`foreign_input=false` für den Entscheid-Agenten, GB-03)
- **Keine Kombination** aus sensibler Daten + external Action ohne
  Mandat (GB-08/GB-03)

**Das ist der Unterschied** zwischen «Level 5» und «chaotische
Autonomie»: Level 5 ist **isoliert**, **nicht frei**.

---

## 2 · GB-Pflichten auf Level 5 — die **vollständigste** Stufe

| Regel | Auswirkung bei Level 5 |
|---|---|
| **GB-01** / **GB-02** | **error** — Schema + Achsen `(model, exception_only)`. |
| **GB-03** Rule of Two | **error**, wenn alle 3 zugleich (`foreign_input=true` + `sensitive_data=true` + `external_action=true`) → «bei Grad ≥ 4 nicht zulässig, auch nicht mit Mandat». |
| **GB-08** Mandat mit Limits im System | **error** (wie Level 4) |
| **GB-11** Identität + Audit + Exception-Queue + Sampling-Audit | **error** — `exception_queue=false` **oder** `sampling_audit=false` **oder** `agent_identity_min_privilege=false` **oder** `audit_log=false` → «Grad 5: fehlende Kontrollen (exception_queue, sampling_audit, agent_identity, audit_log)». **Die vollständigste Level-5-Pflicht.** |
| **GB-13** Shadow-Run + Vorschlag-First | **error** (wie Level 4) |
| **GB-09** Geldwirkung + Money-Limit | **warn** (wie Level 4) |
| **GB-12** Kill-Switch + Rollback + Neu-Entscheid | **error** (wie Level 4) |
| **GB-14** Messung | **error** (wie Level 4) |
| **GB-15** Datenklasse | **error**, wenn `sensitive_data=true` und `data_class` fehlt; **`geheim`** → `error` (on-prem ohne Netz, oder keine KI) |

### Warum GB-11 (Exception-Queue + Sampling-Audit) die zentrale
Level-5-Regel ist

**Exception-Queue + Sampling-Audit** (GB-11) sind die **eigentlichen
Autonomie-Kontrollen** auf Level 5. «Ohne Mensch» heisst **nicht**
«ohne Kontrolle» — es heisst:
- **Exception-Queue:** die **Ausnahmen** (Fälle, die das Modell nicht
  selbst entscheidet) gehen in eine **Queue**, die ein **Mensch**
  verarbeitet.
- **Sampling-Audit:** die **Stichproben** (ein subset der Fälle, die das
  Modell **selbst** entschieden hat) werden **systematisch**
  **auditiert** (reproduzierbar, mit Kriterien, Evidenz, «Audit-von-Audit»).

`validate.py` prüft **einfach**: `exception_queue=true` **und**
`sampling_audit=true` **und** `agent_identity_min_privilege=true`
**und** `audit_log=true` → alle 4 → **Pflicht auf Level 5**.

`gw_core.exception_queue.ExceptionQueue` +
`gw_core.sampling_audit.SamplingAudit` sind die **Bausteine**, die
Level 5 **tragen**.

---

## 3 · Referenz-Case `gw5-standardretouren.json`

```
level: 5
who_plans: model            human_role: exception_only
foreign_input: false        sensitive_data: true
external_action: true       money_effect: true
customer_facing: true       customer_text_in_decisions: true
safety_critical: false      data_class: intern    data_residency: eu
mandate: { limits_in_system: true,
           money_limit: "pro Fall und pro Tag im ERP; nur auf ursprüngliches Zahlungsmittel" }
measurement: { method: shadow }
governance: … agent_identity_min_privilege=TRUE, audit_log=TRUE,
  exception_queue=TRUE, sampling_audit=TRUE,
  kill_switch_tested=TRUE, shadow_run_first=TRUE, proposal_mode_first=TRUE, …
```

**Lesart:**
- `human_role=exception_only` → **Level 5** (GB-02 erfüllt).
- `foreign_input=false` **für den Entscheid-Agenten** → **GB-03 nicht
  ausgelöst** (2 von 3: [B]+[C]+[D], [A] fehlt für den Entscheid-Agenten).
  **Wichtig:** `customer_text_in_decisions=true` + `customer_facing=true`
  → **GB-05 `warn`** — der **Klassifikator** (separat, tool-frei) klassifiziert
  die Kundentexte, der **Entscheid-Agent** arbeitet auf **strukturierten
  Daten** (nicht auf Fremdtext). Das ist die **Isolation**: der
  **Klassifikator** = Vision-Modell **ohne Tools** (GB-05), der
  **Entscheid-Agent** = strukturierte Daten + Mandat (GB-08).
- `money_effect=true` + `mandate.money_limit="pro Fall und pro Tag im
  ERP"` → GB-08/GB-09 erfüllt.
- `agent_identity_min_privilege=true` + `audit_log=true` → GB-11 (Teil 1).
- `exception_queue=true` + `sampling_audit=true` → GB-11 (Teil 2).
  **Alle 4 Flags `true` → GB-11 erfüllt.**
- `shadow_run_first=true` + `proposal_mode_first=true` → GB-13 erfüllt.
- `measurement.method=shadow` → GB-14 erfüllt (Shadow-Run im Betrieb).
- `kill_switch_tested=true` + `automatic_rollback=true` → GB-12 erfüllt.
- `data_class=intern` + `residency=eu` → DSG-konsistent.
- `safety_critical=false` → kein Deckel-Problem (GB-06).

**Wichtig:** `foreign_input=false` für den **Entscheid-Agenten** (nicht
für den **Klassifikator**) — das ist die **Isolation** (GB-05): der
Klassifikator arbeitet auf **Fremdtext** (Vision-Modell, tool-frei),
der Entscheid-Agent arbeitet auf **strukturierten Daten** (Mandat,
systemseitig). Das ist die **einzige legale** Level-5-Konstellation
bei `customer_facing=true` + `customer_text_in_decisions=true`.

---

## 4 · Technische Umsetzung im Unternehmen

### 4.1 Was stehen muss (die **vollständigste** Ausstattung)

- **Exception-Queue (GB-11)** — `gw_core.exception_queue.ExceptionQueue`:
  **deterministische Policy** (wer/was/wann in die Queue), **Append-only**,
  **KPI** (Verarbeitungszeit, Queue-Länge). Die **Ausnahmen** (Fälle,
  die das Modell nicht selbst entscheidet) gehen in die **Queue**, die ein
  **Mensch** (oder ein **niedrigeres Level** — z. B. Level 3/4) verarbeitet.
- **Sampling-Audit (GB-11)** — `gw_core.sampling_audit.SamplingAudit`:
  **reproduzierbare systematische Stichprobe** (welche Fälle, welche
  Kriterien, welche Evidenz), **Audit-von-Audit** (wer hat die Stichprobe
  gemacht, wann, welche Kriterien). Die **Stichproben** (Fälle, die das
  Modell **selbst** entschieden hat) werden **systematisch auditiert**.
- **Agenten-Identität + Audit-Log (GB-11)** — wie auf Level 4 (z. B.
  Service-Principal / OAuth2 Client Credentials) + `gw_core.audit.
  AuditTrail` (Append-only) + `gw_core.tracing.Tracer` (LLM-Request-Trace).
- **Mandat mit systemseitigen Limits (GB-08)** — wie auf Level 4
  (z. B. `mandate.money_limit="pro Fall und pro Tag im ERP"`).
- **Shadow-Run + Vorschlag-First (GB-13)** — wie auf Level 4 (d. h.
  bei Level 5 ist `proposal_mode_first=true` auch **Pflicht** — das
  Modell läuft **zuerst** im Vorschlagsmodus, **dann** im autonomen Modus).
- **Kill-Switch + Rollback (GB-12)** — wie auf Level 4.
- **Messung (GB-14)** — `shadow` (Shadow-Run) oder `pass^k` (Golden-Set).
- **Isolation (GB-05)** — der **Klassifikator** (z. B. Vision-Modell)
  ist **tool-frei** (kein Tool-Zugriff), der **Entscheid-Agent** arbeitet
  auf **strukturierten Daten** (nicht auf Fremdtext). `foreign_input=
  false` für den Entscheid-Agenten.
- **Dedizierte Sandbox (GB-11)** — jeder **Agent** in seiner **eigenen**
  Sandbox (kein Agent sieht den **Token** oder den **Zustand** eines
  anderen) — die **Isolation** der Level-5-Komponenten.
- **Beleg-Export (GB-11)** — `AuditTrail` als **CSV/Parquet**, für die
  **Revision** (z. B. `audit_log.export(format="parquet")`).
- **Kill-Schalter (GB-12)** — ein **systemseitiger**, **nicht
  promptseitiger** Kill-Schalter (z. B. eine API-Call, ein Web-Button,
  ein CLI-Befehl) — der **eigentliche** Kill-Schalter.

### 4.2 Bausteine (`gw_core`) — alle 9 Bausteine sind relevant

| Baustein | Rolle auf Level 5 |
|---|---|
| `exception_queue.ExceptionQueue` | **Pflicht** (GB-11) — die Ausnahmen, Append-only, KPI |
| `sampling_audit.SamplingAudit` | **Pflicht** (GB-11) — die Stichproben, reproduzierbar, Evidenz |
| `rollback.RollbackManager` | **Pflicht** (GB-12) — Snapshot, Reversal-Befehl, Append-only, KPI |
| `audit.AuditTrail` | **Pflicht** (GB-11) — wer, wann, welche Aktion, welche Identität, Append-only, Beleg-Export |
| `authz.FreigabePolicy` | **Pflicht** (GB-11) — die Service-Identität, die Limiten, Least Privilege |
| `tracing.Tracer` | **Pflicht** (GB-11) — LLM-Request-Trace |
| `approval.ApprovalQueue` | **empfohlen** — die Ausnahmen (bei `exception_only`; kann die **Exception-Queue** sein) |
| `verify.pruefe_antwort` | **empfohlen** — VETO gegen Halluzinationen (Geld-Mandate, Kundentexte!) |
| `bexio.BexioZielsystemAdapter` | **Pflicht** (GB-08) — die Limiten im Zielsystem, Dry-Run |

### 4.3 Hardware / Infrastruktur

| Schicht | Option |
|---|---|
| Inferenz | 70B oder MoE (z. B. Qwen3-35B-A3B), CH-Cloud (z. B. Exoscale CH-GVA-2 A30) oder On-Prem. Bei `data_class=intern` → CH-zonal empfohlen. **Getrennter Klassifikator**: 7B–14B tool-frei (z. B. Ollama, lokal). |
| Mandats-Engine (Zielsystem) | ERP/EDI — Shadow-Modus + Prod-Modus. Die Limiten sind **im ERP**. |
| Identität | Service-Principal / OAuth2 Client Credentials — `agent_identity_min_privilege`. |
| Isolation (Sandbox) | Jeder Agent in seiner **eigenen** Sandbox (kein Agent sieht den Token/Zustand eines anderen) — z. B. Docker-Container, Kubernetes-Pods, oder separate VMs. |
| Beleg-Export | `AuditTrail` als CSV/Parquet — lokal oder CH-Cloud. |
| Control-Plane | `gw_core` (SQLite) — lokal oder CH. |
| Messung | `shadow` (Shadow-Run) oder `pass^k` (Golden-Set) — lokal. |

---

## 5 · Absicherung & Grenzen

- **GB-11** (Exception-Queue + Sampling-Audit + Identität + Audit) ist
  die **härteste Level-5-Grenze**: ohne **alle 4** ist Level 5 **nicht
  valid** (GB-11 `error`). Das ist der **Eigentliche Unterschied** zu
  Level 4: auf Level 4 sind `exception_queue` + `sampling_audit`
  **empfohlen** (bei `exception_only`), auf Level 5 sind sie **Pflicht**.
- **GB-03** (Rule of Two, `error` bei Level ≥ 4) — der **einzige legale
  Ausweg** ist, eine der 3-Kategorien **strukturell** auf `false` zu
  setzen. Bei `gw5` (Standardretouren) ist das die **Isolation**: der
  **Klassifikator** arbeitet auf Fremdtext (tool-frei), der
  **Entscheid-Agent** arbeitet auf strukturierten Daten
  (`foreign_input=false` für den Entscheid-Agenten).
- **GB-05** (Kundentexte, `warn`) — der **Klassifikator** (z. B.
  Vision-Modell) klassifiziert die Kundentexte, das ist **isoliert**
  (tool-frei). Der **Entscheid-Agent** arbeitet auf **strukturierten
  Daten** (nicht auf Fremdtext). Das ist die **einzige legale**
  Level-5-Konstellation bei `customer_facing=true` +
  `customer_text_in_decisions=true`.
- **GB-15** (Datenklasse, `error` bei `geheim` + Level ≥ 4) — bei
  **`geheim`** (z. B. Patent-Daten, M&A-Vorbereitung) ist Level 5
  **nur legal** bei **on-prem ohne Netz** (GB-15, `error` sonst).
  **Das ist die härteste Grenze im ganzen System.**
- **Kein Rechtsrat** — DSG, AI Act, Maschinenverordnung, NIS2, DORA,
  CRA sind **technische Grenzen** im Validator; die rechtliche Würdigung
  ist eine Rechtsfrage.

---

## 6 · Offene Punkte / Risiken

- **Typischer Fehler:** Level 5 als «Level 4 mit mehr Modell» verkaufen.
  Der Unterschied: **der Mensch tritt nicht in den Vorschlag ein**
  (nicht `mandate`, sondern `exception_only`), und **Exception-Queue +
  Sampling-Audit sind harte Pflichten** (GB-11 `error`).
- **Kein «Ohne Mensch = ohne Kontrolle»** — Level 5 ist **isoliert**,
  **nicht frei**. Die **Kontrollen** (Exception-Queue, Sampling-Audit,
  Identität, Audit, Kill-Switch, Rollback) sind **stärker** als auf
  Level 4, **nicht schwächer**.
- **Kein Klassifikator mit Tools** — der **Klassifikator** (z. B.
  Vision-Modell) ist **tool-frei** (GB-05), der **Entscheid-Agent** arbeitet
  auf **strukturierten Daten** (`foreign_input=false` für den
  Entscheid-Agenten). Das ist die **Isolation**.
- **Kein Mandat ohne Limits im System** — wie auf Level 4 (GB-08, `error`).
- **Keine anonyme Identität** — wie auf Level 4 (GB-11, `error`).
- **Kein Shadow-Run** — wie auf Level 4 (GB-13, `error`).
- **Kein Kill-Schalter (Code)** — `kill_switch_tested=true` im JSON
  ist nur die **Selbstaussage**; der **eigentliche** Kill-Schalter
  (Code, z. B. eine API-Call, ein Web-Button) ist ein
  **Deployment-Baustein** →
  [../technik-eroeffnung.md](../technik-eroeffnung.md).
- **Kein A2A/MCP (Code)** — die **Agent-Interaktion** (Agent-to-Agent,
  Multi-Agent) ist **entwurf** (nicht Code) →
  [../grad4-5-multiagent-design.md](../grad4-5-multiagent-design.md)
  §4/§5.
- **Kein Mandant-Deployment (Code)** — die **praktische** Implementation
  (Zielsystem, ERP, Identität, Sandbox) ist eine **Mandanten-Aufgabe**,
  nicht im `gw_core`=Code. `gw_core` ist die **Referenz**
  (Bausteine, Tests, GB-Prüfung), nicht das **Deployment**.

---

*Grundlage: `validate.py` (GB-01, 02, 03, 05, 08, 09, 11, 12, 13, 14, 15),
`schema.py::ALLOWED_AXES[5]`, `examples/gw5-standardretouren.json`,
`../unternehmens-implementierung.md` §3, `../technik-eroeffnung.md`
(Mandat-Engine, Kill-Switch-Code, A2A/MCP, Mandant-Deployment),
`../grad4-5-multiagent-design.md` (Multi-Agent-Architektur). Keine Preise,
kein Rechtsrat.*
