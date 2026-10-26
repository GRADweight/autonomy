# Level 1 — Assistent (Mensch plant und steuert jede Aktion)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/autonomy` · **Level 1**
>
> **Achsen** (`schema.py::ALLOWED_AXES[1]`): `(human, full_control)` oder
> `(human, per_action)` — **der Mensch plant den Weg**; jede Aktion wird vom
> **Menschen ausgelöst/geprüft**. Das Modell **vorbereitet**, der Mensch
> **entscheidet und führt aus**.
> **Referenz-Case:** `examples/gw1-produktwissen-innendienst.json` (valid,
> `exit 0`).
>
> Kurz: Ein **Assistent aus der eigenen Wissensbasis**, der **keine
> Aussenwirkung** hat und **niederschriftlich** antwortet.

---

## 1 · Was Level 1 ist (und was nicht)

**Ja:** Produktfragen aus Katalog+Offerten antworten, interne Recherche,
Entwürfe, Antworten mit Quelle. Der Mensch klickt «senden», «übernehmen»,
«eintragen».

**Nein (GB-10, hard):** **keine ausgehende Aktion** — also keine
E-Mail-Auslieferung, kein Ticket-Erstellen, keine API-Schreibzugriffe, keine
externen Links/Bilder in der Antwort (README §2/§7, `validate.py` GB-10).
Level 1 ist «**niederschriftlich**», nicht «**absendend**».

---

## 2 · GB-Pflichten auf Level 1

| Regel | Auswirkung bei Level 1 |
|---|---|
| **GB-01** / **GB-02** | **error** — Schema + Achsen `(human, full_control)` oder `(human, per_action)` |
| **GB-10** Aussenwirkung | **error** — `customer_facing=true` **und** `external_action=true` → «keine Aussenwirkung». Das ist die hard Level-1-Grenze: **keine Sende-Tools, keine externen Links**. |
| **GB-03** Rule of Two | `warn`, wenn alle 3 zugleich — bei Level 1 aber **nicht** das Ziel (Mensch in der Kette) |
| **GB-05** Kundentexte | `warn`, wenn `customer_text_in_decisions=true` — isolierte Klassifikation ohne Tools empfohlen |
| **GB-15** Datenklasse | **error**, wenn `sensitive_data=true` und `data_class` fehlt — bei `data_class='geheim'` **error** schon ab Level 1 |
| **GB-06** Schutzfunktionen | `warn` bei `safety_critical=true` (Deckel 2: max. Level 3) |

**Keine** harten GB-07/08/11/12/13/14 auf Level 1.

---

## 3 · Referenz-Case `gw1-produktwissen-innendienst.json`

```
level: 1
who_plans: human            human_role: per_action
foreign_input: false        sensitive_data: true
external_action: false      money_effect: false
customer_facing: false      customer_text_in_decisions: false
safety_critical: false      data_class: intern    data_residency: ch
governance: … audit_log=true, kill_switch_tested=true,
  shadow_run_first=FALSE, proposal_mode_first=FALSE, …
```

**Lesart:** `external_action=false` → GB-10 nicht ausgelöst (das ist die
Level-1-Grundregel). `sensitive_data=true` + `data_class=intern` → GB-15 ok.
`per_action` = das Modell **vorschlägt**, der Mensch **freigibt/auslöst**
jede Aktion (hier: «antworten senden», «Offerte übernehmen»).

---

## 4 · Technische Umsetzung im Unternehmen

### 4.1 Was stehen muss

- **Wissensbasis** — ein RAG-Setup (Vektorspeicher + Embeddings) oder ein
  strukturiertes Repo (Markdown, CSV, JSON) auf dem das Modell antwortet.
  Für `intern`-Daten: Schweizer/On-Prem bevorzugt (DSG).
- **Antwort mit Quelle** — das Modell gibt eine Antwort **plus** die
  Fundstellen (Seite, Dokument, Abschnitt). `gw_core.verify.pruefe_antwort`
  prüft (Zweitmodell) Antwort gegen die Fundstellen, **VETO** bei
  Widersprüchen.
- **Audit-Trail** — `gw_core.audit.AuditTrail`: wer, wann, welche Frage,
  welche Antwort, welche Quelle. `incident_log` bei Abweichung.
- **Freigabe-Fluss** (bei `per_action`): das System zeigt den Entdraft, der
  Mensch tippt «ok»/«korrigieren»/«ablehnen». Kann ein simples Webform,
  eine CLI, oder ein E-Mail-Filter sein. **Kein** automatisches Senden.
- **Ein Verantwortlicher** (`governance.owner`) und eine **Richtlinie**,
  was das Assistenz-Modell darf / nicht darf.

### 4.2 Bausteine (`gw_core`)

- `verify.pruefe_antwort` — **empfohlen** (Halluzinations-Sicherung,
  Quellenprüfung, VETO).
- `audit.AuditTrail` — **empfohlen** (wer/was/wann, CSV-Export).
- `authz.FreigabePolicy` — **empfohlen** (wer darf zugreifen,
  Least Privilege).
- `approval.ApprovalQueue` — **optional**, wenn `per_action` einen
  Freigabe-Warteschlange-Fluss braucht («diese Antwort ist bereit zum
  Absenden, bitte freigeben»).
- `tracing` — **optional**, für LLM-Request-Trace.
- `rollback` / `exception_queue` / `sampling_audit` / `bexio` — **nicht**
  nötig auf Level 1 (keine Aussenwirkung, kein Geld, kein Mandat, keine
  autonomen Schleifen).

### 4.3 Hardware / Infrastruktur

| Schicht | Option |
|---|---|
| Inferenz | 7B–14B, Ollama, lokal oder CH-Cloud (Exoscale/Infomaniak). Kein GPU-Zwang. |
| RAG | Vektorspeicher (SQLite-Vector/Chroma/FAISS), lokal oder CH. Bei `vertraulich`+ → On-Prem. |
| Control-Plane | `gw_core` (SQLite) — lokal, kein Standort-Risiko. |
| Zielsystem | **Keine** (Level-1-Definition, GB-10). |

---

## 5 · Absicherung & Grenzen

- **GB-10 (kein Aussenw.)** ist die **härteste Level-1-Grenze**. Wenn das
  System selbst sendet, ist das schon Level 2+ (`per_action` mit
  `external_action=true`, Freigabe je Aktion) — `validate.py` prüft das.
- **Prompt-Injection (GB-03/GB-05):** bei `foreign_input=true` oder
  `customer_text_in_decisions=true` → `warn`. **Isolierte Klassifikation
  ohne Tools** empfohlen (README §7, `terminology.isoliert`).
- **DSG (SR 235.1)** bei `intern/vertraulich`: Schweizer/On-Prem-Pfad.
- **Kein Rechtsrat** — DSG/AI Act sind **technische Grenzen**, die wir im
  Validator/Code prüfen; die rechtliche Würdigung ist eine Rechtsfrage.

---

## 6 · Offene Punkte / Risiken

- **Typischer Fehler:** Level 1 als «Level 2 ohne Freigabe» verkaufen —
  wenn `external_action=true`, ist das schon Level 2 (der Validator
  meldet GB-10). Entscheidend: **keine Aussenwirkung**, nur
  «niederschriftlich».
- **Kein Mandat-Flag** auf Level 1 — `mandate` ist erst ab Level 4
  (`model, mandate`) relevant. Wer `mandate.limits_in_system` auf Level 1
  setzt, ist inkonsistent (GB-02/GB-08).
- **Kein Kill-Switch-Pflicht** auf Level 1 (GB-12 ist ab Level 3) — aber
  ein «abstellen-können» ist gute Praxis.
- **Kein Messungs-Pflicht** auf Level 1 (GB-14 ist ab Level 3) — aber
  `audit_log=true` + ein Verantwortler = die minimale Evidenz.

---

*Grundlage: `validate.py` (GB-01, 02, 10, 15, 06), `schema.py::ALLOWED_AXES[1]`,
`examples/gw1-produktwissen-innendienst.json`, `../unternehmens-implementierung.md`
§3. Keine Preise, kein Rechtsrat.*
