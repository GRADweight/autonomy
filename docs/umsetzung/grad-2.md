# Level 2 — Copilot (Modell vorschlägt, Mensch freigibt je Aktion)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/gradautonomy` · **Level 2**
>
> **Achsen** (`schema.py::ALLOWED_AXES[2]`): `(human, per_action)` oder
> `(model, per_action)` — **der Mensch plant OR das Modell plant**, aber
> **jede Aktion wird vom Menschen freigegeben** (Freigabe-Fluss).
> **Referenz-Case:** `examples/gw2-bewerbungsvorsortierung.json` (valid,
> `exit 0`, **Deckel 2** — `max_level=2`).
>
> Kurz: Ein **Copilot**, der **Vorschläge macht** (Antwort, Ticket,
> Sortierung) und **muss freigegeben werden** bevor er wirkt. **Der Mensch
> bleibt die letzte Instanz je Aktion.**

---

## 1 · Was Level 2 ist (und was nicht)

**Ja:** Bewerbungsvorsortierung, Rechnungs-Erstellungsvorschläge,
E-Mail-Entwürfe, Ticket-Klassifikation — **alles, was eine Vorschlags-
UI hat und eine Freigabe einfordert**. Das Modell trifft **keine** endgültige
Aktion selbst; der Mensch klickt «ok»/«korrigieren»/«ablehnen».

**Nein:** keine autonomen Schleifen, kein Geld (ohne Mandat — Level 4),
keine «dunklen» Aktionen ohne Freigabe.

Der Unterschied zu Level 1: **das Modell plant mit** (nicht nur der Mensch),
aber die **Freigabe bleibt je Aktion**. Der Unterschied zu Level 3:
**keine feste Kette** (fixed chain), die Freigabe ist **je Aktion**, nicht
**je Gate**.

---

## 2 · GB-Pflichten auf Level 2 — die **härteste** Regel ist GB-07

| Regel | Auswirkung bei Level 2 |
|---|---|
| **GB-01** / **GB-02** | **error** — Schema + Achsen `(human, per_action)` oder `(model, per_action)` |
| **GB-07** Übernahmequote | **error** — `adoption_rate_monitored=false` → «Übernahmequote wird nicht überwacht» (Automation Bias, Art. 21 DSG). **Die zentrale Level-2-Pflicht.** |
| **GB-10** Aussenwirkung | **error** bei `customer_facing=true` + `external_action=true` (keine Aussenwirkung) — aber: bei `per_action` ist `external_action` **erwartet** (das Modell wirkt, der Mensch gibt frei), also GB-10 **nicht** das Trigger-Szenario. |
| **GB-04** Deckel | **error** bei `level > ceiling.max_level` — das `gw2`-Beispiel hat `max_level=2` (Anhang III AI Act + Art. 21 DSG) |
| **GB-03** Rule of Two | `warn`, wenn alle 3 zugleich |
| **GB-05** Kundentexte | `warn`, wenn `customer_text_in_decisions=true` |
| **GB-15** Datenklasse | **error**, wenn `sensitive_data=true` und `data_class` fehlt |

**Keine** harten GB-08/11/12/13/14 auf Level 2.

### Warum GB-07 die zentrale Level-2-Regel ist

**Automation Bias** (Art. 21 DSG, Singapur MGF 2026 «Bound the risks
upfront»): wenn ein Fast-bestätigter Vorschlag gemacht wird, wird die
menschliche Entscheidung zur **Durchklicken** — die Übernahmequote wird
zur relevanten Metrik. `validate.py` erzwingt das auf Level 2 als **error**
wenn `adoption_rate_monitored=false`. Das ist der **eigentliche
Sicherheits-Nutzen** von Level 2: der Mensch bleibt in der Schleife, und
die **Quote** der Übernahme ist die entscheidende Kennzahl.

---

## 3 · Referenz-Case `gw2-bewerbungsvorsortierung.json`

```
level: 2
who_plans: model            human_role: per_action
foreign_input: true         sensitive_data: true
external_action: false      money_effect: false
customer_facing: false      customer_text_in_decisions: false
safety_critical: false      data_class: vertraulich    data_residency: eu
ceiling: { max_level: 2,
           reason: "Anhang III AI Act (Arbeitswelt) + Art. 21 DSG + Automation-Bias-Risiko",
           regulation: "EU AI Act Annex III (in Kraft ab 2.12.2027); DSG Art. 21" }
governance: … adoption_rate_monitored=TRUE, audit_log=true,
  kill_switch_tested=true, shadow_run_first=FALSE, proposal_mode_first=FALSE, …
```

**Lesart:** `adoption_rate_monitored=true` → **GB-07 erfüllt** (sonst
`error`). `foreign_input=true` + `sensitive_data=true` → 2 von 3 Rule-of-Two
→ `warn` (nicht `error`, Level 2). `ceiling.max_level=2` → der Case kann
**nicht** auf Level 3+ hochgestuft werden (GB-04), weil die
Arbeitswelt-Klassifikation (Annex III) das Deckel setzt. `data_class=
vertraulich` + `residency=eu` → DSG/AI-Act-konsistent.

---

## 4 · Technische Umsetzung im Unternehmen

### 4.1 Was stehen muss

- **Freigabe-Fluss** (`per_action`) — eine UI/CLI/E-Mail-Filter, die
  **jede** Vorschlag-Aktion anzeigt und **eine Freigabe-Entscheidung
  einfordert** (ok / korrigieren / ablehnen). Kann ein simples Webform,
  ein E-Mail-«Freigeben/-Korrigieren/-Verwerfen»-Fluss, oder eine
  Approval-Queue sein.
- **Übernahmequote-Messung** (GB-07) — ein **Zähler + Dashboard**, der
  pro Woche/Monat den Wert «wie oft wurde der Vorschlag so übernommen»
  misst. `gw_core.tracing` (LLM-Request-Trace) + ein Audit-Eintrag pro
  Freigabe-Entscheidung → die **Quellen** der Übernahmequote. Ein
  Verantwortlicher liest die Quote (das ist der **eigentliche** GB-07-
  Check — nicht nur das `true` im JSON).
- **Audit-Trail** — `gw_core.audit.AuditTrail`: wer, wann, welche
  Freigabe-Entscheidung, Vorschlag + Kontext.
- **Zweitmodell-Prüfung** — `gw_core.verify.pruefe_antwort` (Halluzinations-
  + Quellenprüfung, VETO). Besonders bei Bewerbungsvorsortierung.
- **Freigabe-Policy** — `gw_core.authz.FreigabePolicy` (Least Privilege):
  welche Rollen dürfen welche Freigaben treffen.

### 4.2 Bausteine (`gw_core`)

| Baustein | Rolle auf Level 2 |
|---|---|
| `approval.ApprovalQueue` | **empfohlen** — die Freigabe-Flüsse, Freigabe/Anpassen/Zurückstellen |
| `authz.FreigabePolicy` | **empfohlen** — wer darf welche Freigaben treffen |
| `verify.pruefe_antwort` | **empfohlen** — VETO gegen Halluzinationen, Quellen |
| `audit.AuditTrail` | **empfohlen** — wer, wann, welche Freigabe |
| `tracing.Tracer` | **empfohlen** — LLM-Request-Trace → Übernahmequote-Source |
| `rollback` / `exception_queue` / `sampling_audit` / `bexio` | **nicht** nötig (kein Mandat, keine autonomen Schleifen, kein Geld) |

### 4.3 Hardware / Infrastruktur

| Schicht | Option |
|---|---|
| Inferenz | 7B–14B, Ollama, lokal oder CH-Cloud (z. B. Exoscale CH-GVA-2 A30). |
| RAG (z. B. Bewerbungen) | Vektorspeicher, CH/EU. Bei `vertraulich` → On-Prem oder CH-zonal. |
| Control-Plane | `gw_core` (SQLite) — lokal oder CH. |
| Freigabe-UI | Lokales Web, E-Mail-Filter, oder ein simples Webform. |
| Zielsystem | **Keine** (Level 2, `external_action=false` im Beispiel). |

---

## 5 · Absicherung & Grenzen

- **GB-07** ist der eigentliche Check: `adoption_rate_monitored=true` im
  JSON ist nur die **Selbstaussage** — die **tatsächliche Messung** eines
  Verantwortlichen ist die Evidenz. `validate.py` prüft das Flag; die
  **Praxis** (Dashboard + Verantwortlicher) ist der Betrieb.
- **GB-03** (Rule of Two, `warn`) — bei `foreign_input=true` und
  `sensitive_data=true` ist die Kombination **2 von 3**. Bei Level 2 ist
  das **erlaubt** (Mensch in der Kette), aber ein **Risk-Hinweis**:
  Prompt-Injection kann in der Fremdeingabe stecken. Empfehlung:
  **isolierte Klassifikation** (tool-frei) + `verify`.
- **GB-04** (Deckel) — der `ceiling` im JSON ist **politischer**
  Charakter. Wer ein Level-2-System auf Level 3+ hochstufen will, muss
  die Instanz finden, die den Deckel verabschiedet hat. **Kein**
  Self-Service.
- **DSG Art. 21** — menschliche Überwachung bei algorithmischen
  Entscheidungen; `adoption_rate_monitored` = die technische Umsetzung
  im Modell. (DSG-Texte sind kein Rechtsrat — hier nur die technische
  Entsprechung.)
- **Kein Rechtsrat** — AI Act Annex III, DSG, NIS2 sind **technische
  Grenzen** im Validator; die rechtliche Würdigung ist eine Rechtsfrage.

---

## 6 · Offene Punkte / Risiken

- **Typischer Fehler:** Level 2 als «Level 1 mit mehr Modell» verkaufen.
  Der Unterschied: **das Modell plant mit**, aber **je Aktion wird
  freigegeben** — und die **Übernahmequote wird gemessen**. Ohne
  `adoption_rate_monitored=true` ist das Level **nicht valid**
  (GB-07 `error`).
- **Deckel (GB-04)** — der Deckel ist eine **politische** Grenze, keine
  technische. Wer den Deckel hebt, ist die **Instanz**, die den Deckel
  verabschiedet hat (nicht der Betrieb).
- **Kein Mandat-Flag** auf Level 2 (erst ab Level 4) — Level 2 ist
  «Vorschlag + Freigabe», nicht «Mandat mit Limits im System». Ein
  `mandate`-Objekt auf Level 2 ist **Inkonsistenz** (GB-02/GB-08).
- **Kein Kill-Switch-Pflicht** auf Level 2 (GB-12 ist ab Level 3) — aber
  ein «abstellen-können» ist gute Praxis (besonders bei
  Bewerbungsvorsortierung, wo ein Fehlvorlage schnell «unfreundlich»
  wirkt).
- **Adoption-Quote ist die Metrik, die man liest.** Ohne ein Dashboard
  und einen Verantwortlichen, der die Quote liest, ist `adoption_rate_
 monitored=true` im JSON eine **Selbstaussage ohne Evidenz** — das ist
  genau der Punkt, an dem der Validator ehrlich bleibt.

---

*Grundlage: `validate.py` (GB-01, 02, 03, 04, 05, 07, 15), `schema.py::
ALLOWED_AXES[2]`, `examples/gw2-bewerbungsvorsortierung.json`,
`../unternehmens-implementierung.md` §3, `../technik-eroeffnung.md`.
Keine Preise, kein Rechtsrat.*
