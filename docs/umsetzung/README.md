# Umsetzung je Autonomiegrad — technische Umsetzung im Unternehmen

> **Stand:** 2026-10-12 · **Repo:** `GRADweight/grad-autonomy` (Org)
>
> **Was hier ist:** Für **jeden** Autonomiegrad (Level 0–5) eine eigene
> technische Umsetzungsdoku — was im Unternehmen stehen muss, welche
> `gw_core`-Bausteine tragen, welche GB-Regeln hart greifen (Error), was
> **kein** Overkill ist, und wie Infrastruktur/Hardware/Standort je Grad
> aussehen. Keine Marketing-Grade, keine Preise, kein Rechtsrat.
>
> **Grundlage (Single Source of Truth):** `packages/gradbuild/gradbuild/validate.py`
> (GB-01…GB-16), `packages/gradbuild/gradbuild/schema.py` (Achsen, Datenklassen,
> Residency), `packages/gw_core/gw_core/__init__.py` (9 Bausteine),
> `examples/gw0…gw5.json` (je einer pro Grad, alle valid — `exit 0`).

---

## 1 · Die sechs Umsetzungsdokus (Level 0–5)

| Level | Name | Wer plant | Mensch greift ein bei | Umsetzungsdoku | Referenz-Case (valid) |
|---|---|---|---|---|---|
| **0** | Keine Autonomie | Mensch | `full_control`, jeder Schritt | [grad-0.md](grad-0.md) | `gw0-marktforschung.json` |
| **1** | Assistent | Mensch | `full_control` / `per_action` | [grad-1.md](grad-1.md) | `gw1-produktwissen-innendienst.json` |
| **2** | Copilot | Mensch *oder* Modell | `per_action`, je Aktion | [grad-2.md](grad-2.md) | `gw2-bewerbungsvorsortierung.json` |
| **3** | Workflow | `fixed_chain` *oder* Modell (Gate) | `per_gate` (+ Dunkel-Varianten) | [grad-3.md](grad-3.md) | `gw3-predictive-maintenance.json` |
| **4** | Delegiert (Mandat) | Modell | `mandate`, Limiten **im Zielsystem** | [grad-4.md](grad-4.md) | `gw4-c-teile-nachbestellen.json` |
| **5** | Eigentlich (isoliert) | Modell | `exception_only`, nur Ausnahme+Stichprobe | [grad-5.md](grad-5.md) | `gw5-standardretouren.json` |

Die Spalten «Wer plant» / «Mensch greift ein bei» sind das exakte Ergebnis
von `schema.py::ALLOWED_AXES` (Level → Kombinationen `(who_plans, human_role)`).
Alle sechs Beispieldateien laufen in `tests_gradbuild/` und im CI gegen
GB-01…GB-16; die `counterexample.json` ist der bewusste Negativfall.

### Numbering-Brücke (Level 0–5 vs. «Grad 01–05»)

In diesem Repo ist das **Level** die Nummer — `schema.ALLOWED_AXES` ist
mit den Ganzzahlen **0–5** indexiert, die Beispiele heissen `gw0…gw5`. Die
ältere PROJEKT.md-Narrative zählte «Grad 01–05» (1-basiert, ohne Level 0).
**Mapping, damit nichts vermischt wird:**

| Level (Code, Beisp.) | PROJEKT.md-Narrativ (1-basiert) |
|---|---|
| 0 (`gw0`, keine Autonomie) | (vor Grad 01 — Recherche/Mensch steuert) |
| 1 (`gw1`) = Assistent | Grad 01 |
| 2 (`gw2`) = Copilot | Grad 02 |
| 3 (`gw3`) = Workflow | Grad 03 |
| 4 (`gw4`) = Mandat/Agent | Grad 04 |
| 5 (`gw5`) = Eigen/Agent | Grad 05 |

Diese Doku folgt **consequent** Level 0–5 (wie `schema.py`), damit jede
Ankündigungs-Regel exakt die Trigger-Level aus `validate.py` hat.

---

## 2 · Die gemeinsame Grundlage (gilt für alle Grade)

### 2.1 Die zwei Achsen

Jeder Use-Case wird auf zwei Achsen eingeordnet (Schema `schema.py`):

- **Achse 1 — Wer plant den Weg?** `human` | `fixed_chain` | `model`
- **Achse 2 — Wo greift der Mensch ein?** `full_control` | `per_action` | `per_gate` | `mandate` | `exception_only`

Regel (GB-02): die Kombination muss in `ALLOWED_AXES[level]` stehen —
der Validator wirft `error` bei jeder anderen. «Zielarchitektur bauen,
Freigabe strenger halten» ist dabei bewusst erlaubt (z. B. `(model, per_gate)`
bei Level 3, `(human, per_action)` bei Level 2) — wer eine Grenze öffnet,
übernimmt aber die Leitplanken der nächsthohen Stufe.

### 2.2 Die drei Stufen-Eigenschaften (Regel of Two, GB-03)

Jeder Use-Case trägt drei boolesche Merkmale (Schema `BOOL_KEYS`):

- **[A] `foreign_input`** — ausserhalb des kontrollierten Systems entsteht (E-Mail, Web-Form, externe API)
- **[B] `sensitive_data`** — personenbezogen, Geschäftsgeheimnis, Finanzdaten
- **[C] `external_action`** — Wirkung, die ausserhalb sichtbar wird (E-Mail-Versand, Zahlung, API-Payload)

**Rule of Two (Meta/Runtim-Basis, GB-03):** bei Level ≥ 4 sind **alle drei
zugleich** ein harter `error`, **auch nicht** mit Mandat umgehbar. Das ist
bewusst hart: ein Mandat kann die Kette [A]+[B]+[C] nicht durch Limiten
entschärfen — der einzige legale Ausweg ist, **eine** der drei Kategorien
**strukturell** auf `false` zu setzen (z. B. `foreign_input=false` bei
`gw4`, `gw5`). Bei Level ≤ 3 ist die Kombination nur `warn`, weil der Mensch
die Kette bricht. Zwei von drei sind überall erlaubt.

### 2.3 Datenklassen und Residency (GB-15)

- **Datenklassen:** `frei` | `intern` | `vertraulich` | `geheim`
- **Residency-Werte:** `public` | `ch` | `eu` | `on_prem`

Härteste Grenze im ganzen Repo (GB-15, Level ≥ 4): `data_class='geheim'`
ist `error` — erlaubte Varianten sind **on-prem ohne Netz** oder **keine KI**.
Bei `sensitive_data=true` ohne `data_class` → `error`. → Details zu
Standort/Infrastruktur je Grad in den Einzel-Dokus und
[../unternehmens-implementierung.md](../unternehmens-implementierung.md) §3.

---

## 3 · Die `gw_core`-Bausteine — was trägt, je Grad

`packages/gw_core/gw_core/__init__.py` exportiert **neun** getestete Bausteine
(`84 passed, 6 subtests` im Stand 2026-10-11, `tests_gwcore/`):

| Baustein | Wozu | Trägt (ab welchem Level) |
|---|---|---|
| `audit.AuditTrail` | Append-only wer/was/wann, CSV-Export | empfohlen ab 1; Pflicht-Logik ab 4 (GB-11) |
| `approval.ApprovalQueue` | Freigabe/Anpassen/Zurückstellen | Level 2–3 (per_action/per_gate) |
| `authz.FreigabePolicy` | Rolle × Kontext, Least Privilege | ab 2, Pflicht ab 4 (GB-11) |
| `tracing.Tracer` | LLM-Request-Trace, Identität/Beobachtbarkeit | empfohlen ab 4 (GB-11) |
| `verify.pruefe_antwort` | Zweitmodell-Prüfung (Antwort vs. Fundstellen, VETO) | empfohlen 1–4 |
| `bexio.BexioZielsystemAdapter` | Zielsystem-Adapter, systemseitige Limiten, Dry-Run | ab 4 (GB-08), Referenz für EDI/ERP |
| `exception_queue.ExceptionQueue` | Deterministische Policy, Append-only, KPI | Pflicht 5 (GB-11); empfohlen ab 4 |
| `rollback.RollbackManager` | Snapshot-Registry, Reversal-Befehl, Append-only | Pflicht 3+ (GB-12) |
| `sampling_audit.SamplingAudit` | Reproduzierbare systematische Stichprobe, Evidenz | Pflicht 5 (GB-11); empfohlen ab 4 |

> **Wichtig:** «trägt» ist eine Empfehlung zur Umsetzung, nicht ein harter
> Validator-Trigger. Hart greifen nur die GB-Regeln in `validate.py`. Die
> Bausteine sind Mittel, die Pflicht ist das GB-Ergebnis.

---

## 4 · Wie man die Grade in die Praxis bringt (Ablauf)

1. **Case-JSON** je Use-Case schreiben (Schema `schema.py`, Vorlage
   `examples/gw*.json`).
2. **Validieren:** `python -m gradbuild.cli <datei>` → `0` = ok, `1` = Error,
   `2` = Schema-Problem. Im CI: `.github/workflows/ci.yml` prüft alle Beispiele.
3. **GB-Ergebnis lesen:** `info` (Kontext) · `warn` (Hinweis) · `error`
   (Blocker). Nur `error` sind echte Grenzen.
4. **Bausteine verdrahten:** je `gw_core`-Baustein aus §3, der zum Grad passt.
5. **Standort/Hardware** je Grad (in den Einzel-Dokus) — die Inferenz-Schicht
   ist die einzige mit echtem GPU-/Standort-Entscheid.
6. **Nicht Overkill-Treiben:** jede Einzel-Doku sagt explizit, was für diesen
   Grad **nicht** nötig ist (bewusst kleiner, nicht «mehr ist besser»).

---

## 5 · Offene Punkte / Entscheidungen (je Thema, mit Quellen)

- **Kill-Switch-Flag vs. Kill-Switch-Code:** `kill_switch_tested=true` im JSON
  wird nur geprüft (gb-12); ein *geprüfter*, getesteter Notausschalter im
  Deployment ist noch ein Mandanten-/Deployment-Baustein →
  [../technik-eroeffnung.md](../technik-eroeffnung.md).
- **Mandat-/Limit-Engine:** `mandate.limits_in_system` wird nur auf `true`
  geprüft; die eigentliche Enforce-Schicht im Zielsystem (ERP/EDI) ist
  eine Mandantenaufgabe (README §9 Punkt 5, `bexio.py` = Referenz-Adapter).
- **A2A Agent-Card + MCP:** Entwurf, nicht Code —
  [../grad4-5-multiagent-design.md](../grad4-5-multiagent-design.md) §4/§5 und
  [../technik-eroeffnung.md](../technik-eroeffnung.md).
- **Kein Rechtsrat:** GB-15, DSG (SR 235.1), EU AI Act (Annex III, Digital
  Omnibus VO (EU) 2026/1744), Maschinenverordnung 2023/1230, ISO/IEC TR 5469
  sind hier **technische Grenzen** (Validator). Die rechtliche Würdigung ist
  eine Rechtsfrage, nicht eine Validierungsfrage.

---

*Diese Übersicht ist ein Hub. Für die konkrete Umsetzung eines einzelnen
Grad: die jeweilige `grad-N.md`. Die übergreifenden Infrastruktur-,
Hardware-, Standort-Entscheide: [../unternehmens-implementierung.md](../unternehmens-implementierung.md).
Keine Preise, kein Rechtsrat.*
